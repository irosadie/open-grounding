"""Embed stage — embed chunks using active IndexProfile's embedding provider."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dev_trace import get_tracer
from app.core.settings import Settings
from app.infrastructure.providers.registry import ProviderRegistry
from app.infrastructure.rag_catalog import (
    SqlAlchemyDocumentVersionRepository,
    SqlAlchemyIndexProfileRepository,
    SqlAlchemyModelProfileRepository,
)
from app.workers.stages.parse import _chunks_cache, _vectors_cache

logger = logging.getLogger(__name__)

# Batch size for embedding API calls
EMBED_BATCH_SIZE = 50


async def embed_chunks(
    document_version_id: str,
    tenant_id: str,
    session: AsyncSession,
    settings: Settings,
) -> list[list[float]]:
    """Embed all chunks using the active IndexProfile's embedding provider."""
    repo = SqlAlchemyDocumentVersionRepository(session)
    index_repo = SqlAlchemyIndexProfileRepository(session)
    model_repo = SqlAlchemyModelProfileRepository(session)

    await repo.update_lifecycle_state(
        tenant_id=tenant_id, version_id=document_version_id, lifecycle_state="EMBEDDING"
    )

    chunks = _chunks_cache.get(document_version_id)
    if not chunks:
        raise ValueError(f"No chunks found for {document_version_id}. Chunk stage must run first.")

    index_profile = await index_repo.find_active(tenant_id=tenant_id)
    if index_profile is None:
        raise ValueError("No active index profile found.")

    emb_profile = await model_repo.find_by_id(
        tenant_id=tenant_id, profile_id=index_profile.embedding_profile_id
    )
    if emb_profile is None:
        raise ValueError(f"Embedding profile {index_profile.embedding_profile_id} not found.")

    registry = ProviderRegistry(settings)
    vectors = await registry.embed_with_fallback(
        texts=chunks,
        primary_provider=emb_profile.provider,
        primary_model=emb_profile.model,
        tenant_id=tenant_id,
        session=session,
    )

    dim = len(vectors[0]) if vectors else 0
    tracer = get_tracer()
    async with tracer.op(
        "ingestion.embed",
        version_id=document_version_id,
        vectors=len(vectors),
        dim=dim,
        verbose_meta={"provider": emb_profile.provider, "model": emb_profile.model},
    ):
        _vectors_cache[document_version_id] = vectors

    logger.info("[embed] %d vectors (dim=%d) for %s", len(vectors), dim, document_version_id)
    return vectors
