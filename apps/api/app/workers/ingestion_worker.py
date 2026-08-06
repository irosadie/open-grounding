"""Ingestion pipeline worker — consumes BullMQ jobs from Redis.

Reads jobs from BullMQ queue format (Redis streams/lists).
Processes: parse → chunk → embed → index → validate.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.infrastructure.database import create_session_factory
from app.workers.stages.chunk import chunk_document
from app.workers.stages.embed import embed_chunks
from app.workers.stages.index import index_chunks
from app.workers.stages.memory_prune import prune_expired_memory
from app.workers.stages.memory_summarize import summarize_conversation
from app.workers.stages.parse import parse_document
from app.workers.stages.validate import validate_and_finalize

logger = logging.getLogger(__name__)

QUEUE_PARSE = "ingestion.parse"
QUEUE_CHUNK = "ingestion.chunk"
QUEUE_EMBED = "ingestion.embed"
QUEUE_INDEX = "ingestion.index"
QUEUE_VALIDATE = "ingestion.validate"
QUEUE_MEMORY_SUMMARIZE = "memory.summarize"
QUEUE_MEMORY_PRUNE = "memory.prune"

POLL_INTERVAL = 2  # seconds
MEMORY_PRUNE_INTERVAL = 24 * 60 * 60  # 24 hours


@dataclass
class IngestionJob:
    document_version_id: str
    tenant_id: str
    knowledge_base_id: str | None = None
    user_id: str | None = None


class IngestionWorker:
    def __init__(self, settings: Settings, redis_url: str) -> None:
        self._settings = settings
        self._redis_url = redis_url
        self._running = False
        self._session_factory = create_session_factory(settings)
        self._last_prune_at = 0.0

    async def start(self) -> None:
        self._running = True
        self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
        logger.info("Ingestion worker started. Listening on queues: parse, chunk, embed, index, validate, memory.summarize, memory.prune")

        while self._running:
            await self._poll_queues()
            await self._maybe_run_prune()
            await asyncio.sleep(POLL_INTERVAL)

    async def stop(self) -> None:
        self._running = False
        if self._redis:
            await self._redis.aclose()
        logger.info("Ingestion worker stopped")

    async def _maybe_run_prune(self) -> None:
        """Run memory prune daily (not more than once per interval)."""
        import time
        now = time.monotonic()
        if now - self._last_prune_at < MEMORY_PRUNE_INTERVAL:
            return
        self._last_prune_at = now
        logger.info("Running scheduled memory.prune (daily)")
        try:
            async with self._session_factory() as session:
                await prune_expired_memory(
                    session=session,
                    settings=self._settings,
                )
        except Exception as e:
            logger.warning("Scheduled memory.prune failed: %s", e)

    async def _poll_queues(self) -> None:
        """Poll all ingestion queues in priority order."""
        for queue_name, handler in [
            (QUEUE_PARSE, self._handle_parse),
            (QUEUE_CHUNK, self._handle_chunk),
            (QUEUE_EMBED, self._handle_embed),
            (QUEUE_INDEX, self._handle_index),
            (QUEUE_VALIDATE, self._handle_validate),
            (QUEUE_MEMORY_SUMMARIZE, self._handle_memory_summarize),
            (QUEUE_MEMORY_PRUNE, self._handle_memory_prune),
        ]:
            job = await self._dequeue(queue_name)
            if job:
                async with self._session_factory() as session:
                    await handler(job, session)

    async def _dequeue(self, queue_name: str) -> IngestionJob | None:
        """Dequeue one job from BullMQ wait list (RPOPLPUSH pattern)."""
        key = f"bull:{queue_name}:wait"
        job_id = await self._redis.rpoplpush(key, f"bull:{queue_name}:active")
        if not job_id:
            return None
        job_key = f"bull:{queue_name}:{job_id}"
        data_raw = await self._redis.hget(job_key, "data")
        if not data_raw:
            return None
        try:
            data = json.loads(data_raw)
            return IngestionJob(
                document_version_id=data.get("documentVersionId", ""),
                tenant_id=data["tenantId"],
                knowledge_base_id=data.get("knowledgeBaseId"),
                user_id=data.get("userId"),
            )
        except (KeyError, json.JSONDecodeError) as e:
            logger.error("Failed to parse job data from %s: %s", queue_name, e)
            return None

    async def _ack(self, queue_name: str, job_id: str) -> None:
        """Remove job from active list after successful processing."""
        key = f"bull:{queue_name}:active"
        await self._redis.lrem(key, 1, job_id)

    async def _enqueue_next(self, queue_name: str, job: IngestionJob) -> None:
        """Enqueue job to next stage queue."""
        key = f"bull:{queue_name}:wait"
        job_id = f"auto:{job.document_version_id}"
        job_key = f"bull:{queue_name}:{job_id}"
        data = json.dumps({
            "documentVersionId": job.document_version_id,
            "tenantId": job.tenant_id,
            "knowledgeBaseId": job.knowledge_base_id,
            "userId": job.user_id,
        })
        await self._redis.hset(job_key, "data", data)
        await self._redis.lpush(key, job_id)

    async def _handle_parse(self, job: IngestionJob, session: AsyncSession) -> None:
        logger.info("[parse] %s", job.document_version_id)
        try:
            await parse_document(job.document_version_id, job.tenant_id, session, self._settings)
            await self._enqueue_next(QUEUE_CHUNK, job)
            await self._ack(QUEUE_PARSE, job.document_version_id)
        except Exception as e:
            logger.error("[parse] FAILED %s: %s", job.document_version_id, e)
            await self._mark_failed(job.document_version_id, job.tenant_id, session)

    async def _handle_chunk(self, job: IngestionJob, session: AsyncSession) -> None:
        logger.info("[chunk] %s", job.document_version_id)
        try:
            await chunk_document(job.document_version_id, job.tenant_id, session, self._settings)
            await self._enqueue_next(QUEUE_EMBED, job)
            await self._ack(QUEUE_CHUNK, job.document_version_id)
        except Exception as e:
            logger.error("[chunk] FAILED %s: %s", job.document_version_id, e)
            await self._mark_failed(job.document_version_id, job.tenant_id, session)

    async def _handle_embed(self, job: IngestionJob, session: AsyncSession) -> None:
        logger.info("[embed] %s", job.document_version_id)
        try:
            await embed_chunks(job.document_version_id, job.tenant_id, session, self._settings)
            await self._enqueue_next(QUEUE_INDEX, job)
            await self._ack(QUEUE_EMBED, job.document_version_id)
        except Exception as e:
            logger.error("[embed] FAILED %s: %s", job.document_version_id, e)
            await self._mark_failed(job.document_version_id, job.tenant_id, session)

    async def _handle_index(self, job: IngestionJob, session: AsyncSession) -> None:
        logger.info("[index] %s", job.document_version_id)
        try:
            await index_chunks(job.document_version_id, job.tenant_id, session, self._settings)
            await self._enqueue_next(QUEUE_VALIDATE, job)
            await self._ack(QUEUE_INDEX, job.document_version_id)
        except Exception as e:
            logger.error("[index] FAILED %s: %s", job.document_version_id, e)
            await self._mark_failed(job.document_version_id, job.tenant_id, session)

    async def _handle_validate(self, job: IngestionJob, session: AsyncSession) -> None:
        logger.info("[validate] %s", job.document_version_id)
        try:
            await validate_and_finalize(job.document_version_id, job.tenant_id, session, self._settings)
            await self._ack(QUEUE_VALIDATE, job.document_version_id)
        except Exception as e:
            logger.error("[validate] FAILED %s: %s", job.document_version_id, e)
            await self._mark_failed(job.document_version_id, job.tenant_id, session)

    async def _handle_memory_summarize(self, job: IngestionJob, session: AsyncSession) -> None:
        """Handle memory.summarize job. document_version_id carries conversation_id."""
        conversation_id = job.document_version_id
        knowledge_base_id = job.knowledge_base_id or ""
        user_id = job.user_id or ""
        logger.info("[memory.summarize] conversation=%s kb=%s", conversation_id, knowledge_base_id)
        try:
            await summarize_conversation(
                conversation_id=conversation_id,
                tenant_id=job.tenant_id,
                knowledge_base_id=knowledge_base_id,
                user_id=user_id,
                session=session,
                settings=self._settings,
            )
            await self._ack(QUEUE_MEMORY_SUMMARIZE, conversation_id)
        except Exception as e:
            logger.error("[memory.summarize] FAILED conversation=%s: %s", conversation_id, e)
            await self._ack(QUEUE_MEMORY_SUMMARIZE, conversation_id)

    async def enqueue_memory_summarize(
        self,
        *,
        conversation_id: str,
        tenant_id: str,
        knowledge_base_id: str,
        user_id: str,
    ) -> None:
        """Enqueue a memory.summarize job for a completed conversation."""
        queue_name = QUEUE_MEMORY_SUMMARIZE
        job_id = f"mem:{conversation_id}"
        job_key = f"bull:{queue_name}:{job_id}"
        data = json.dumps({
            "documentVersionId": conversation_id,
            "tenantId": tenant_id,
            "knowledgeBaseId": knowledge_base_id,
            "userId": user_id,
        })
        await self._redis.hset(job_key, "data", data)
        await self._redis.lpush(f"bull:{queue_name}:wait", job_id)

    async def _handle_memory_prune(self, job: IngestionJob, session: AsyncSession) -> None:
        logger.info("[memory.prune] running batch prune")
        try:
            deleted = await prune_expired_memory(session=session, settings=self._settings)
            logger.info("[memory.prune] deleted %d chunks", deleted)
            await self._ack(QUEUE_MEMORY_PRUNE, job.document_version_id)
        except Exception as e:
            logger.error("[memory.prune] FAILED: %s", e)
            await self._ack(QUEUE_MEMORY_PRUNE, job.document_version_id)

    async def _mark_failed(self, document_version_id: str, tenant_id: str, session: AsyncSession) -> None:
        from app.infrastructure.rag_catalog import SqlAlchemyDocumentVersionRepository
        repo = SqlAlchemyDocumentVersionRepository(session)
        await repo.update_lifecycle_state(
            tenant_id=tenant_id,
            version_id=document_version_id,
            lifecycle_state="FAILED",
        )
