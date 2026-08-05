"""Validate stage — verify vector count and set document to READY or FAILED."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.infrastructure.rag_catalog import (
    SqlAlchemyDocumentVersionRepository,
    SqlAlchemyIndexProfileRepository,
)
from app.workers.stages.parse import _chunks_cache, _parsed_cache, _vectors_cache

logger = logging.getLogger(__name__)


async def validate_and_finalize(
    document_version_id: str,
    tenant_id: str,
    session: AsyncSession,
    settings: Settings,
) -> None:
    """Verify vector count matches chunk count, then set READY or FAILED."""
    repo = SqlAlchemyDocumentVersionRepository(session)
    index_repo = SqlAlchemyIndexProfileRepository(session)

    await repo.update_lifecycle_state(
        tenant_id=tenant_id, version_id=document_version_id, lifecycle_state="VALIDATING"
    )

    chunks = _chunks_cache.get(document_version_id, [])
    vectors = _vectors_cache.get(document_version_id, [])
    expected_count = len(chunks)

    index_profile = await index_repo.find_active(tenant_id=tenant_id)
    if index_profile is None:
        await repo.update_lifecycle_state(
            tenant_id=tenant_id, version_id=document_version_id, lifecycle_state="FAILED"
        )
        raise ValueError("No active index profile found during validation.")

    # Verify in Qdrant
    qdrant_url = getattr(settings, "qdrant_url", None) or "http://127.0.0.1:6334"
    qdrant_api_key = getattr(settings, "qdrant_api_key", None)

    try:
        from qdrant_client import AsyncQdrantClient
        client = AsyncQdrantClient(url=qdrant_url, api_key=qdrant_api_key)

        result = await client.count(
            collection_name=index_profile.collection,
            count_filter={
                "must": [
                    {"key": "document_version_id", "match": {"value": document_version_id}},
                    {"key": "is_active", "match": {"value": True}},
                ]
            },
            exact=True,
        )
        actual_count = result.count
        await client.close()
    except Exception as e:
        logger.error("[validate] Qdrant count failed for %s: %s", document_version_id, e)
        await repo.update_lifecycle_state(
            tenant_id=tenant_id, version_id=document_version_id, lifecycle_state="FAILED"
        )
        raise

    if actual_count != expected_count:
        logger.error(
            "[validate] FAILED %s: expected %d vectors, found %d",
            document_version_id, expected_count, actual_count,
        )
        await repo.update_lifecycle_state(
            tenant_id=tenant_id, version_id=document_version_id, lifecycle_state="FAILED"
        )
        raise ValueError(f"Vector count mismatch: expected {expected_count}, got {actual_count}")

    await repo.update_lifecycle_state(
        tenant_id=tenant_id, version_id=document_version_id, lifecycle_state="READY"
    )

    # Cleanup in-memory cache
    _parsed_cache.pop(document_version_id, None)
    _chunks_cache.pop(document_version_id, None)
    _vectors_cache.pop(document_version_id, None)

    logger.info("[validate] READY %s (%d vectors)", document_version_id, actual_count)
