"""Worker job: prune expired memory chunks from Qdrant and DB."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.memory_summarizer import MemorySummarizer
from app.core.settings import Settings

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


async def prune_expired_memory(
    *,
    session: AsyncSession,
    settings: Settings,
) -> int:
    """Delete expired memory chunks (Qdrant + DB). Returns count of deleted chunks."""
    from app.infrastructure.rag_catalog import SqlAlchemyMemoryChunkRepository

    chunk_repo = SqlAlchemyMemoryChunkRepository(session)
    summarizer = MemorySummarizer(settings)

    chunks = await chunk_repo.find_expired(limit=BATCH_SIZE)
    if not chunks:
        logger.info("[memory.prune] no expired chunks found")
        return 0

    deleted = 0
    for chunk in chunks:
        try:
            await summarizer.delete_qdrant_points_by_ids(point_ids=[chunk.qdrant_point_id])
        except Exception as e:
            logger.warning("[memory.prune] failed to delete Qdrant point %s: %s — skipping", chunk.qdrant_point_id, e)
            continue
        try:
            await chunk_repo.delete_many(chunk_ids=[chunk.id])
            deleted += 1
        except Exception as e:
            logger.warning("[memory.prune] failed to delete DB chunk %s: %s — skipping", chunk.id, e)

    logger.info("[memory.prune] deleted %d expired chunks", deleted)
    return deleted
