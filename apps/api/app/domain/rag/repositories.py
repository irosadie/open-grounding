"""Tenant-scoped repository protocols for the RAG knowledge catalog.

All methods are async and operate on domain entities from ``catalog.py`` and
``profiles.py``. Every read and write MUST receive a ``tenant_id`` to scope the
operation; tenant-neutral catalog access for tenant-owned content is
prohibited. Protocols define only the persistence contract — concrete
SQLAlchemy implementations live in infrastructure.
"""

from typing import Protocol

from app.domain.rag.catalog import (
    Chunk,
    Document,
    DocumentVersion,
    IndexGeneration,
    IngestionJob,
    KnowledgeBase,
    KnowledgeSource,
    OutboxEvent,
    StageCheckpoint,
)
from app.domain.rag.profiles import IndexProfile, ModelProfile


class KnowledgeBaseRepository(Protocol):
    async def find_by_id(self, *, tenant_id: str, knowledge_base_id: str) -> KnowledgeBase | None: ...
    async def create(
        self, *, tenant_id: str, slug: str, name: str, status: str
    ) -> KnowledgeBase: ...


class KnowledgeSourceRepository(Protocol):
    async def create(
        self,
        *,
        tenant_id: str,
        knowledge_base_id: str,
        source_type: str,
        name: str,
        config_ref: str | None,
    ) -> KnowledgeSource: ...


class DocumentRepository(Protocol):
    async def find_by_id(self, *, tenant_id: str, document_id: str) -> Document | None: ...
    async def create(
        self, *, tenant_id: str, knowledge_base_id: str, source_id: str, title: str | None
    ) -> Document: ...


class DocumentVersionRepository(Protocol):
    async def find_by_id(self, *, tenant_id: str, version_id: str) -> DocumentVersion | None: ...
    async def create(
        self,
        *,
        tenant_id: str,
        document_id: str,
        version_number: int,
        content_checksum: str,
        object_key_raw: str,
        source_revision: str | None,
        pipeline_fingerprint: str | None,
        size_bytes: int | None,
        mime_type: str | None,
    ) -> DocumentVersion: ...
    async def update_lifecycle_state(
        self, *, tenant_id: str, version_id: str, lifecycle_state: str
    ) -> DocumentVersion | None: ...


class ModelProfileRepository(Protocol):
    async def find_by_id(self, *, tenant_id: str, profile_id: str) -> ModelProfile | None: ...
    async def create(
        self,
        *,
        tenant_id: str,
        profile_kind: str,
        provider: str,
        model: str,
        dimensions: int | None,
        version: str,
    ) -> ModelProfile: ...


class IndexProfileRepository(Protocol):
    async def find_by_id(self, *, tenant_id: str, profile_id: str) -> IndexProfile | None: ...
    async def create(
        self,
        *,
        tenant_id: str,
        embedding_profile_id: str,
        sparse_profile_id: str | None,
        collection: str,
        dimensions: int,
        distance_metric: str,
        version: str,
    ) -> IndexProfile: ...


class IndexGenerationRepository(Protocol):
    async def find_by_id(self, *, tenant_id: str, generation_id: str) -> IndexGeneration | None: ...
    async def find_active_for_version(
        self, *, tenant_id: str, document_version_id: str
    ) -> IndexGeneration | None: ...
    async def create(
        self,
        *,
        tenant_id: str,
        document_version_id: str,
        index_profile_id: str,
        status: str,
    ) -> IndexGeneration: ...
    async def update_status(
        self, *, tenant_id: str, generation_id: str, status: str
    ) -> IndexGeneration | None: ...


class IngestionJobRepository(Protocol):
    async def find_by_idempotency_key(
        self, *, tenant_id: str, idempotency_key: str
    ) -> IngestionJob | None: ...
    async def create(
        self,
        *,
        tenant_id: str,
        document_version_id: str,
        generation_id: str | None,
        stage: str,
        idempotency_key: str,
        trace_id: str | None,
    ) -> IngestionJob: ...


class OutboxEventRepository(Protocol):
    async def create(
        self,
        *,
        tenant_id: str,
        event_type: str,
        resource_id: str | None,
        generation_id: str | None,
        idempotency_key: str,
        trace_id: str | None,
        payload: dict[str, object],
    ) -> OutboxEvent: ...
    async def find_pending(self, *, tenant_id: str, limit: int) -> list[OutboxEvent]: ...
    async def mark_dispatched(self, *, tenant_id: str, event_id: str) -> None: ...


class ChunkRepository(Protocol):
    async def find_by_generation(
        self, *, tenant_id: str, generation_id: str
    ) -> list[Chunk]: ...
    async def create_many(
        self, *, tenant_id: str, chunks: list[dict[str, object]]
    ) -> int: ...
    async def delete_by_generation(self, *, tenant_id: str, generation_id: str) -> None: ...


class StageCheckpointRepository(Protocol):
    async def find_by_stage(
        self, *, tenant_id: str, document_version_id: str, stage: str
    ) -> StageCheckpoint | None: ...
    async def upsert(
        self,
        *,
        tenant_id: str,
        document_version_id: str,
        generation_id: str | None,
        stage: str,
        status: str,
        attempts: int,
        idempotency_key: str,
        trace_id: str | None,
        checkpoint_data: dict[str, object],
    ) -> StageCheckpoint: ...

