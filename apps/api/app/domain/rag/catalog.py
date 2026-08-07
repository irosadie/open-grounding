"""Tenant-scoped RAG knowledge-catalog domain entities.

These frozen dataclasses are the domain model for the knowledge lifecycle:
knowledge bases, sources, documents, document versions, index generations,
ingestion jobs, and outbox events. Model and index profiles are reused from
``profiles.py`` so the provider ports and the catalog share one type.

All entities carry a non-null ``tenant_id`` supplied by the prerequisite
tenant foundation. The catalog is authoritative for identity, lifecycle, and
audit even when Qdrant or object storage is unavailable. Document identity is
stable and distinct from immutable document versions; derived index
generations are versioned and never overwrite an active generation in place.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.rag.policy import Classification


class KnowledgeBaseStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class KnowledgeSourceType(StrEnum):
    UPLOAD = "UPLOAD"
    CONNECTOR = "CONNECTOR"


class DocumentVersionLifecycleState(StrEnum):
    RECEIVED = "RECEIVED"
    STORED = "STORED"
    QUEUED = "QUEUED"
    PARSING = "PARSING"
    NORMALIZING = "NORMALIZING"
    CLASSIFYING = "CLASSIFYING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    INDEXING = "INDEXING"
    VALIDATING = "VALIDATING"
    READY = "READY"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"
    DELETING = "DELETING"
    DELETED = "DELETED"


class IndexGenerationStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"
    DELETING = "DELETING"
    DELETED = "DELETED"


class IngestionJobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class OutboxEventStatus(StrEnum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class KnowledgeBase:
    id: str
    tenant_id: str
    slug: str
    name: str
    status: KnowledgeBaseStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class KnowledgeSource:
    id: str
    tenant_id: str
    knowledge_base_id: str
    source_type: KnowledgeSourceType
    name: str
    config_ref: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Document:
    id: str
    tenant_id: str
    knowledge_base_id: str
    source_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class DocumentVersion:
    id: str
    tenant_id: str
    document_id: str
    version_number: int
    lifecycle_state: DocumentVersionLifecycleState
    content_checksum: str
    source_revision: str | None
    pipeline_fingerprint: str | None
    parsed_text: str | None
    object_key_raw: str
    size_bytes: int | None
    mime_type: str | None
    classification: Classification
    acl_principals: tuple[str, ...]
    effective_from: datetime | None
    effective_to: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class IndexGeneration:
    id: str
    tenant_id: str
    document_version_id: str
    index_profile_id: str
    status: IndexGenerationStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class IngestionJob:
    id: str
    tenant_id: str
    document_version_id: str
    generation_id: str | None
    stage: str
    attempts: int
    idempotency_key: str
    trace_id: str | None
    status: IngestionJobStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class OutboxEvent:
    id: str
    tenant_id: str
    event_type: str
    resource_id: str | None
    generation_id: str | None
    idempotency_key: str
    trace_id: str | None
    payload: dict[str, object]
    status: OutboxEventStatus
    created_at: datetime
    dispatched_at: datetime | None


class ChunkType(StrEnum):
    PARENT = "PARENT"
    CHILD = "CHILD"


class StageCheckpointStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class Chunk:
    """A parent or child retrieval unit with source lineage."""

    id: str
    tenant_id: str
    document_version_id: str
    generation_id: str
    parent_id: str | None
    chunk_type: ChunkType
    hierarchy_path: tuple[str, ...]
    page: int | None
    content_type: str
    text: str
    token_count: int
    source_offsets_start: int | None
    source_offsets_end: int | None
    chunker_version: str
    created_at: datetime


@dataclass(frozen=True)
class StageCheckpoint:
    """A resumable pipeline stage checkpoint with recovery metadata."""

    id: str
    tenant_id: str
    document_version_id: str
    generation_id: str | None
    stage: str
    status: StageCheckpointStatus
    attempts: int
    idempotency_key: str
    trace_id: str | None
    checkpoint_data: dict[str, object]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class DecompositionConfig:
    """Per-KB configuration for hybrid query decomposition."""

    id: str
    tenant_id: str
    knowledge_base_id: str
    enabled: bool
    model_profile_id: str
    system_prompt: str
    user_prompt_template: str
    max_sub_queries: int
    max_depth: int
    min_complexity_score: float
    guardrails: dict[str, object]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class PlannerConfig:
    """Per-KB configuration for typed query planning."""

    id: str
    tenant_id: str
    knowledge_base_id: str
    enabled: bool
    model_profile_id: str
    system_prompt: str
    user_prompt_template: str
    max_tasks: int
    task_timeout_seconds: int
    task_types: tuple[str, ...]
    mcp_enabled: bool
    guardrails: dict[str, object]
    created_at: datetime
    updated_at: datetime
