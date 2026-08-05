"""Embed stage — embed chunks using active IndexProfile's embedding provider."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.infrastructure.rag_catalog import (
    SqlAlchemyDocumentVersionRepository,
    SqlAlchemyIndexProfileRepository,
    SqlAlchemyModelProfileRepository,
)
from app.infrastructure.providers.registry import ProviderRegistry
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
    provider = registry.get_embedding_provider(emb_profile.provider, emb_profile.model)

    # Embed in batches
    all_vectors: list[list[float]] = []
    for i in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[i : i + EMBED_BATCH_SIZE]
        vectors = await provider.embed(batch)  # type: ignore[union-attr]
        all_vectors.extend(vectors)
        logger.info("[embed] batch %d/%d for %s", i // EMBED_BATCH_SIZE + 1, -(-len(chunks) // EMBED_BATCH_SIZE), document_version_id)

    _vectors_cache[document_version_id] = all_vectors
    logger.info("[embed] %d vectors (dim=%d) for %s", len(all_vectors), len(all_vectors[0]) if all_vectors else 0, document_version_id)
    return all_vectors
