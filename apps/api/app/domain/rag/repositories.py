"""Tenant-scoped repository protocols for the RAG knowledge catalog.

All methods are async and operate on domain entities from ``catalog.py`` and
``profiles.py``. Every read and write MUST receive a ``tenant_id`` to scope the
operation; tenant-neutral catalog access for tenant-owned content is
prohibited. Protocols define only the persistence contract — concrete
SQLAlchemy implementations live in infrastructure.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.domain.rag.memory import MemoryChunk, MemoryConfig

from app.domain.models import Project
from app.domain.rag.catalog import (
    Chunk,
    DecompositionConfig,
    Document,
    DocumentVersion,
    IndexGeneration,
    IngestionJob,
    KnowledgeBase,
    KnowledgeSource,
    OutboxEvent,
    PlannerConfig,
    StageCheckpoint,
)
from app.domain.rag.profiles import IndexProfile, ModelProfile, RetrievalConfig


class KnowledgeBaseRepository(Protocol):
    async def find_by_id(self, *, tenant_id: str, knowledge_base_id: str) -> KnowledgeBase | None: ...
    async def find_by_slug(self, *, tenant_id: str, slug: str) -> KnowledgeBase | None: ...
    async def create(self, *, tenant_id: str, slug: str, name: str, status: str, project_id: str | None = None) -> KnowledgeBase: ...
    async def list_by_tenant(self, *, tenant_id: str) -> list[KnowledgeBase]: ...
    async def archive(self, *, tenant_id: str, knowledge_base_id: str) -> KnowledgeBase | None: ...


class ProjectRepository(Protocol):
    async def find_by_id(self, *, tenant_id: str, project_id: str) -> Project | None: ...
    async def find_by_slug(self, *, tenant_id: str, slug: str) -> Project | None: ...
    async def find_default(self, *, tenant_id: str) -> Project | None: ...
    async def create(self, *, tenant_id: str, slug: str, name: str, is_default: bool = False) -> Project: ...
    async def list_by_tenant(self, *, tenant_id: str) -> list[Project]: ...
    async def archive(self, *, tenant_id: str, project_id: str) -> Project | None: ...
    async def update(self, *, tenant_id: str, project_id: str, name: str, slug: str) -> Project | None: ...
    async def list_knowledge_bases(self, *, tenant_id: str, project_id: str) -> list[KnowledgeBase]: ...
    async def move_knowledge_base(self, *, tenant_id: str, project_id: str, knowledge_base_id: str) -> KnowledgeBase | None: ...
    async def resolve_project_for_knowledge_bases(self, *, tenant_id: str, knowledge_base_ids: tuple[str, ...]) -> Project | None: ...


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
    async def create(self, *, tenant_id: str, knowledge_base_id: str, source_id: str, title: str | None) -> Document: ...


class DocumentVersionRepository(Protocol):
    async def find_by_id(self, *, tenant_id: str, version_id: str) -> DocumentVersion | None: ...
    async def list_by_knowledge_base(self, *, tenant_id: str, knowledge_base_id: str) -> list[tuple[DocumentVersion, str, str]]: ...
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
        classification: str = "INTERNAL",
        acl_principals: tuple[str, ...] = (),
    ) -> DocumentVersion: ...
    async def update_lifecycle_state(self, *, tenant_id: str, version_id: str, lifecycle_state: str) -> DocumentVersion | None: ...


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
    async def find_active(self, *, tenant_id: str) -> IndexProfile | None: ...
    async def create(
        self,
        *,
        tenant_id: str,
        name: str,
        embedding_profile_id: str,
        sparse_profile_id: str | None,
        reranker_profile_id: str | None = None,
        collection: str,
        dimensions: int,
        distance_metric: str,
        chunking_strategy: str = "RECURSIVE",
        chunk_size_tokens: int = 400,
        chunk_overlap_tokens: int = 50,
        parent_chunk_size: int = 1500,
        version: str,
        is_active: bool = False,
    ) -> IndexProfile: ...
    async def set_active(self, *, tenant_id: str, profile_id: str) -> IndexProfile | None: ...
    async def activate(self, *, tenant_id: str, profile_id: str) -> IndexProfile | None: ...


class RetrievalConfigRepository(Protocol):
    async def find_by_profile(self, *, tenant_id: str, index_profile_id: str) -> RetrievalConfig | None: ...
    async def upsert(
        self,
        *,
        tenant_id: str,
        index_profile_id: str,
        dense_weight: float,
        sparse_weight: float,
        fusion_k: int,
        dense_candidates: int,
        sparse_candidates: int,
        fused_candidates: int,
        enabled: bool,
    ) -> RetrievalConfig: ...
    async def delete(self, *, tenant_id: str, index_profile_id: str) -> bool: ...


class IndexGenerationRepository(Protocol):
    async def find_by_id(self, *, tenant_id: str, generation_id: str) -> IndexGeneration | None: ...
    async def find_active_for_version(self, *, tenant_id: str, document_version_id: str) -> IndexGeneration | None: ...
    async def list_for_version(self, *, tenant_id: str, document_version_id: str) -> list[IndexGeneration]: ...
    async def find_active_for_knowledge_bases(self, *, tenant_id: str, knowledge_base_ids: tuple[str, ...]) -> list[IndexGeneration]: ...
    async def create(
        self,
        *,
        tenant_id: str,
        document_version_id: str,
        index_profile_id: str,
        status: str,
    ) -> IndexGeneration: ...
    async def update_status(self, *, tenant_id: str, generation_id: str, status: str) -> IndexGeneration | None: ...


class IngestionJobRepository(Protocol):
    async def find_by_idempotency_key(self, *, tenant_id: str, idempotency_key: str) -> IngestionJob | None: ...
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
    async def find_by_generation(self, *, tenant_id: str, generation_id: str) -> list[Chunk]: ...
    async def find_by_ids(self, *, tenant_id: str, chunk_ids: tuple[str, ...]) -> list[Chunk]: ...
    async def create_many(self, *, tenant_id: str, chunks: list[dict[str, object]]) -> int: ...
    async def delete_by_generation(self, *, tenant_id: str, generation_id: str) -> None: ...


class StageCheckpointRepository(Protocol):
    async def find_by_stage(self, *, tenant_id: str, document_version_id: str, stage: str) -> StageCheckpoint | None: ...
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


class DecompositionConfigRepository(Protocol):
    async def find_by_knowledge_base(self, *, tenant_id: str, knowledge_base_id: str) -> DecompositionConfig | None: ...
    async def find_by_project(self, *, tenant_id: str, project_id: str) -> DecompositionConfig | None: ...
    async def upsert(
        self,
        *,
        tenant_id: str,
        knowledge_base_id: str,
        enabled: bool,
        model_profile_id: str,
        system_prompt: str,
        user_prompt_template: str,
        max_sub_queries: int,
        max_depth: int,
        min_complexity_score: float,
        guardrails: dict[str, object],
    ) -> DecompositionConfig: ...
    async def delete(self, *, tenant_id: str, knowledge_base_id: str) -> bool: ...
    async def upsert_for_project(
        self,
        *,
        tenant_id: str,
        project_id: str,
        enabled: bool,
        model_profile_id: str,
        system_prompt: str,
        user_prompt_template: str,
        max_sub_queries: int,
        max_depth: int,
        min_complexity_score: float,
        guardrails: dict[str, object],
    ) -> DecompositionConfig: ...
    async def delete_for_project(self, *, tenant_id: str, project_id: str) -> bool: ...


class PlannerConfigRepository(Protocol):
    async def find_by_knowledge_base(self, *, tenant_id: str, knowledge_base_id: str) -> PlannerConfig | None: ...
    async def find_by_project(self, *, tenant_id: str, project_id: str) -> PlannerConfig | None: ...
    async def upsert(
        self,
        *,
        tenant_id: str,
        knowledge_base_id: str,
        enabled: bool,
        model_profile_id: str,
        system_prompt: str,
        user_prompt_template: str,
        max_tasks: int,
        task_timeout_seconds: int,
        task_types: tuple[str, ...],
        mcp_enabled: bool,
        guardrails: dict[str, object],
    ) -> PlannerConfig: ...
    async def delete(self, *, tenant_id: str, knowledge_base_id: str) -> bool: ...
    async def upsert_for_project(
        self,
        *,
        tenant_id: str,
        project_id: str,
        enabled: bool,
        model_profile_id: str,
        system_prompt: str,
        user_prompt_template: str,
        max_tasks: int,
        task_timeout_seconds: int,
        task_types: tuple[str, ...],
        mcp_enabled: bool,
        guardrails: dict[str, object],
    ) -> PlannerConfig: ...
    async def delete_for_project(self, *, tenant_id: str, project_id: str) -> bool: ...


class MemoryConfigRepository(Protocol):
    async def find_by_knowledge_base(self, *, tenant_id: str, knowledge_base_id: str) -> "MemoryConfig | None": ...
    async def find_by_project(self, *, tenant_id: str, project_id: str) -> "MemoryConfig | None": ...
    async def upsert(
        self,
        *,
        tenant_id: str,
        knowledge_base_id: str,
        enabled: bool,
        summarization_model_profile_id: str,
        embedding_profile_id: str,
        retention_days: int,
        retrieval_top_k: int,
        min_turns_to_summarize: int,
        system_prompt: str,
    ) -> "MemoryConfig": ...
    async def delete(self, *, tenant_id: str, knowledge_base_id: str) -> bool: ...
    async def upsert_for_project(
        self,
        *,
        tenant_id: str,
        project_id: str,
        enabled: bool,
        summarization_model_profile_id: str,
        embedding_profile_id: str,
        retention_days: int,
        retrieval_top_k: int,
        min_turns_to_summarize: int,
        system_prompt: str,
    ) -> "MemoryConfig": ...
    async def delete_for_project(self, *, tenant_id: str, project_id: str) -> bool: ...


class MemoryChunkRepository(Protocol):
    async def find_by_user_kb(
        self,
        *,
        tenant_id: str,
        knowledge_base_id: str,
        user_id: str,
        page: int,
        page_size: int,
    ) -> "list[MemoryChunk]": ...
    async def count_by_user_kb(self, *, tenant_id: str, knowledge_base_id: str, user_id: str) -> int: ...
    async def find_expired(self, *, limit: int) -> "list[MemoryChunk]": ...
    async def create(
        self,
        *,
        tenant_id: str,
        knowledge_base_id: str,
        user_id: str,
        conversation_id: str,
        summary: str,
        qdrant_point_id: str,
        embedding_profile_id: str,
        turn_count: int,
        expires_at: "datetime",
    ) -> "MemoryChunk": ...
    async def delete(self, *, tenant_id: str, chunk_id: str, user_id: str) -> bool: ...
    async def delete_by_user_kb(self, *, tenant_id: str, knowledge_base_id: str, user_id: str) -> int: ...
    async def delete_by_knowledge_base(self, *, tenant_id: str, knowledge_base_id: str) -> int: ...
    async def delete_many(self, *, chunk_ids: list[str]) -> None: ...
    async def is_conversation_summarized(self, *, conversation_id: str) -> bool: ...
    async def find_by_id(self, *, tenant_id: str, chunk_id: str) -> "MemoryChunk | None": ...
