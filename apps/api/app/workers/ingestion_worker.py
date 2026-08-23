"""Ingestion pipeline workers — BullMQ-backed via python-bullmq.

Replaces the hand-rolled IngestionWorker class with proper bullmq.Worker
instances. Each stage gets its own Worker for independent concurrency control.
Stage-to-stage chaining uses bullmq.Queue.add() to keep job lifecycle within
BullMQ's Lua-managed state machine.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bullmq import Job, Queue, Worker

from app.core.settings import Settings
from app.infrastructure.database import create_session_factory
from app.workers.stages.chunk import chunk_document
from app.workers.stages.embed import embed_chunks
from app.workers.stages.index import index_chunks
from app.workers.stages.memory_prune import prune_expired_memory
from app.workers.stages.memory_summarize import summarize_conversation
from app.workers.stages.parse import parse_document
from app.workers.stages.validate import validate_and_finalize

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)

QUEUE_PARSE = "ingestion.parse"
QUEUE_CHUNK = "ingestion.chunk"
QUEUE_EMBED = "ingestion.embed"
QUEUE_INDEX = "ingestion.index"
QUEUE_VALIDATE = "ingestion.validate"
QUEUE_MEMORY_SUMMARIZE = "memory.summarize"
QUEUE_MEMORY_PRUNE = "memory.prune"

_DEFAULT_JOB_OPTS: dict[str, object] = {
    "attempts": 3,
    "backoff": {"type": "exponential", "delay": 5000},
}


async def enqueue_memory_summarize(
    *,
    conversation_id: str,
    tenant_id: str,
    knowledge_base_id: str,
    user_id: str,
    redis_url: str,
) -> None:
    """Enqueue a memory.summarize job. Called from application layer."""
    q = Queue(QUEUE_MEMORY_SUMMARIZE, {"connection": redis_url})
    try:
        await q.add(
            "summarize",
            {
                "conversationId": conversation_id,
                "tenantId": tenant_id,
                "knowledgeBaseId": knowledge_base_id,
                "userId": user_id,
            },
            {**_DEFAULT_JOB_OPTS, "jobId": f"mem:{conversation_id}"},
        )
    finally:
        await q.close()


async def _mark_failed(
    document_version_id: str,
    tenant_id: str,
    session_factory: "async_sessionmaker",
) -> None:
    from app.infrastructure.rag_catalog import SqlAlchemyDocumentVersionRepository

    async with session_factory() as session:
        repo = SqlAlchemyDocumentVersionRepository(session)
        await repo.update_lifecycle_state(
            tenant_id=tenant_id,
            version_id=document_version_id,
            lifecycle_state="FAILED",
        )


def create_ingestion_workers(
    settings: Settings,
    session_factory: "async_sessionmaker",
    redis_url: str,
) -> list[Worker]:
    """Create all ingestion + memory BullMQ workers."""

    def _on_failed_ingestion(job: Job | None, error: Exception) -> None:
        """Mark document version FAILED after all retry attempts exhausted."""
        if job is None:
            return
        max_attempts = (job.opts or {}).get("attempts", _DEFAULT_JOB_OPTS["attempts"])
        if job.attemptsMade >= max_attempts:
            import asyncio
            version_id = (job.data or {}).get("documentVersionId", "")
            tenant_id = (job.data or {}).get("tenantId", "")
            if version_id and tenant_id:
                asyncio.create_task(
                    _mark_failed(version_id, tenant_id, session_factory)
                )

    async def handle_parse(job: Job, token: str) -> None:
        data = job.data
        version_id = data["documentVersionId"]
        tenant_id = data["tenantId"]
        logger.info("[parse] %s", version_id)
        async with session_factory() as session:
            await parse_document(version_id, tenant_id, session, settings)
            # Check lifecycle state — only continue to chunk if not waiting for human review
            from app.infrastructure.rag_catalog import SqlAlchemyDocumentVersionRepository
            repo = SqlAlchemyDocumentVersionRepository(session)
            version = await repo.find_by_id(tenant_id=tenant_id, version_id=version_id)
            if version is None or version.lifecycle_state in ("NEEDS_REVIEW", "FAILED"):
                logger.info("[parse] halting pipeline — state=%s for %s", version.lifecycle_state if version else "NOT_FOUND", version_id)
                return
        q = Queue(QUEUE_CHUNK, {"connection": redis_url})
        try:
            await q.add("chunk", data, _DEFAULT_JOB_OPTS)
        finally:
            await q.close()

    async def handle_chunk(job: Job, token: str) -> None:
        data = job.data
        version_id = data["documentVersionId"]
        tenant_id = data["tenantId"]
        logger.info("[chunk] %s", version_id)
        async with session_factory() as session:
            await chunk_document(version_id, tenant_id, session, settings)
        q = Queue(QUEUE_EMBED, {"connection": redis_url})
        try:
            await q.add("embed", data, _DEFAULT_JOB_OPTS)
        finally:
            await q.close()

    async def handle_embed(job: Job, token: str) -> None:
        data = job.data
        version_id = data["documentVersionId"]
        tenant_id = data["tenantId"]
        logger.info("[embed] %s", version_id)
        async with session_factory() as session:
            await embed_chunks(version_id, tenant_id, session, settings)
        q = Queue(QUEUE_INDEX, {"connection": redis_url})
        try:
            await q.add("index", data, _DEFAULT_JOB_OPTS)
        finally:
            await q.close()

    async def handle_index(job: Job, token: str) -> None:
        data = job.data
        version_id = data["documentVersionId"]
        tenant_id = data["tenantId"]
        logger.info("[index] %s", version_id)
        async with session_factory() as session:
            await index_chunks(version_id, tenant_id, session, settings)
        q = Queue(QUEUE_VALIDATE, {"connection": redis_url})
        try:
            await q.add("validate", data, _DEFAULT_JOB_OPTS)
        finally:
            await q.close()

    async def handle_validate(job: Job, token: str) -> None:
        data = job.data
        version_id = data["documentVersionId"]
        tenant_id = data["tenantId"]
        logger.info("[validate] %s", version_id)
        async with session_factory() as session:
            await validate_and_finalize(version_id, tenant_id, session, settings)

    async def handle_memory_summarize(job: Job, token: str) -> None:
        data = job.data
        logger.info("[memory.summarize] conversation=%s", data.get("conversationId"))
        async with session_factory() as session:
            await summarize_conversation(
                conversation_id=data["conversationId"],
                tenant_id=data["tenantId"],
                knowledge_base_id=data.get("knowledgeBaseId", ""),
                user_id=data.get("userId", ""),
                session=session,
                settings=settings,
            )

    async def handle_memory_prune(job: Job, token: str) -> None:
        logger.info("[memory.prune] running batch prune")
        async with session_factory() as session:
            deleted = await prune_expired_memory(session=session, settings=settings)
        logger.info("[memory.prune] deleted %d chunks", deleted)

    conn = {"connection": redis_url}
    ingestion_opts = {**conn, "concurrency": 4}

    parse_worker = Worker(QUEUE_PARSE, handle_parse, {**ingestion_opts})
    chunk_worker = Worker(QUEUE_CHUNK, handle_chunk, {**ingestion_opts})
    embed_worker = Worker(QUEUE_EMBED, handle_embed, {**ingestion_opts})
    index_worker = Worker(QUEUE_INDEX, handle_index, {**ingestion_opts})
    validate_worker = Worker(QUEUE_VALIDATE, handle_validate, {**ingestion_opts})

    for w in (parse_worker, chunk_worker, embed_worker, index_worker, validate_worker):
        w.on("failed", _on_failed_ingestion)

    memory_summarize_worker = Worker(
        QUEUE_MEMORY_SUMMARIZE, handle_memory_summarize, {**conn, "concurrency": 3}
    )
    memory_prune_worker = Worker(
        QUEUE_MEMORY_PRUNE, handle_memory_prune, {**conn, "concurrency": 1}
    )

    return [
        parse_worker,
        chunk_worker,
        embed_worker,
        index_worker,
        validate_worker,
        memory_summarize_worker,
        memory_prune_worker,
    ]
