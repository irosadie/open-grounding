"""Worker job: summarize a completed conversation into a memory chunk."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.memory_summarizer import MemorySummarizer
from app.core.settings import Settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


async def summarize_conversation(
    *,
    conversation_id: str,
    tenant_id: str,
    knowledge_base_id: str,
    user_id: str,
    session: AsyncSession,
    settings: Settings,
    attempt: int = 1,
) -> bool:
    """Summarize a conversation into a persistent memory chunk.

    Returns True if a chunk was created, False if skipped (already summarized,
    too few turns, memory disabled). Raises on unrecoverable failure after retries.
    """
    summarizer = MemorySummarizer(settings)
    for i in range(1, MAX_RETRIES + 1):
        try:
            return await summarizer.summarize(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                knowledge_base_id=knowledge_base_id,
                user_id=user_id,
                session=session,
            )
        except Exception as e:
            logger.warning(
                "[memory.summarize] attempt %d/%d failed for conversation=%s: %s",
                i,
                MAX_RETRIES,
                conversation_id,
                e,
            )
            if i == MAX_RETRIES:
                logger.error(
                    "[memory.summarize] moving to dead letter after %d attempts: conversation=%s",
                    MAX_RETRIES,
                    conversation_id,
                )
                raise
    return False
