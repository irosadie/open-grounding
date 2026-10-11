"""Worker job: summarize a completed conversation into a memory chunk."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.memory_summarizer import MemorySummarizer
from app.core.llm_rollout_trace import rollout_context
from app.core.settings import Settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


async def summarize_conversation(
    *,
    conversation_id: str,
    tenant_id: str,
    knowledge_base_id: str,
    project_id: str | None = None,
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
    async with rollout_context(
        source="memory.summarize",
        trace_dir=settings.rag_llm_trace_dir,
        enabled=settings.rag_llm_trace_enabled,
        metadata={"conversation_id": conversation_id, "knowledge_base_id": knowledge_base_id},
    ) as trace:
        for i in range(1, MAX_RETRIES + 1):
            try:
                trace.record("turn_started", {"attempt": i, "conversation_id": conversation_id})
                trace.record(
                    "compaction",
                    {
                        "operation": "memory.summarize",
                        "conversation_id": conversation_id,
                        "reason": "summarize_conversation",
                        "attempt": i,
                    },
                )
                result = await summarizer.summarize(
                    conversation_id=conversation_id,
                    tenant_id=tenant_id,
                    knowledge_base_id=knowledge_base_id,
                    project_id=project_id,
                    user_id=user_id,
                    session=session,
                )
                trace.record("turn_completed", {"attempt": i, "created": result})
                return result
            except Exception as e:
                trace.record("llm_retry", {"attempt": i, "max_attempts": MAX_RETRIES, "error_type": type(e).__name__, "error": str(e)})
                logger.warning(
                    "[memory.summarize] attempt %d/%d failed for conversation=%s: %s",
                    i,
                    MAX_RETRIES,
                    conversation_id,
                    e,
                )
                if i == MAX_RETRIES:
                    trace.record("turn_failed", {"attempt": i, "error_type": type(e).__name__, "error": str(e)})
                    logger.error(
                        "[memory.summarize] moving to dead letter after %d attempts: conversation=%s",
                        MAX_RETRIES,
                        conversation_id,
                    )
                    raise
    return False
