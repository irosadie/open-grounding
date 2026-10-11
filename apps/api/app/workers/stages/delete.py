"""Hard-delete stage for document versions and their derived resources."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.domain.rag.catalog import DocumentVersionLifecycleState, IndexGeneration, IndexGenerationStatus
from app.domain.tenant_context import TenantContext
from app.infrastructure.object_store import S3ObjectStoreAdapter
from app.infrastructure.qdrant import QdrantVectorStoreAdapter
from app.infrastructure.rag_answer_trace import AnswerCitationRecord
from app.infrastructure.rag_catalog import (
    DocumentRecord,
    DocumentVersionRecord,
    IndexGenerationRecord,
    SqlAlchemyDocumentVersionRepository,
    SqlAlchemyIndexGenerationRepository,
    SqlAlchemyIndexProfileRepository,
)
from app.workers.stages.parse import _chunks_cache, _parsed_cache, _vectors_cache

logger = logging.getLogger(__name__)


async def delete_document_version(
    document_version_id: str,
    tenant_id: str,
    session: AsyncSession,
    settings: Settings,
) -> None:
    """Remove one DELETING version from Qdrant, object storage, and Postgres.

    The stage is deliberately idempotent. A retry re-applies the same scoped
    external deletes and then sees either the still-present DELETING row or no
    row at all after a previous successful attempt.
    """
    version_repo = SqlAlchemyDocumentVersionRepository(session)
    version = await version_repo.find_by_id(tenant_id=tenant_id, version_id=document_version_id)
    if version is None:
        logger.warning("[delete] version already absent: %s", document_version_id)
        return
    if version.lifecycle_state is not DocumentVersionLifecycleState.DELETING:
        logger.warning(
            "[delete] skipping version %s in state %s",
            document_version_id,
            version.lifecycle_state.value,
        )
        return

    generation_repo = SqlAlchemyIndexGenerationRepository(session)
    generations = await generation_repo.list_for_version(
        tenant_id=tenant_id,
        document_version_id=document_version_id,
    )

    # Answer trace rows are audit history. Nulling both source references keeps
    # those rows while unblocking the RESTRICT FKs for chunks and versions.
    await session.execute(
        update(AnswerCitationRecord)
        .where(
            AnswerCitationRecord.tenant_id == tenant_id,
            AnswerCitationRecord.document_version_id == document_version_id,
        )
        .values(document_version_id=None, chunk_id=None)
    )
    await session.execute(
        text(
            """
            UPDATE rag_selected_evidence
            SET chunk_id = NULL
            WHERE tenant_id = :tenant_id
              AND chunk_id IN (
                  SELECT id
                  FROM rag_chunks
                  WHERE tenant_id = :tenant_id
                    AND document_version_id = :document_version_id
              )
            """
        ),
        {
            "tenant_id": tenant_id,
            "document_version_id": document_version_id,
        },
    )
    await session.flush()

    await _delete_vectors(
        tenant_id=tenant_id,
        document_version_id=document_version_id,
        generations=generations,
        session=session,
        settings=settings,
    )
    if version.object_key_raw:
        await S3ObjectStoreAdapter(settings).delete_object(version.object_key_raw)

    await session.execute(
        update(IndexGenerationRecord)
        .where(
            IndexGenerationRecord.tenant_id == tenant_id,
            IndexGenerationRecord.document_version_id == document_version_id,
        )
        .values(status=IndexGenerationStatus.DELETED)
    )
    await session.execute(
        update(DocumentVersionRecord)
        .where(
            DocumentVersionRecord.tenant_id == tenant_id,
            DocumentVersionRecord.id == document_version_id,
        )
        .values(
            parsed_text=None,
            lifecycle_state=DocumentVersionLifecycleState.DELETED,
        )
    )
    await session.flush()

    await session.execute(
        delete(DocumentVersionRecord).where(
            DocumentVersionRecord.tenant_id == tenant_id,
            DocumentVersionRecord.id == document_version_id,
        )
    )
    remaining_versions = await session.scalar(
        select(func.count())
        .select_from(DocumentVersionRecord)
        .where(
            DocumentVersionRecord.tenant_id == tenant_id,
            DocumentVersionRecord.document_id == version.document_id,
        )
    )
    if remaining_versions == 0:
        await session.execute(
            update(DocumentRecord)
            .where(
                DocumentRecord.tenant_id == tenant_id,
                DocumentRecord.id == version.document_id,
            )
            .values(deleted_at=func.now())
        )

    await session.commit()
    _clear_pipeline_caches(document_version_id)
    logger.info("[delete] completed document version %s", document_version_id)


async def _delete_vectors(
    *,
    tenant_id: str,
    document_version_id: str,
    generations: list[IndexGeneration],
    session: AsyncSession,
    settings: Settings,
) -> None:
    if not generations:
        return

    profile_repo = SqlAlchemyIndexProfileRepository(session)
    tenant = TenantContext(tenant_id=tenant_id, membership_id=tenant_id, user_id=tenant_id)
    async with httpx.AsyncClient(timeout=30.0) as client:
        vector_store = QdrantVectorStoreAdapter(settings, client)
        for generation in generations:
            generation_id = generation.id
            profile_id = generation.index_profile_id
            profile = await profile_repo.find_by_id(tenant_id=tenant_id, profile_id=profile_id)
            if profile is None:
                raise RuntimeError(
                    f"Index profile {profile_id} for generation {generation_id} was not found"
                )
            try:
                await vector_store.delete_points(
                    tenant=tenant,
                    collection=profile.collection,
                    document_version_id=document_version_id,
                )
            except httpx.HTTPStatusError as error:
                if error.response.status_code != 404:
                    raise
                logger.warning(
                    "[delete] Qdrant collection %s is absent for generation %s",
                    profile.collection,
                    generation_id,
                )


def _clear_pipeline_caches(document_version_id: str) -> None:
    _parsed_cache.pop(document_version_id, None)
    _chunks_cache.pop(document_version_id, None)
    _vectors_cache.pop(document_version_id, None)
