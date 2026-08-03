"""Pending index-generation and transactional outbox application service.

Creates a pending index generation and its outbox event in ONE PostgreSQL
transaction so a dispatcher can process only committed events with stable
idempotency and trace context. The generation becomes active only after
downstream validation succeeds; a failed generation never replaces the active
one.

This service does NOT dispatch parser, embedding, or retrieval work. It owns
only the atomic catalog state transition; derived side effects are reconciled
from the catalog by a future ingestion worker.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.rag.catalog import IndexGeneration, OutboxEvent
from app.infrastructure.rag_catalog import (
    SqlAlchemyIndexGenerationRepository,
    SqlAlchemyOutboxEventRepository,
)


@dataclass(frozen=True)
class PendingPublication:
    """Result of creating a pending generation plus outbox event atomically."""

    generation: IndexGeneration
    outbox_event: OutboxEvent


class RagPublicationService:
    """Owns the atomic pending-generation + outbox transition.

    Both records are committed in the same session transaction. If either
    fails, neither is persisted, so a dispatcher never observes a generation
    without its event or vice versa.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._generations = SqlAlchemyIndexGenerationRepository(session)
        self._outbox = SqlAlchemyOutboxEventRepository(session)

    async def create_pending_publication(
        self,
        *,
        tenant_id: str,
        document_version_id: str,
        index_profile_id: str,
        trace_id: str | None,
    ) -> PendingPublication:
        """Create a pending index generation and its outbox event in one transaction.

        The generation starts as PENDING and the outbox event as PENDING. A
        future dispatcher processes only the committed event. This method does
        not perform any derived-store work.
        """

        generation = await self._generations.create(
            tenant_id=tenant_id,
            document_version_id=document_version_id,
            index_profile_id=index_profile_id,
            status="PENDING",
        )
        idempotency_key = f"publication:{tenant_id}:{generation.id}"
        outbox_event = await self._outbox.create(
            tenant_id=tenant_id,
            event_type="GENERATION_PUBLISHED",
            resource_id=document_version_id,
            generation_id=generation.id,
            idempotency_key=idempotency_key,
            trace_id=trace_id,
            payload={
                "tenantId": tenant_id,
                "documentVersionId": document_version_id,
                "generationId": generation.id,
                "indexProfileId": index_profile_id,
            },
        )
        return PendingPublication(generation=generation, outbox_event=outbox_event)

    async def promote_generation(
        self, *, tenant_id: str, generation_id: str
    ) -> IndexGeneration | None:
        """Promote a validated generation to ACTIVE.

        The prior active generation (if any) is superseded by the caller, not
        mutated in place. This method only flips the target generation; the
        caller is responsible for validating derived state first.
        """
        return await self._generations.update_status(
            tenant_id=tenant_id, generation_id=generation_id, status="ACTIVE"
        )

    async def fail_generation(
        self, *, tenant_id: str, generation_id: str
    ) -> IndexGeneration | None:
        """Mark a generation FAILED without affecting the active generation."""
        return await self._generations.update_status(
            tenant_id=tenant_id, generation_id=generation_id, status="FAILED"
        )

    @staticmethod
    def new_idempotency_key(tenant_id: str, generation_id: str) -> str:
        return f"publication:{tenant_id}:{generation_id}"

    @staticmethod
    def new_trace_id() -> str:
        from uuid import uuid4

        return str(uuid4())
