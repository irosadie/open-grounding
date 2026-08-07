"""Async RAG query worker — BullMQ Worker.

Picks up jobs from the rag.query queue, runs RagQueryService.query(),
updates rag_query_jobs status, and fires optional webhooks.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx
from bullmq import Job, Worker

from app.core.settings import Settings
from app.infrastructure.rag_catalog import SqlAlchemyRagQueryJobRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


async def _fire_webhook(
    url: str | None,
    job_id: str,
    status: str,
    result: dict[str, Any] | None,
    error: str | None,
) -> None:
    if not url:
        return
    payload = {"jobId": job_id, "status": status, "result": result, "error": error}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=payload)
    except Exception:
        pass  # fire-and-forget


def _build_rag_query_service(settings: Settings, session: "AsyncSession") -> "RagQueryService":  # type: ignore[name-defined]
    from app.application.rag_generation import RagGenerationService
    from app.application.rag_hybrid_retrieval import RagHybridRetrievalService
    from app.application.rag_query_service import RagQueryService
    from app.infrastructure.embedding_adapter import ProfileSparseEncoderAdapter, ProviderEmbeddingAdapter
    from app.infrastructure.generation_adapter import LLMGenerationAdapter
    from app.infrastructure.qdrant import QdrantVectorStoreAdapter
    from app.infrastructure.rag_answer_trace import SqlAlchemyAnswerRunRepository, SqlAlchemyAnswerTraceDetailRepository
    from app.infrastructure.rag_catalog import (
        SqlAlchemyDecompositionConfigRepository,
        SqlAlchemyIndexGenerationRepository,
        SqlAlchemyIndexProfileRepository,
        SqlAlchemyKnowledgeBaseRepository,
        SqlAlchemyPlannerConfigRepository,
        SqlAlchemyRetrievalConfigRepository,
    )
    from app.infrastructure.rag_conversations import SqlAlchemyConversationHistoryRepository
    from app.interfaces.http.dependencies import get_rag_query_admission

    client = httpx.AsyncClient(timeout=30.0)
    retrieval = RagHybridRetrievalService(
        settings,
        ProviderEmbeddingAdapter(settings),
        ProfileSparseEncoderAdapter(settings),
        QdrantVectorStoreAdapter(settings, client),
        SqlAlchemyRetrievalConfigRepository(session),
    )
    generation = RagGenerationService(settings, LLMGenerationAdapter(settings))

    return RagQueryService(
        settings,
        SqlAlchemyAnswerRunRepository(session),
        get_rag_query_admission(),
        SqlAlchemyKnowledgeBaseRepository(session),
        SqlAlchemyConversationHistoryRepository(session),
        SqlAlchemyIndexGenerationRepository(session),
        SqlAlchemyAnswerTraceDetailRepository(session),
        SqlAlchemyDecompositionConfigRepository(session),
        SqlAlchemyIndexProfileRepository(session),
        retrieval,
        generation,
        planner_configs=SqlAlchemyPlannerConfigRepository(session),
    )


def create_query_worker(
    settings: Settings,
    session_factory: "async_sessionmaker",
    redis_url: str,
) -> Worker:
    """Return a BullMQ Worker for the rag.query queue."""

    async def handle_rag_query(job: Job, token: str) -> None:
        data = job.data
        job_id: str = data["job_id"]
        tenant_id: str = data["tenant_id"]
        user_id: str = data["user_id"]
        membership_id: str = data.get("membership_id", "")
        webhook_url: str | None = data.get("webhook_url")

        logger.info("[rag.query] job=%s tenant=%s", job_id, tenant_id)

        from app.domain.tenant_context import TenantContext

        async with session_factory() as session:
            repo = SqlAlchemyRagQueryJobRepository(session)
            await repo.update_running(job_id)

            decomposition = data.get("decomposition") or {}
            planner = data.get("planner") or {}
            memory = data.get("memory") or {}

            tenant = TenantContext(tenant_id=tenant_id, user_id=user_id, membership_id=membership_id)

            try:
                service = _build_rag_query_service(settings, session)
                result = await service.query(
                    tenant=tenant,
                    message=data["message"],
                    knowledge_base_ids=tuple(data["knowledge_base_ids"]),
                    conversation_id=data.get("conversation_id"),
                    decomposition_enabled=decomposition.get("enabled") if decomposition else None,
                    decomposition_max_sub_queries=decomposition.get("max_sub_queries") if decomposition else None,
                    planner_enabled=planner.get("enabled") if planner else None,
                    planner_max_tasks=planner.get("max_tasks") if planner else None,
                    planner_task_types=tuple(planner["task_types"]) if planner and planner.get("task_types") else None,
                    memory_enabled=memory.get("enabled") if memory else None,
                    session=session,
                )
                await repo.update_completed(job_id, dict(result))
                logger.info("[rag.query] job=%s completed", job_id)
                await _fire_webhook(webhook_url, job_id, "completed", dict(result), None)
            except Exception as exc:
                await repo.update_failed(job_id, str(exc))
                logger.error("[rag.query] job=%s failed: %s", job_id, exc)
                await _fire_webhook(webhook_url, job_id, "failed", None, str(exc))
                raise

    worker = Worker("rag.query", handle_rag_query, {"connection": redis_url, "concurrency": 10})
    worker.on("failed", lambda job, err: logger.error(
        "[rag.query] job=%s permanently failed: %s", job.id if job else "?", err
    ))
    return worker
