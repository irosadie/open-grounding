"""SQLAlchemy ORM records and repositories for the RAG knowledge catalog.

All records carry a non-null ``tenant_id`` foreign key to ``tenants.id`` and
use tenant-local uniqueness constraints so catalog relationships cannot cross
tenant boundaries. Repositories map ORM records to domain entities and never
return raw records. Imports SQLAlchemy only; domain code never imports this
module's types.
"""

from datetime import datetime
from typing import cast
from uuid import uuid4

from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.rag.catalog import (
    Chunk,
    ChunkType,
    DecompositionConfig,
    PlannerConfig,
    Document,
    DocumentVersion,
    DocumentVersionLifecycleState,
    IndexGeneration,
    IndexGenerationStatus,
    IngestionJob,
    IngestionJobStatus,
    KnowledgeBase,
    KnowledgeBaseStatus,
    KnowledgeSource,
    KnowledgeSourceType,
    OutboxEvent,
    OutboxEventStatus,
    StageCheckpoint,
    StageCheckpointStatus,
)
from app.domain.rag.confidence import CalibrationFixture, CalibrationFixtureEntry, CalibrationModelVersion, CalibrationSource, ConfidenceConfig, ConfidenceLabel
from app.domain.rag.policy import Classification
from app.domain.rag.profiles import IndexProfile, ModelProfile, RetrievalConfig
from app.domain.mcp.entities import McpInvocation, McpServer, McpTool, McpToolDescriptor
from app.domain.mcp.enums import McpInvocationStatus, McpServerStatus, McpTransport
from app.infrastructure.database import Base, utc_now


def _tenant_fk() -> ForeignKey:
    """Return a fresh tenant FK. ForeignKey objects cannot be shared across columns."""
    return ForeignKey("tenants.id", ondelete="CASCADE")


class KnowledgeBaseRecord(Base):
    __tablename__ = "rag_knowledge_bases"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[KnowledgeBaseStatus] = mapped_column(
        Enum(KnowledgeBaseStatus, name="KnowledgeBaseStatus"),
        default=KnowledgeBaseStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)
    __table_args__ = ()


class KnowledgeSourceRecord(Base):
    __tablename__ = "rag_knowledge_sources"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column("knowledge_base_id", Uuid(as_uuid=False), ForeignKey("rag_knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[KnowledgeSourceType] = mapped_column(Enum(KnowledgeSourceType, name="KnowledgeSourceType"), default=KnowledgeSourceType.UPLOAD, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class DocumentRecord(Base):
    __tablename__ = "rag_documents"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column("knowledge_base_id", Uuid(as_uuid=False), ForeignKey("rag_knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[str] = mapped_column("source_id", Uuid(as_uuid=False), ForeignKey("rag_knowledge_sources.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class DocumentVersionRecord(Base):
    __tablename__ = "rag_document_versions"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    document_id: Mapped[str] = mapped_column("document_id", Uuid(as_uuid=False), ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_state: Mapped[DocumentVersionLifecycleState] = mapped_column(
        Enum(DocumentVersionLifecycleState, name="DocumentVersionLifecycleState"),
        default=DocumentVersionLifecycleState.RECEIVED,
        nullable=False,
    )
    content_checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    source_revision: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pipeline_fingerprint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    parsed_text: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    object_key_raw: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    classification: Mapped[Classification] = mapped_column(
        Enum(Classification, name="Classification"), default=Classification.INTERNAL, nullable=False
    )
    acl_principals: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class ModelProfileRecord(Base):
    __tablename__ = "rag_model_profiles"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    modality: Mapped[str] = mapped_column(String(60), nullable=False, default="TEXT")
    dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    config_json: Mapped[str | None] = mapped_column(String, nullable=True)
    version: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class IndexProfileRecord(Base):
    __tablename__ = "rag_index_profiles"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_profile_id: Mapped[str] = mapped_column("embedding_profile_id", Uuid(as_uuid=False), ForeignKey("rag_model_profiles.id", ondelete="RESTRICT"), nullable=False)
    sparse_profile_id: Mapped[str | None] = mapped_column("sparse_profile_id", Uuid(as_uuid=False), ForeignKey("rag_model_profiles.id", ondelete="RESTRICT"), nullable=True)
    reranker_profile_id: Mapped[str | None] = mapped_column("reranker_profile_id", Uuid(as_uuid=False), ForeignKey("rag_model_profiles.id", ondelete="RESTRICT"), nullable=True)
    collection: Mapped[str] = mapped_column(String(255), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_metric: Mapped[str] = mapped_column(String(50), nullable=False)
    chunking_strategy: Mapped[str] = mapped_column(String(60), nullable=False, default="RECURSIVE")
    chunk_size_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=400)
    chunk_overlap_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    parent_chunk_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1500)
    version: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class RetrievalConfigRecord(Base):
    __tablename__ = "rag_retrieval_configs"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    index_profile_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("rag_index_profiles.id", ondelete="CASCADE"), nullable=False
    )
    dense_weight: Mapped[float] = mapped_column(nullable=False, default=1.0)
    sparse_weight: Mapped[float] = mapped_column(nullable=False, default=1.0)
    fusion_k: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    dense_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    sparse_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    fused_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (UniqueConstraint("tenant_id", "index_profile_id", name="uq_retrieval_config_tenant_profile"),)


class CalibrationFixtureRecord(Base):
    __tablename__ = "calibration_fixture"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    retrieval_profile_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("rag_index_profiles.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[str] = mapped_column(String(120), nullable=False)
    source: Mapped[CalibrationSource] = mapped_column(Enum(CalibrationSource, name="CalibrationSource"), nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    created_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("uq_calibration_fixture_active_profile", "tenant_id", "retrieval_profile_id", unique=True, postgresql_where=is_active.is_(True)),
    )


class CalibrationFixtureEntryRecord(Base):
    __tablename__ = "calibration_fixture_entry"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    fixture_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("calibration_fixture.id", ondelete="CASCADE"), nullable=False)
    answer_run_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("rag_answer_runs.id", ondelete="SET NULL"), nullable=True)
    query: Mapped[str] = mapped_column(String, nullable=False)
    evidence_chunk_ids: Mapped[list[str]] = mapped_column(ARRAY(Uuid(as_uuid=False)), nullable=False, default=list)
    answer: Mapped[str] = mapped_column(String, nullable=False)
    confidence_label: Mapped[ConfidenceLabel] = mapped_column(Enum(ConfidenceLabel, name="ConfidenceLabel"), nullable=False)
    annotator_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    annotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


class CalibrationModelVersionRecord(Base):
    __tablename__ = "calibration_model_version"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    retrieval_profile_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("rag_index_profiles.id", ondelete="CASCADE"), nullable=False)
    fixture_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("calibration_fixture.id", ondelete="RESTRICT"), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    feature_names: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    threshold_used: Mapped[float] = mapped_column(nullable=False)
    precision_at_threshold: Mapped[float] = mapped_column(nullable=False)
    recall_at_threshold: Mapped[float] = mapped_column(nullable=False)
    f1_at_threshold: Mapped[float] = mapped_column(nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    promoted_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("uq_calibration_model_active_profile", "tenant_id", "retrieval_profile_id", unique=True, postgresql_where=is_active.is_(True)),
    )


class ConfidenceConfigRecord(Base):
    __tablename__ = "confidence_config"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    retrieval_profile_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("rag_index_profiles.id", ondelete="CASCADE"), nullable=False)
    feature_weights: Mapped[dict[str, float] | None] = mapped_column(JSONB, nullable=True)
    abstention_threshold: Mapped[float] = mapped_column(nullable=False, default=0.35)
    emit_numeric_score: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    min_labeled_entries: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    active_model_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("calibration_model_version.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (UniqueConstraint("tenant_id", "retrieval_profile_id", name="uq_confidence_config_tenant_profile"),)


class IndexGenerationRecord(Base):
    __tablename__ = "rag_index_generations"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    document_version_id: Mapped[str] = mapped_column("document_version_id", Uuid(as_uuid=False), ForeignKey("rag_document_versions.id", ondelete="CASCADE"), nullable=False)
    index_profile_id: Mapped[str] = mapped_column("index_profile_id", Uuid(as_uuid=False), ForeignKey("rag_index_profiles.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[IndexGenerationStatus] = mapped_column(
        Enum(IndexGenerationStatus, name="IndexGenerationStatus"),
        default=IndexGenerationStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class IngestionJobRecord(Base):
    __tablename__ = "rag_ingestion_jobs"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    document_version_id: Mapped[str] = mapped_column("document_version_id", Uuid(as_uuid=False), ForeignKey("rag_document_versions.id", ondelete="CASCADE"), nullable=False)
    generation_id: Mapped[str | None] = mapped_column("generation_id", Uuid(as_uuid=False), ForeignKey("rag_index_generations.id", ondelete="SET NULL"), nullable=True)
    stage: Mapped[str] = mapped_column(String(120), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(512), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[IngestionJobStatus] = mapped_column(Enum(IngestionJobStatus, name="IngestionJobStatus"), default=IngestionJobStatus.PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class OutboxEventRecord(Base):
    __tablename__ = "rag_outbox_events"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    generation_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(512), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[OutboxEventStatus] = mapped_column(Enum(OutboxEventStatus, name="OutboxEventStatus"), default=OutboxEventStatus.PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column("dispatched_at", DateTime(timezone=False), nullable=True)


class McpServerRecord(Base):
    __tablename__ = "mcp_servers"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    transport: Mapped[McpTransport] = mapped_column(Enum(McpTransport, name="McpTransport", values_callable=lambda values: [value.value for value in values]), nullable=False)
    command: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    args: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    auth_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    credential_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    headers_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    max_payload_bytes: Mapped[int] = mapped_column(Integer, default=1_048_576, nullable=False)
    allow_insecure: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[McpServerStatus] = mapped_column(Enum(McpServerStatus, name="McpServerStatus", values_callable=lambda values: [value.value for value in values]), default=McpServerStatus.UNKNOWN, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (Index("ix_mcp_servers_tenant_id", "tenant_id"),)


class McpToolRecord(Base):
    __tablename__ = "mcp_tools"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    server_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(4000), default="", nullable=False)
    input_schema: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "server_id", "name", name="uq_mcp_tools_tenant_server_name"),
        Index("ix_mcp_tools_tenant_server", "tenant_id", "server_id"),
    )


class McpInvocationRecord(Base):
    __tablename__ = "mcp_invocations"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    server_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False)
    tool_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("mcp_tools.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    args_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    args_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[McpInvocationStatus] = mapped_column(Enum(McpInvocationStatus, name="McpInvocationStatus", values_callable=lambda values: [value.value for value in values]), nullable=False)
    result_text: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "created_at", name="uq_mcp_invocations_tenant_created_at"),
        Index("ix_mcp_invocations_tenant_created_at", "tenant_id", "created_at"),
        Index("ix_mcp_invocations_tenant_server_status", "tenant_id", "server_id", "status"),
    )


# --- Entity mappers ----------------------------------------------------------


def _to_knowledge_base(row: KnowledgeBaseRecord) -> KnowledgeBase:
    return KnowledgeBase(
        id=row.id,
        tenant_id=row.tenant_id,
        slug=row.slug,
        name=row.name,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_knowledge_source(row: KnowledgeSourceRecord) -> KnowledgeSource:
    return KnowledgeSource(
        id=row.id,
        tenant_id=row.tenant_id,
        knowledge_base_id=row.knowledge_base_id,
        source_type=row.source_type,
        name=row.name,
        config_ref=row.config_ref,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_document(row: DocumentRecord) -> Document:
    return Document(
        id=row.id,
        tenant_id=row.tenant_id,
        knowledge_base_id=row.knowledge_base_id,
        source_id=row.source_id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_document_version(row: DocumentVersionRecord) -> DocumentVersion:
    return DocumentVersion(
        id=row.id,
        tenant_id=row.tenant_id,
        document_id=row.document_id,
        version_number=row.version_number,
        lifecycle_state=row.lifecycle_state,
        content_checksum=row.content_checksum,
        source_revision=row.source_revision,
        pipeline_fingerprint=row.pipeline_fingerprint,
        parsed_text=row.parsed_text,
        metadata=dict(row.metadata_json) if row.metadata_json else None,
        object_key_raw=row.object_key_raw,
        size_bytes=row.size_bytes,
        mime_type=row.mime_type,
        classification=row.classification,
        acl_principals=tuple(row.acl_principals),
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_model_profile(row: ModelProfileRecord) -> ModelProfile:
    return ModelProfile(
        id=row.id,
        tenant_id=row.tenant_id,
        name=row.name,
        profile_kind=row.profile_kind,
        provider=row.provider,
        model=row.model,
        modality=row.modality,
        dimensions=row.dimensions,
        config_json=row.config_json,
        version=row.version,
        is_active=row.is_active,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def _to_index_profile(row: IndexProfileRecord) -> IndexProfile:
    return IndexProfile(
        id=row.id,
        tenant_id=row.tenant_id,
        name=row.name,
        embedding_profile_id=row.embedding_profile_id,
        sparse_profile_id=row.sparse_profile_id,
        reranker_profile_id=row.reranker_profile_id,
        collection=row.collection,
        dimensions=row.dimensions,
        distance_metric=row.distance_metric,
        chunking_strategy=row.chunking_strategy,
        chunk_size_tokens=row.chunk_size_tokens,
        chunk_overlap_tokens=row.chunk_overlap_tokens,
        parent_chunk_size=row.parent_chunk_size,
        version=row.version,
        is_active=row.is_active,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def _to_retrieval_config(row: RetrievalConfigRecord) -> RetrievalConfig:
    return RetrievalConfig(
        index_profile_id=row.index_profile_id,
        dense_weight=row.dense_weight,
        sparse_weight=row.sparse_weight,
        fusion_k=row.fusion_k,
        dense_candidates=row.dense_candidates,
        sparse_candidates=row.sparse_candidates,
        fused_candidates=row.fused_candidates,
        enabled=row.enabled,
    )


def _to_calibration_fixture(row: CalibrationFixtureRecord) -> CalibrationFixture:
    return CalibrationFixture(row.id, row.tenant_id, row.retrieval_profile_id, row.version, row.source, row.entry_count, row.is_active, row.created_at, row.created_by)


def _to_calibration_fixture_entry(row: CalibrationFixtureEntryRecord) -> CalibrationFixtureEntry:
    return CalibrationFixtureEntry(row.id, row.fixture_id, row.answer_run_id, row.query, tuple(row.evidence_chunk_ids), row.answer, row.confidence_label, row.annotator_id, row.annotated_at, row.created_at)


def _to_calibration_model(row: CalibrationModelVersionRecord) -> CalibrationModelVersion:
    return CalibrationModelVersion(row.id, row.tenant_id, row.retrieval_profile_id, row.fixture_id, row.artifact_path, tuple(row.feature_names), row.threshold_used, row.precision_at_threshold, row.recall_at_threshold, row.f1_at_threshold, row.entry_count, row.is_active, row.created_at, row.promoted_by)


def _to_confidence_config(row: ConfidenceConfigRecord) -> ConfidenceConfig:
    return ConfidenceConfig(row.tenant_id, row.retrieval_profile_id, row.feature_weights, row.abstention_threshold, row.emit_numeric_score, row.min_labeled_entries, row.active_model_id, row.updated_at, row.updated_by)


def _to_index_generation(row: IndexGenerationRecord) -> IndexGeneration:
    return IndexGeneration(
        id=row.id,
        tenant_id=row.tenant_id,
        document_version_id=row.document_version_id,
        index_profile_id=row.index_profile_id,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_ingestion_job(row: IngestionJobRecord) -> IngestionJob:
    return IngestionJob(
        id=row.id,
        tenant_id=row.tenant_id,
        document_version_id=row.document_version_id,
        generation_id=row.generation_id,
        stage=row.stage,
        attempts=row.attempts,
        idempotency_key=row.idempotency_key,
        trace_id=row.trace_id,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_outbox_event(row: OutboxEventRecord) -> OutboxEvent:
    return OutboxEvent(
        id=row.id,
        tenant_id=row.tenant_id,
        event_type=row.event_type,
        resource_id=row.resource_id,
        generation_id=row.generation_id,
        idempotency_key=row.idempotency_key,
        trace_id=row.trace_id,
        payload=row.payload,
        status=row.status,
        created_at=row.created_at,
        dispatched_at=row.dispatched_at,
    )


def _to_mcp_server(row: McpServerRecord) -> McpServer:
    return McpServer(
        id=row.id, tenant_id=row.tenant_id, name=row.name, transport=row.transport,
        command=row.command, args=list(row.args), url=row.url, auth_type=row.auth_type,
        credential_ref=row.credential_ref, headers_json=dict(row.headers_json),
        timeout_seconds=row.timeout_seconds, max_payload_bytes=row.max_payload_bytes,
        allow_insecure=row.allow_insecure, enabled=row.enabled, status=row.status,
        last_error=row.last_error, created_at=row.created_at, updated_at=row.updated_at,
    )


def _to_mcp_tool(row: McpToolRecord) -> McpTool:
    return McpTool(
        id=row.id, tenant_id=row.tenant_id, server_id=row.server_id, name=row.name,
        description=row.description, input_schema=dict(row.input_schema), allowed=row.allowed,
        is_stale=row.is_stale, last_discovered_at=row.last_discovered_at,
        created_at=row.created_at, updated_at=row.updated_at,
    )


def _to_mcp_invocation(row: McpInvocationRecord) -> McpInvocation:
    return McpInvocation(
        id=row.id, tenant_id=row.tenant_id, server_id=row.server_id, tool_id=row.tool_id,
        user_id=row.user_id, args_json=dict(row.args_json), args_hash=row.args_hash,
        status=row.status, result_text=row.result_text, duration_ms=row.duration_ms,
        created_at=row.created_at,
    )


# --- Repositories ------------------------------------------------------------


class SqlAlchemyKnowledgeBaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, *, tenant_id: str, knowledge_base_id: str) -> KnowledgeBase | None:
        result = await self._session.execute(
            select(KnowledgeBaseRecord).where(
                KnowledgeBaseRecord.tenant_id == tenant_id,
                KnowledgeBaseRecord.id == knowledge_base_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_knowledge_base(row) if row else None

    async def find_by_slug(self, *, tenant_id: str, slug: str) -> KnowledgeBase | None:
        result = await self._session.execute(
            select(KnowledgeBaseRecord).where(
                KnowledgeBaseRecord.tenant_id == tenant_id,
                KnowledgeBaseRecord.slug == slug,
            )
        )
        row = result.scalar_one_or_none()
        return _to_knowledge_base(row) if row else None

    async def create(self, *, tenant_id: str, slug: str, name: str, status: str) -> KnowledgeBase:
        row = KnowledgeBaseRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            slug=slug,
            name=name,
            status=KnowledgeBaseStatus(status),
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_knowledge_base(row)

    async def list_by_tenant(self, *, tenant_id: str) -> list[KnowledgeBase]:
        result = await self._session.execute(
            select(KnowledgeBaseRecord).where(
                KnowledgeBaseRecord.tenant_id == tenant_id,
                KnowledgeBaseRecord.status == KnowledgeBaseStatus.ACTIVE,
            ).order_by(KnowledgeBaseRecord.created_at.desc())
        )
        return [_to_knowledge_base(row) for row in result.scalars().all()]

    async def archive(self, *, tenant_id: str, knowledge_base_id: str) -> KnowledgeBase | None:
        result = await self._session.execute(
            select(KnowledgeBaseRecord).where(
                KnowledgeBaseRecord.tenant_id == tenant_id,
                KnowledgeBaseRecord.id == knowledge_base_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.status = KnowledgeBaseStatus.ARCHIVED
        await self._session.commit()
        await self._session.refresh(row)
        return _to_knowledge_base(row)


class SqlAlchemyKnowledgeSourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        tenant_id: str,
        knowledge_base_id: str,
        source_type: str,
        name: str,
        config_ref: str | None,
    ) -> KnowledgeSource:
        row = KnowledgeSourceRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            source_type=KnowledgeSourceType(source_type),
            name=name,
            config_ref=config_ref,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_knowledge_source(row)


class SqlAlchemyDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, *, tenant_id: str, document_id: str) -> Document | None:
        result = await self._session.execute(
            select(DocumentRecord).where(
                DocumentRecord.tenant_id == tenant_id,
                DocumentRecord.id == document_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_document(row) if row else None

    async def create(self, *, tenant_id: str, knowledge_base_id: str, source_id: str, title: str | None) -> Document:
        row = DocumentRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            source_id=source_id,
            title=title,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_document(row)


class SqlAlchemyDocumentVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, *, tenant_id: str, version_id: str) -> DocumentVersion | None:
        result = await self._session.execute(
            select(DocumentVersionRecord).where(
                DocumentVersionRecord.tenant_id == tenant_id,
                DocumentVersionRecord.id == version_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_document_version(row) if row else None

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
        metadata: dict[str, str] | None = None,
    ) -> DocumentVersion:
        row = DocumentVersionRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            document_id=document_id,
            version_number=version_number,
            content_checksum=content_checksum,
            object_key_raw=object_key_raw,
            source_revision=source_revision,
            pipeline_fingerprint=pipeline_fingerprint,
            size_bytes=size_bytes,
            mime_type=mime_type,
            classification=Classification(classification),
            acl_principals=list(acl_principals),
            metadata_json=metadata,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_document_version(row)

    async def update_lifecycle_state(self, *, tenant_id: str, version_id: str, lifecycle_state: str) -> DocumentVersion | None:
        result = await self._session.execute(
            select(DocumentVersionRecord).where(
                DocumentVersionRecord.tenant_id == tenant_id,
                DocumentVersionRecord.id == version_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.lifecycle_state = DocumentVersionLifecycleState(lifecycle_state)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_document_version(row)

    async def _get_row(self, *, tenant_id: str, version_id: str) -> DocumentVersionRecord | None:
        result = await self._session.execute(
            select(DocumentVersionRecord).where(
                DocumentVersionRecord.tenant_id == tenant_id,
                DocumentVersionRecord.id == version_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_parsed_text(self, *, tenant_id: str, version_id: str, parsed_text: str) -> DocumentVersion | None:
        row = await self._get_row(tenant_id=tenant_id, version_id=version_id)
        if row is None:
            return None
        row.parsed_text = parsed_text
        row.lifecycle_state = DocumentVersionLifecycleState.NEEDS_REVIEW
        await self._session.commit()
        await self._session.refresh(row)
        return _to_document_version(row)

    async def patch_parsed_text(self, *, tenant_id: str, version_id: str, text: str) -> DocumentVersion | None:
        row = await self._get_row(tenant_id=tenant_id, version_id=version_id)
        if row is None:
            return None
        row.parsed_text = text
        await self._session.commit()
        await self._session.refresh(row)
        return _to_document_version(row)

    async def find_parsed_text(self, *, tenant_id: str, version_id: str) -> str | None:
        row = await self._get_row(tenant_id=tenant_id, version_id=version_id)
        return row.parsed_text if row else None

    async def count_needs_review(self, *, tenant_id: str) -> int:
        from sqlalchemy import func, select
        result = await self._session.execute(
            select(func.count()).where(
                DocumentVersionRecord.tenant_id == tenant_id,
                DocumentVersionRecord.lifecycle_state == DocumentVersionLifecycleState.NEEDS_REVIEW,
            )
        )
        return result.scalar_one() or 0

    async def count_needs_review(self, *, tenant_id: str) -> int:
        """Return count of document versions in NEEDS_REVIEW state for a tenant."""
        from sqlalchemy import func
        result = await self._session.execute(
            select(func.count()).where(
                DocumentVersionRecord.tenant_id == tenant_id,
                DocumentVersionRecord.lifecycle_state == DocumentVersionLifecycleState.NEEDS_REVIEW,
            )
        )
        return result.scalar_one() or 0

    async def list_by_knowledge_base(
        self,
        *,
        tenant_id: str,
        knowledge_base_id: str,
    ) -> list[tuple[DocumentVersion, str, str]]:
        """Return list of (version, document_title, filename) for a KB."""
        result = await self._session.execute(
            select(DocumentVersionRecord, DocumentRecord)
            .join(DocumentRecord, DocumentVersionRecord.document_id == DocumentRecord.id)
            .where(
                DocumentVersionRecord.tenant_id == tenant_id,
                DocumentRecord.knowledge_base_id == knowledge_base_id,
                DocumentRecord.tenant_id == tenant_id,
            )
            .order_by(DocumentVersionRecord.created_at.desc())
        )
        rows = result.all()
        return [
            (_to_document_version(ver), doc.title or doc.id, doc.id)
            for ver, doc in rows
        ]


class SqlAlchemyModelProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, *, tenant_id: str, profile_id: str) -> ModelProfile | None:
        result = await self._session.execute(
            select(ModelProfileRecord).where(
                ModelProfileRecord.tenant_id == tenant_id,
                ModelProfileRecord.id == profile_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_model_profile(row) if row else None

    async def list_by_tenant(self, *, tenant_id: str) -> list[ModelProfile]:
        result = await self._session.execute(
            select(ModelProfileRecord).where(
                ModelProfileRecord.tenant_id == tenant_id,
                ModelProfileRecord.is_active == True,  # noqa: E712
            ).order_by(ModelProfileRecord.created_at.desc())
        )
        return [_to_model_profile(row) for row in result.scalars().all()]

    async def archive(self, *, tenant_id: str, profile_id: str) -> ModelProfile | None:
        result = await self._session.execute(
            select(ModelProfileRecord).where(
                ModelProfileRecord.tenant_id == tenant_id,
                ModelProfileRecord.id == profile_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.is_active = False
        await self._session.commit()
        await self._session.refresh(row)
        return _to_model_profile(row)

    async def create(
        self,
        *,
        tenant_id: str,
        name: str,
        profile_kind: str,
        provider: str,
        model: str,
        modality: str = "TEXT",
        dimensions: int | None,
        config_json: str | None = None,
        version: str,
    ) -> ModelProfile:
        row = ModelProfileRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            name=name,
            profile_kind=profile_kind,
            provider=provider,
            model=model,
            modality=modality,
            dimensions=dimensions,
            config_json=config_json,
            version=version,
            is_active=True,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_model_profile(row)


class SqlAlchemyIndexProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, *, tenant_id: str, profile_id: str) -> IndexProfile | None:
        result = await self._session.execute(
            select(IndexProfileRecord).where(
                IndexProfileRecord.tenant_id == tenant_id,
                IndexProfileRecord.id == profile_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_index_profile(row) if row else None

    async def find_active(self, *, tenant_id: str) -> IndexProfile | None:
        result = await self._session.execute(
            select(IndexProfileRecord).where(
                IndexProfileRecord.tenant_id == tenant_id,
                IndexProfileRecord.is_active == True,  # noqa: E712
            ).limit(1)
        )
        row = result.scalar_one_or_none()
        return _to_index_profile(row) if row else None

    async def list_by_tenant(self, *, tenant_id: str) -> list[IndexProfile]:
        result = await self._session.execute(
            select(IndexProfileRecord).where(
                IndexProfileRecord.tenant_id == tenant_id,
            ).order_by(IndexProfileRecord.created_at.desc())
        )
        return [_to_index_profile(row) for row in result.scalars().all()]

    async def set_active(self, *, tenant_id: str, profile_id: str) -> IndexProfile | None:
        # Deactivate all profiles for tenant
        all_result = await self._session.execute(
            select(IndexProfileRecord).where(
                IndexProfileRecord.tenant_id == tenant_id,
            )
        )
        for r in all_result.scalars().all():
            r.is_active = False
        # Activate selected profile
        result = await self._session.execute(
            select(IndexProfileRecord).where(
                IndexProfileRecord.tenant_id == tenant_id,
                IndexProfileRecord.id == profile_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.is_active = True
        await self._session.commit()
        await self._session.refresh(row)
        return _to_index_profile(row)

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
    ) -> IndexProfile:
        row = IndexProfileRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            name=name,
            embedding_profile_id=embedding_profile_id,
            sparse_profile_id=sparse_profile_id,
            reranker_profile_id=reranker_profile_id,
            collection=collection,
            dimensions=dimensions,
            distance_metric=distance_metric,
            chunking_strategy=chunking_strategy,
            chunk_size_tokens=chunk_size_tokens,
            chunk_overlap_tokens=chunk_overlap_tokens,
            parent_chunk_size=parent_chunk_size,
            version=version,
            is_active=is_active,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_index_profile(row)

    async def activate(self, *, tenant_id: str, profile_id: str) -> IndexProfile | None:
        return await self.set_active(tenant_id=tenant_id, profile_id=profile_id)


class SqlAlchemyRetrievalConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_profile(self, *, tenant_id: str, index_profile_id: str) -> RetrievalConfig | None:
        result = await self._session.execute(
            select(RetrievalConfigRecord).where(
                RetrievalConfigRecord.tenant_id == tenant_id,
                RetrievalConfigRecord.index_profile_id == index_profile_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_retrieval_config(row) if row else None

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
    ) -> RetrievalConfig:
        result = await self._session.execute(
            select(RetrievalConfigRecord).where(
                RetrievalConfigRecord.tenant_id == tenant_id,
                RetrievalConfigRecord.index_profile_id == index_profile_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = RetrievalConfigRecord(id=str(uuid4()), tenant_id=tenant_id, index_profile_id=index_profile_id)
            self._session.add(row)
        row.dense_weight = dense_weight
        row.sparse_weight = sparse_weight
        row.fusion_k = fusion_k
        row.dense_candidates = dense_candidates
        row.sparse_candidates = sparse_candidates
        row.fused_candidates = fused_candidates
        row.enabled = enabled
        await self._session.commit()
        await self._session.refresh(row)
        return _to_retrieval_config(row)

    async def delete(self, *, tenant_id: str, index_profile_id: str) -> bool:
        result = await self._session.execute(
            select(RetrievalConfigRecord).where(
                RetrievalConfigRecord.tenant_id == tenant_id,
                RetrievalConfigRecord.index_profile_id == index_profile_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.commit()
        return True


class SqlCalibrationFixtureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, fixture: CalibrationFixture) -> CalibrationFixture:
        row = CalibrationFixtureRecord(
            id=fixture.id, tenant_id=fixture.tenant_id, retrieval_profile_id=fixture.retrieval_profile_id, version=fixture.version,
            source=fixture.source, entry_count=fixture.entry_count, is_active=fixture.is_active, created_at=fixture.created_at, created_by=fixture.created_by,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_calibration_fixture(row)

    async def get_active(self, *, tenant_id: str, retrieval_profile_id: str) -> CalibrationFixture | None:
        result = await self._session.execute(select(CalibrationFixtureRecord).where(CalibrationFixtureRecord.tenant_id == tenant_id, CalibrationFixtureRecord.retrieval_profile_id == retrieval_profile_id, CalibrationFixtureRecord.is_active.is_(True)))
        row = result.scalar_one_or_none()
        return _to_calibration_fixture(row) if row else None

    async def list(self, *, tenant_id: str, retrieval_profile_id: str) -> list[CalibrationFixture]:
        result = await self._session.execute(select(CalibrationFixtureRecord).where(CalibrationFixtureRecord.tenant_id == tenant_id, CalibrationFixtureRecord.retrieval_profile_id == retrieval_profile_id).order_by(CalibrationFixtureRecord.created_at.desc()))
        return [_to_calibration_fixture(row) for row in result.scalars()]

    async def deactivate_previous(self, *, tenant_id: str, retrieval_profile_id: str) -> None:
        result = await self._session.execute(select(CalibrationFixtureRecord).where(CalibrationFixtureRecord.tenant_id == tenant_id, CalibrationFixtureRecord.retrieval_profile_id == retrieval_profile_id, CalibrationFixtureRecord.is_active.is_(True)))
        for row in result.scalars():
            row.is_active = False
        await self._session.commit()

    async def append_entries(self, *, tenant_id: str, fixture_id: str, entries: list[CalibrationFixtureEntry]) -> None:
        result = await self._session.execute(select(CalibrationFixtureRecord).where(CalibrationFixtureRecord.id == fixture_id, CalibrationFixtureRecord.tenant_id == tenant_id))
        fixture = result.scalar_one_or_none()
        if fixture is None:
            return
        self._session.add_all([CalibrationFixtureEntryRecord(id=entry.id, fixture_id=fixture_id, answer_run_id=entry.answer_run_id, query=entry.query, evidence_chunk_ids=list(entry.evidence_chunk_ids), answer=entry.answer, confidence_label=entry.confidence_label, annotator_id=entry.annotator_id, annotated_at=entry.annotated_at, created_at=entry.created_at) for entry in entries])
        fixture.entry_count += len(entries)
        await self._session.commit()

    async def count_labeled_entries(self, *, tenant_id: str, retrieval_profile_id: str) -> int:
        result = await self._session.execute(select(CalibrationFixtureRecord.entry_count).where(CalibrationFixtureRecord.tenant_id == tenant_id, CalibrationFixtureRecord.retrieval_profile_id == retrieval_profile_id, CalibrationFixtureRecord.source == CalibrationSource.OPERATOR_LABELED, CalibrationFixtureRecord.is_active.is_(True)))
        return sum(result.scalars())

    async def get(self, *, tenant_id: str, fixture_id: str) -> CalibrationFixture | None:
        result = await self._session.execute(select(CalibrationFixtureRecord).where(CalibrationFixtureRecord.id == fixture_id, CalibrationFixtureRecord.tenant_id == tenant_id))
        row = result.scalar_one_or_none()
        return _to_calibration_fixture(row) if row else None

    async def get_entries(self, *, tenant_id: str, fixture_id: str) -> list[CalibrationFixtureEntry]:
        result = await self._session.execute(
            select(CalibrationFixtureEntryRecord)
            .join(CalibrationFixtureRecord, CalibrationFixtureEntryRecord.fixture_id == CalibrationFixtureRecord.id)
            .where(CalibrationFixtureEntryRecord.fixture_id == fixture_id, CalibrationFixtureRecord.tenant_id == tenant_id)
            .order_by(CalibrationFixtureEntryRecord.created_at)
        )
        return [_to_calibration_fixture_entry(row) for row in result.scalars()]

    async def upsert_answer_run_entries(self, *, tenant_id: str, fixture_id: str, entries: list[CalibrationFixtureEntry]) -> int:
        result = await self._session.execute(select(CalibrationFixtureRecord).where(CalibrationFixtureRecord.id == fixture_id, CalibrationFixtureRecord.tenant_id == tenant_id).with_for_update())
        fixture = result.scalar_one_or_none()
        if fixture is None:
            return 0
        created = 0
        for entry in entries:
            result = await self._session.execute(select(CalibrationFixtureEntryRecord).where(CalibrationFixtureEntryRecord.fixture_id == fixture_id, CalibrationFixtureEntryRecord.answer_run_id == entry.answer_run_id))
            row = result.scalar_one_or_none()
            if row is None:
                self._session.add(CalibrationFixtureEntryRecord(id=entry.id, fixture_id=fixture_id, answer_run_id=entry.answer_run_id, query=entry.query, evidence_chunk_ids=list(entry.evidence_chunk_ids), answer=entry.answer, confidence_label=entry.confidence_label, annotator_id=entry.annotator_id, annotated_at=entry.annotated_at, created_at=entry.created_at))
                created += 1
            else:
                row.confidence_label = entry.confidence_label
                row.annotator_id = entry.annotator_id
                row.annotated_at = entry.annotated_at
        fixture.entry_count += created
        await self._session.commit()
        return created


class SqlCalibrationModelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, model: CalibrationModelVersion) -> CalibrationModelVersion:
        row = CalibrationModelVersionRecord(id=model.id, tenant_id=model.tenant_id, retrieval_profile_id=model.retrieval_profile_id, fixture_id=model.fixture_id, artifact_path=model.artifact_path, feature_names=list(model.feature_names), threshold_used=model.threshold_used, precision_at_threshold=model.precision_at_threshold, recall_at_threshold=model.recall_at_threshold, f1_at_threshold=model.f1_at_threshold, entry_count=model.entry_count, is_active=model.is_active, created_at=model.created_at, promoted_by=model.promoted_by)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_calibration_model(row)

    async def get_active(self, *, tenant_id: str, retrieval_profile_id: str) -> CalibrationModelVersion | None:
        result = await self._session.execute(select(CalibrationModelVersionRecord).where(CalibrationModelVersionRecord.tenant_id == tenant_id, CalibrationModelVersionRecord.retrieval_profile_id == retrieval_profile_id, CalibrationModelVersionRecord.is_active.is_(True)))
        row = result.scalar_one_or_none()
        return _to_calibration_model(row) if row else None

    async def promote(self, *, tenant_id: str, model_id: str, promoted_by: str) -> CalibrationModelVersion | None:
        result = await self._session.execute(select(CalibrationModelVersionRecord).where(CalibrationModelVersionRecord.id == model_id, CalibrationModelVersionRecord.tenant_id == tenant_id))
        target = result.scalar_one_or_none()
        if target is None:
            return None
        active = await self._session.execute(select(CalibrationModelVersionRecord).where(CalibrationModelVersionRecord.tenant_id == tenant_id, CalibrationModelVersionRecord.retrieval_profile_id == target.retrieval_profile_id, CalibrationModelVersionRecord.is_active.is_(True)))
        for row in active.scalars():
            row.is_active = False
        target.is_active = True
        target.promoted_by = promoted_by
        await self._session.commit()
        await self._session.refresh(target)
        return _to_calibration_model(target)

    async def list(self, *, tenant_id: str, retrieval_profile_id: str) -> list[CalibrationModelVersion]:
        result = await self._session.execute(select(CalibrationModelVersionRecord).where(CalibrationModelVersionRecord.tenant_id == tenant_id, CalibrationModelVersionRecord.retrieval_profile_id == retrieval_profile_id).order_by(CalibrationModelVersionRecord.created_at.desc()))
        return [_to_calibration_model(row) for row in result.scalars()]

    async def get(self, *, tenant_id: str, model_id: str) -> CalibrationModelVersion | None:
        result = await self._session.execute(select(CalibrationModelVersionRecord).where(CalibrationModelVersionRecord.id == model_id, CalibrationModelVersionRecord.tenant_id == tenant_id))
        row = result.scalar_one_or_none()
        return _to_calibration_model(row) if row else None


class SqlConfidenceConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_default(self, *, tenant_id: str, retrieval_profile_id: str) -> ConfidenceConfig:
        result = await self._session.execute(select(ConfidenceConfigRecord).where(ConfidenceConfigRecord.tenant_id == tenant_id, ConfidenceConfigRecord.retrieval_profile_id == retrieval_profile_id))
        row = result.scalar_one_or_none()
        return _to_confidence_config(row) if row else ConfidenceConfig.defaults(tenant_id=tenant_id, retrieval_profile_id=retrieval_profile_id)

    async def upsert(self, config: ConfidenceConfig) -> ConfidenceConfig:
        result = await self._session.execute(select(ConfidenceConfigRecord).where(ConfidenceConfigRecord.tenant_id == config.tenant_id, ConfidenceConfigRecord.retrieval_profile_id == config.retrieval_profile_id))
        row = result.scalar_one_or_none()
        if row is None:
            row = ConfidenceConfigRecord(id=str(uuid4()), tenant_id=config.tenant_id, retrieval_profile_id=config.retrieval_profile_id)
            self._session.add(row)
        row.feature_weights = config.feature_weights
        row.abstention_threshold = config.abstention_threshold
        row.emit_numeric_score = config.emit_numeric_score
        row.min_labeled_entries = config.min_labeled_entries
        row.active_model_id = config.active_model_id
        row.updated_by = config.updated_by
        await self._session.commit()
        await self._session.refresh(row)
        return _to_confidence_config(row)

    async def set_active_model(self, *, tenant_id: str, retrieval_profile_id: str, active_model_id: str | None, updated_by: str | None) -> ConfidenceConfig:
        config = await self.get_or_default(tenant_id=tenant_id, retrieval_profile_id=retrieval_profile_id)
        return await self.upsert(ConfidenceConfig(tenant_id, retrieval_profile_id, config.feature_weights, config.abstention_threshold, config.emit_numeric_score, config.min_labeled_entries, active_model_id, updated_by=updated_by))


class SqlAlchemyIndexGenerationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, *, tenant_id: str, generation_id: str) -> IndexGeneration | None:
        result = await self._session.execute(
            select(IndexGenerationRecord).where(
                IndexGenerationRecord.tenant_id == tenant_id,
                IndexGenerationRecord.id == generation_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_index_generation(row) if row else None

    async def find_active_for_version(self, *, tenant_id: str, document_version_id: str) -> IndexGeneration | None:
        result = await self._session.execute(
            select(IndexGenerationRecord).where(
                IndexGenerationRecord.tenant_id == tenant_id,
                IndexGenerationRecord.document_version_id == document_version_id,
                IndexGenerationRecord.status == IndexGenerationStatus.ACTIVE,
            )
        )
        row = result.scalar_one_or_none()
        return _to_index_generation(row) if row else None

    async def find_active_for_knowledge_bases(
        self, *, tenant_id: str, knowledge_base_ids: tuple[str, ...]
    ) -> list[IndexGeneration]:
        if not knowledge_base_ids:
            return []
        result = await self._session.execute(
            select(IndexGenerationRecord)
            .join(DocumentVersionRecord, IndexGenerationRecord.document_version_id == DocumentVersionRecord.id)
            .join(DocumentRecord, DocumentVersionRecord.document_id == DocumentRecord.id)
            .where(
                IndexGenerationRecord.tenant_id == tenant_id,
                IndexGenerationRecord.status == IndexGenerationStatus.ACTIVE,
                DocumentVersionRecord.tenant_id == tenant_id,
                DocumentRecord.tenant_id == tenant_id,
                DocumentRecord.knowledge_base_id.in_(knowledge_base_ids),
            )
        )
        return [_to_index_generation(row) for row in result.scalars().all()]

    async def create(self, *, tenant_id: str, document_version_id: str, index_profile_id: str, status: str) -> IndexGeneration:
        row = IndexGenerationRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            document_version_id=document_version_id,
            index_profile_id=index_profile_id,
            status=IndexGenerationStatus(status),
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_index_generation(row)

    async def update_status(self, *, tenant_id: str, generation_id: str, status: str) -> IndexGeneration | None:
        result = await self._session.execute(
            select(IndexGenerationRecord).where(
                IndexGenerationRecord.tenant_id == tenant_id,
                IndexGenerationRecord.id == generation_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.status = IndexGenerationStatus(status)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_index_generation(row)


class SqlAlchemyIngestionJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_idempotency_key(self, *, tenant_id: str, idempotency_key: str) -> IngestionJob | None:
        result = await self._session.execute(
            select(IngestionJobRecord).where(
                IngestionJobRecord.tenant_id == tenant_id,
                IngestionJobRecord.idempotency_key == idempotency_key,
            )
        )
        row = result.scalar_one_or_none()
        return _to_ingestion_job(row) if row else None

    async def create(
        self,
        *,
        tenant_id: str,
        document_version_id: str,
        generation_id: str | None,
        stage: str,
        idempotency_key: str,
        trace_id: str | None,
    ) -> IngestionJob:
        row = IngestionJobRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            document_version_id=document_version_id,
            generation_id=generation_id,
            stage=stage,
            idempotency_key=idempotency_key,
            trace_id=trace_id,
            status=IngestionJobStatus.PENDING,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_ingestion_job(row)


class SqlAlchemyOutboxEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
    ) -> OutboxEvent:
        row = OutboxEventRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            event_type=event_type,
            resource_id=resource_id,
            generation_id=generation_id,
            idempotency_key=idempotency_key,
            trace_id=trace_id,
            payload=payload,
            status=OutboxEventStatus.PENDING,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_outbox_event(row)

    async def find_pending(self, *, tenant_id: str, limit: int) -> list[OutboxEvent]:
        result = await self._session.execute(
            select(OutboxEventRecord)
            .where(
                OutboxEventRecord.tenant_id == tenant_id,
                OutboxEventRecord.status == OutboxEventStatus.PENDING,
            )
            .limit(limit)
        )
        rows = list(result.scalars().all())
        return [_to_outbox_event(row) for row in rows]

    async def mark_dispatched(self, *, tenant_id: str, event_id: str) -> None:
        result = await self._session.execute(
            select(OutboxEventRecord).where(
                OutboxEventRecord.tenant_id == tenant_id,
                OutboxEventRecord.id == event_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return
        row.status = OutboxEventStatus.DISPATCHED
        row.dispatched_at = utc_now()
        await self._session.commit()


# --- Chunk ORM ---------------------------------------------------------------


class ChunkRecord(Base):
    __tablename__ = "rag_chunks"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    document_version_id: Mapped[str] = mapped_column("document_version_id", Uuid(as_uuid=False), ForeignKey("rag_document_versions.id", ondelete="CASCADE"), nullable=False)
    generation_id: Mapped[str] = mapped_column("generation_id", Uuid(as_uuid=False), ForeignKey("rag_index_generations.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[str | None] = mapped_column("parent_id", Uuid(as_uuid=False), ForeignKey("rag_chunks.id", ondelete="SET NULL"), nullable=True)
    chunk_type: Mapped[ChunkType] = mapped_column(Enum(ChunkType, name="ChunkType"), default=ChunkType.CHILD, nullable=False)
    hierarchy_path: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str] = mapped_column(String(60), nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_offsets_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_offsets_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunker_version: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)


def _to_chunk(row: ChunkRecord) -> Chunk:
    return Chunk(
        id=row.id,
        tenant_id=row.tenant_id,
        document_version_id=row.document_version_id,
        generation_id=row.generation_id,
        parent_id=row.parent_id,
        chunk_type=row.chunk_type,
        hierarchy_path=tuple(row.hierarchy_path),
        page=row.page,
        content_type=row.content_type,
        text=row.text,
        token_count=row.token_count,
        source_offsets_start=row.source_offsets_start,
        source_offsets_end=row.source_offsets_end,
        chunker_version=row.chunker_version,
        created_at=row.created_at,
    )


class SqlAlchemyChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_generation(self, *, tenant_id: str, generation_id: str) -> list[Chunk]:
        result = await self._session.execute(
            select(ChunkRecord)
            .where(
                ChunkRecord.tenant_id == tenant_id,
                ChunkRecord.generation_id == generation_id,
            )
            .order_by(ChunkRecord.created_at)
        )
        rows = list(result.scalars().all())
        return [_to_chunk(row) for row in rows]

    async def find_by_ids(self, *, tenant_id: str, chunk_ids: tuple[str, ...]) -> list[Chunk]:
        if not chunk_ids:
            return []
        result = await self._session.execute(select(ChunkRecord).where(ChunkRecord.tenant_id == tenant_id, ChunkRecord.id.in_(chunk_ids)))
        return [_to_chunk(row) for row in result.scalars()]

    async def create_many(self, *, tenant_id: str, chunks: list[dict[str, object]]) -> int:
        for chunk_data in chunks:
            row = ChunkRecord(
                id=str(chunk_data.get("id", str(uuid4()))),
                tenant_id=tenant_id,
                document_version_id=str(chunk_data["document_version_id"]),
                generation_id=str(chunk_data["generation_id"]),
                parent_id=chunk_data.get("parent_id"),
                chunk_type=ChunkType(str(chunk_data.get("chunk_type", "CHILD"))),
                hierarchy_path=list(cast(list[str], chunk_data.get("hierarchy_path", []))),
                page=chunk_data.get("page"),
                content_type=str(chunk_data.get("content_type", "narrative")),
                text=str(chunk_data.get("text", "")),
                token_count=int(cast(int, chunk_data.get("token_count", 0))),
                source_offsets_start=chunk_data.get("source_offsets_start"),
                source_offsets_end=chunk_data.get("source_offsets_end"),
                chunker_version=str(chunk_data.get("chunker_version", "1")),
            )
            self._session.add(row)
        await self._session.commit()
        return len(chunks)

    async def delete_by_generation(self, *, tenant_id: str, generation_id: str) -> None:
        await self._session.execute(
            select(ChunkRecord).where(
                ChunkRecord.tenant_id == tenant_id,
                ChunkRecord.generation_id == generation_id,
            )
        )
        from sqlalchemy import delete as sa_delete

        await self._session.execute(
            sa_delete(ChunkRecord).where(
                ChunkRecord.tenant_id == tenant_id,
                ChunkRecord.generation_id == generation_id,
            )
        )
        await self._session.commit()


# --- Stage checkpoint ORM ----------------------------------------------------


class StageCheckpointRecord(Base):
    __tablename__ = "rag_stage_checkpoints"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    document_version_id: Mapped[str] = mapped_column("document_version_id", Uuid(as_uuid=False), ForeignKey("rag_document_versions.id", ondelete="CASCADE"), nullable=False)
    generation_id: Mapped[str | None] = mapped_column("generation_id", Uuid(as_uuid=False), ForeignKey("rag_index_generations.id", ondelete="SET NULL"), nullable=True)
    stage: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[StageCheckpointStatus] = mapped_column(
        Enum(StageCheckpointStatus, name="StageCheckpointStatus"),
        default=StageCheckpointStatus.PENDING,
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(512), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    checkpoint_data: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)
    __table_args__ = ()


def _to_stage_checkpoint(row: StageCheckpointRecord) -> StageCheckpoint:
    return StageCheckpoint(
        id=row.id,
        tenant_id=row.tenant_id,
        document_version_id=row.document_version_id,
        generation_id=row.generation_id,
        stage=row.stage,
        status=row.status,
        attempts=row.attempts,
        idempotency_key=row.idempotency_key,
        trace_id=row.trace_id,
        checkpoint_data=row.checkpoint_data,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyStageCheckpointRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_stage(self, *, tenant_id: str, document_version_id: str, stage: str) -> StageCheckpoint | None:
        result = await self._session.execute(
            select(StageCheckpointRecord).where(
                StageCheckpointRecord.tenant_id == tenant_id,
                StageCheckpointRecord.document_version_id == document_version_id,
                StageCheckpointRecord.stage == stage,
            )
        )
        row = result.scalar_one_or_none()
        return _to_stage_checkpoint(row) if row else None

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
    ) -> StageCheckpoint:
        existing = await self.find_by_stage(tenant_id=tenant_id, document_version_id=document_version_id, stage=stage)
        if existing is not None:
            result = await self._session.execute(select(StageCheckpointRecord).where(StageCheckpointRecord.id == existing.id))
            row = result.scalar_one()
            row.status = StageCheckpointStatus(status)
            row.attempts = attempts
            row.generation_id = generation_id
            row.trace_id = trace_id
            row.checkpoint_data = checkpoint_data
        else:
            row = StageCheckpointRecord(
                id=str(uuid4()),
                tenant_id=tenant_id,
                document_version_id=document_version_id,
                generation_id=generation_id,
                stage=stage,
                status=StageCheckpointStatus(status),
                attempts=attempts,
                idempotency_key=idempotency_key,
                trace_id=trace_id,
                checkpoint_data=checkpoint_data,
            )
            self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_stage_checkpoint(row)


class ProviderCredentialRecord(Base):
    __tablename__ = "rag_provider_credentials"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    key_name: Mapped[str] = mapped_column(String(120), nullable=False)
    value_enc: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class SqlAlchemyProviderCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def set_credential(
        self,
        *,
        tenant_id: str,
        provider: str,
        key_name: str,
        value_enc: str,
    ) -> ProviderCredentialRecord:
        result = await self._session.execute(
            select(ProviderCredentialRecord).where(
                ProviderCredentialRecord.tenant_id == tenant_id,
                ProviderCredentialRecord.provider == provider,
                ProviderCredentialRecord.key_name == key_name,
            )
        )
        row = result.scalar_one_or_none()
        if row is not None:
            row.value_enc = value_enc
            row.is_active = True
        else:
            row = ProviderCredentialRecord(
                id=str(uuid4()),
                tenant_id=tenant_id,
                provider=provider,
                key_name=key_name,
                value_enc=value_enc,
                is_active=True,
            )
            self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def find_credential(
        self,
        *,
        tenant_id: str,
        provider: str,
        key_name: str,
    ) -> ProviderCredentialRecord | None:
        result = await self._session.execute(
            select(ProviderCredentialRecord).where(
                ProviderCredentialRecord.tenant_id == tenant_id,
                ProviderCredentialRecord.provider == provider,
                ProviderCredentialRecord.key_name == key_name,
                ProviderCredentialRecord.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(self, *, tenant_id: str) -> list[ProviderCredentialRecord]:
        result = await self._session.execute(
            select(ProviderCredentialRecord).where(
                ProviderCredentialRecord.tenant_id == tenant_id,
            ).order_by(ProviderCredentialRecord.provider, ProviderCredentialRecord.key_name)
        )
        return list(result.scalars().all())

    async def revoke(
        self,
        *,
        tenant_id: str,
        provider: str,
        key_name: str,
    ) -> bool:
        result = await self._session.execute(
            select(ProviderCredentialRecord).where(
                ProviderCredentialRecord.tenant_id == tenant_id,
                ProviderCredentialRecord.provider == provider,
                ProviderCredentialRecord.key_name == key_name,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        row.is_active = False
        row.value_enc = ""
        await self._session.commit()
        return True


class DecompositionConfigRecord(Base):
    __tablename__ = "rag_decomposition_configs"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(
        "knowledge_base_id", Uuid(as_uuid=False),
        ForeignKey("rag_knowledge_bases.id", ondelete="CASCADE"), nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    model_profile_id: Mapped[str] = mapped_column(
        "model_profile_id", Uuid(as_uuid=False),
        ForeignKey("rag_model_profiles.id", ondelete="RESTRICT"), nullable=False,
    )
    system_prompt: Mapped[str] = mapped_column(String, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(String, nullable=False)
    max_sub_queries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    max_depth: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    min_complexity_score: Mapped[float] = mapped_column(nullable=False, default=0.6)
    guardrails_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (UniqueConstraint("tenant_id", "knowledge_base_id", name="uq_decomp_config_tenant_kb"),)


def _to_decomposition_config(row: DecompositionConfigRecord) -> DecompositionConfig:
    return DecompositionConfig(
        id=row.id,
        tenant_id=row.tenant_id,
        knowledge_base_id=row.knowledge_base_id,
        enabled=row.enabled,
        model_profile_id=row.model_profile_id,
        system_prompt=row.system_prompt,
        user_prompt_template=row.user_prompt_template,
        max_sub_queries=row.max_sub_queries,
        max_depth=row.max_depth,
        min_complexity_score=row.min_complexity_score,
        guardrails=row.guardrails_json or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyDecompositionConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_knowledge_base(self, *, tenant_id: str, knowledge_base_id: str) -> DecompositionConfig | None:
        result = await self._session.execute(
            select(DecompositionConfigRecord).where(
                DecompositionConfigRecord.tenant_id == tenant_id,
                DecompositionConfigRecord.knowledge_base_id == knowledge_base_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_decomposition_config(row) if row else None

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
    ) -> DecompositionConfig:
        result = await self._session.execute(
            select(DecompositionConfigRecord).where(
                DecompositionConfigRecord.tenant_id == tenant_id,
                DecompositionConfigRecord.knowledge_base_id == knowledge_base_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = DecompositionConfigRecord(
                id=str(uuid4()),
                tenant_id=tenant_id,
                knowledge_base_id=knowledge_base_id,
            )
            self._session.add(row)
        row.enabled = enabled
        row.model_profile_id = model_profile_id
        row.system_prompt = system_prompt
        row.user_prompt_template = user_prompt_template
        row.max_sub_queries = max_sub_queries
        row.max_depth = max_depth
        row.min_complexity_score = min_complexity_score
        row.guardrails_json = guardrails
        await self._session.commit()
        await self._session.refresh(row)
        return _to_decomposition_config(row)

    async def delete(self, *, tenant_id: str, knowledge_base_id: str) -> bool:
        result = await self._session.execute(
            select(DecompositionConfigRecord).where(
                DecompositionConfigRecord.tenant_id == tenant_id,
                DecompositionConfigRecord.knowledge_base_id == knowledge_base_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.commit()
        return True


class PlannerConfigRecord(Base):
    __tablename__ = "rag_planner_configs"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(
        "knowledge_base_id", Uuid(as_uuid=False),
        ForeignKey("rag_knowledge_bases.id", ondelete="CASCADE"), nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    model_profile_id: Mapped[str] = mapped_column(
        "model_profile_id", Uuid(as_uuid=False),
        ForeignKey("rag_model_profiles.id", ondelete="RESTRICT"), nullable=False,
    )
    system_prompt: Mapped[str] = mapped_column(String, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(String, nullable=False)
    max_tasks: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    task_timeout_seconds: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    task_types_json: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["RAG", "MCP", "GENERAL"], nullable=False)
    mcp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    guardrails_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (UniqueConstraint("tenant_id", "knowledge_base_id", name="uq_planner_config_tenant_kb"),)


def _to_planner_config(row: PlannerConfigRecord) -> PlannerConfig:
    return PlannerConfig(
        id=row.id,
        tenant_id=row.tenant_id,
        knowledge_base_id=row.knowledge_base_id,
        enabled=row.enabled,
        model_profile_id=row.model_profile_id,
        system_prompt=row.system_prompt,
        user_prompt_template=row.user_prompt_template,
        max_tasks=row.max_tasks,
        task_timeout_seconds=row.task_timeout_seconds,
        task_types=tuple(row.task_types_json or []),
        mcp_enabled=row.mcp_enabled,
        guardrails=row.guardrails_json or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyPlannerConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_knowledge_base(self, *, tenant_id: str, knowledge_base_id: str) -> PlannerConfig | None:
        result = await self._session.execute(select(PlannerConfigRecord).where(
            PlannerConfigRecord.tenant_id == tenant_id,
            PlannerConfigRecord.knowledge_base_id == knowledge_base_id,
        ))
        row = result.scalar_one_or_none()
        return _to_planner_config(row) if row else None

    async def upsert(self, *, tenant_id: str, knowledge_base_id: str, enabled: bool, model_profile_id: str, system_prompt: str, user_prompt_template: str, max_tasks: int, task_timeout_seconds: int, task_types: tuple[str, ...], mcp_enabled: bool, guardrails: dict[str, object]) -> PlannerConfig:
        result = await self._session.execute(select(PlannerConfigRecord).where(
            PlannerConfigRecord.tenant_id == tenant_id,
            PlannerConfigRecord.knowledge_base_id == knowledge_base_id,
        ))
        row = result.scalar_one_or_none()
        if row is None:
            row = PlannerConfigRecord(id=str(uuid4()), tenant_id=tenant_id, knowledge_base_id=knowledge_base_id)
            self._session.add(row)
        row.enabled = enabled
        row.model_profile_id = model_profile_id
        row.system_prompt = system_prompt
        row.user_prompt_template = user_prompt_template
        row.max_tasks = max_tasks
        row.task_timeout_seconds = task_timeout_seconds
        row.task_types_json = list(task_types)
        row.mcp_enabled = mcp_enabled
        row.guardrails_json = guardrails
        await self._session.commit()
        await self._session.refresh(row)
        return _to_planner_config(row)

    async def delete(self, *, tenant_id: str, knowledge_base_id: str) -> bool:
        result = await self._session.execute(select(PlannerConfigRecord).where(
            PlannerConfigRecord.tenant_id == tenant_id,
            PlannerConfigRecord.knowledge_base_id == knowledge_base_id,
        ))
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.commit()
        return True


# --- Memory ORM models -------------------------------------------------------

class MemoryConfigRecord(Base):
    __tablename__ = "rag_memory_configs"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(
        "knowledge_base_id", Uuid(as_uuid=False),
        ForeignKey("rag_knowledge_bases.id", ondelete="CASCADE"), nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    summarization_model_profile_id: Mapped[str] = mapped_column(
        "summarization_model_profile_id", Uuid(as_uuid=False),
        ForeignKey("rag_model_profiles.id", ondelete="RESTRICT"), nullable=False,
    )
    embedding_profile_id: Mapped[str] = mapped_column(
        "embedding_profile_id", Uuid(as_uuid=False),
        ForeignKey("rag_model_profiles.id", ondelete="RESTRICT"), nullable=False,
    )
    retention_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    retrieval_top_k: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    min_turns_to_summarize: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    system_prompt: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (UniqueConstraint("tenant_id", "knowledge_base_id", name="uq_memory_config_tenant_kb"),)


class MemoryChunkRecord(Base):
    __tablename__ = "rag_memory_chunks"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column(
        "knowledge_base_id", Uuid(as_uuid=False),
        ForeignKey("rag_knowledge_bases.id", ondelete="CASCADE"), nullable=False,
    )
    user_id: Mapped[str] = mapped_column("user_id", Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(
        "conversation_id", Uuid(as_uuid=False),
        ForeignKey("rag_conversations.id", ondelete="SET NULL"), nullable=True,
    )
    summary: Mapped[str] = mapped_column(String, nullable=False)
    qdrant_point_id: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding_profile_id: Mapped[str] = mapped_column(String(120), nullable=False)
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column("expires_at", DateTime(timezone=False), nullable=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)

    __table_args__ = (
        __import__("sqlalchemy").Index("ix_memory_chunks_tenant_kb_user", "tenant_id", "knowledge_base_id", "user_id"),
        __import__("sqlalchemy").Index("ix_memory_chunks_expires_at", "expires_at"),
    )


# --- Memory entity mappers ---------------------------------------------------

def _to_memory_config(row: MemoryConfigRecord) -> "MemoryConfig":
    from app.domain.rag.memory import MemoryConfig
    return MemoryConfig(
        id=row.id,
        tenant_id=row.tenant_id,
        knowledge_base_id=row.knowledge_base_id,
        enabled=row.enabled,
        summarization_model_profile_id=row.summarization_model_profile_id,
        embedding_profile_id=row.embedding_profile_id,
        retention_days=row.retention_days,
        retrieval_top_k=row.retrieval_top_k,
        min_turns_to_summarize=row.min_turns_to_summarize,
        system_prompt=row.system_prompt,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_memory_chunk(row: MemoryChunkRecord) -> "MemoryChunk":
    from app.domain.rag.memory import MemoryChunk
    return MemoryChunk(
        id=row.id,
        tenant_id=row.tenant_id,
        knowledge_base_id=row.knowledge_base_id,
        user_id=row.user_id,
        conversation_id=row.conversation_id,
        summary=row.summary,
        qdrant_point_id=row.qdrant_point_id,
        embedding_profile_id=row.embedding_profile_id,
        turn_count=row.turn_count,
        expires_at=row.expires_at,
        created_at=row.created_at,
    )


# --- Memory repositories -----------------------------------------------------

class SqlAlchemyMemoryConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_knowledge_base(self, *, tenant_id: str, knowledge_base_id: str) -> "MemoryConfig | None":
        result = await self._session.execute(
            select(MemoryConfigRecord).where(
                MemoryConfigRecord.tenant_id == tenant_id,
                MemoryConfigRecord.knowledge_base_id == knowledge_base_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_memory_config(row) if row else None

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
    ) -> "MemoryConfig":
        result = await self._session.execute(
            select(MemoryConfigRecord).where(
                MemoryConfigRecord.tenant_id == tenant_id,
                MemoryConfigRecord.knowledge_base_id == knowledge_base_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = MemoryConfigRecord(
                id=str(uuid4()),
                tenant_id=tenant_id,
                knowledge_base_id=knowledge_base_id,
            )
            self._session.add(row)
        row.enabled = enabled
        row.summarization_model_profile_id = summarization_model_profile_id
        row.embedding_profile_id = embedding_profile_id
        row.retention_days = retention_days
        row.retrieval_top_k = retrieval_top_k
        row.min_turns_to_summarize = min_turns_to_summarize
        row.system_prompt = system_prompt
        await self._session.commit()
        await self._session.refresh(row)
        return _to_memory_config(row)

    async def delete(self, *, tenant_id: str, knowledge_base_id: str) -> bool:
        result = await self._session.execute(
            select(MemoryConfigRecord).where(
                MemoryConfigRecord.tenant_id == tenant_id,
                MemoryConfigRecord.knowledge_base_id == knowledge_base_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.commit()
        return True


class SqlAlchemyMemoryChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_user_kb(
        self,
        *,
        tenant_id: str,
        knowledge_base_id: str,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> list["MemoryChunk"]:
        result = await self._session.execute(
            select(MemoryChunkRecord)
            .where(
                MemoryChunkRecord.tenant_id == tenant_id,
                MemoryChunkRecord.knowledge_base_id == knowledge_base_id,
                MemoryChunkRecord.user_id == user_id,
            )
            .order_by(MemoryChunkRecord.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [_to_memory_chunk(row) for row in result.scalars().all()]

    async def count_by_user_kb(self, *, tenant_id: str, knowledge_base_id: str, user_id: str) -> int:
        from sqlalchemy import func
        result = await self._session.execute(
            select(func.count()).select_from(MemoryChunkRecord).where(
                MemoryChunkRecord.tenant_id == tenant_id,
                MemoryChunkRecord.knowledge_base_id == knowledge_base_id,
                MemoryChunkRecord.user_id == user_id,
            )
        )
        return result.scalar_one()

    async def find_expired(self, *, limit: int = 500) -> list["MemoryChunk"]:
        from datetime import UTC, datetime as dt
        now = dt.now(UTC).replace(tzinfo=None)
        result = await self._session.execute(
            select(MemoryChunkRecord)
            .where(MemoryChunkRecord.expires_at < now)
            .limit(limit)
        )
        return [_to_memory_chunk(row) for row in result.scalars().all()]

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
        expires_at: datetime,
    ) -> "MemoryChunk":
        row = MemoryChunkRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            user_id=user_id,
            conversation_id=conversation_id,
            summary=summary,
            qdrant_point_id=qdrant_point_id,
            embedding_profile_id=embedding_profile_id,
            turn_count=turn_count,
            expires_at=expires_at,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_memory_chunk(row)

    async def delete(self, *, tenant_id: str, chunk_id: str, user_id: str) -> bool:
        result = await self._session.execute(
            select(MemoryChunkRecord).where(
                MemoryChunkRecord.tenant_id == tenant_id,
                MemoryChunkRecord.id == chunk_id,
                MemoryChunkRecord.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.commit()
        return True

    async def delete_by_user_kb(self, *, tenant_id: str, knowledge_base_id: str, user_id: str) -> int:
        from sqlalchemy import delete as sa_delete
        result = await self._session.execute(
            sa_delete(MemoryChunkRecord).where(
                MemoryChunkRecord.tenant_id == tenant_id,
                MemoryChunkRecord.knowledge_base_id == knowledge_base_id,
                MemoryChunkRecord.user_id == user_id,
            )
        )
        await self._session.commit()
        return result.rowcount  # type: ignore[return-value]

    async def delete_by_knowledge_base(self, *, tenant_id: str, knowledge_base_id: str) -> int:
        from sqlalchemy import delete as sa_delete
        result = await self._session.execute(
            sa_delete(MemoryChunkRecord).where(
                MemoryChunkRecord.tenant_id == tenant_id,
                MemoryChunkRecord.knowledge_base_id == knowledge_base_id,
            )
        )
        await self._session.commit()
        return result.rowcount  # type: ignore[return-value]

    async def delete_many(self, *, chunk_ids: list[str]) -> None:
        from sqlalchemy import delete as sa_delete
        if not chunk_ids:
            return
        await self._session.execute(
            sa_delete(MemoryChunkRecord).where(MemoryChunkRecord.id.in_(chunk_ids))
        )
        await self._session.commit()

    async def is_conversation_summarized(self, *, conversation_id: str) -> bool:
        result = await self._session.execute(
            select(MemoryChunkRecord).where(
                MemoryChunkRecord.conversation_id == conversation_id,
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def find_by_id(self, *, tenant_id: str, chunk_id: str) -> "MemoryChunk | None":
        result = await self._session.execute(
            select(MemoryChunkRecord).where(
                MemoryChunkRecord.tenant_id == tenant_id,
                MemoryChunkRecord.id == chunk_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_memory_chunk(row) if row else None


class SqlAlchemyMcpServerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **values: object) -> McpServer:
        row = McpServerRecord(id=str(uuid4()), **values)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_mcp_server(row)

    async def find_by_id(self, *, tenant_id: str, server_id: str) -> McpServer | None:
        result = await self._session.execute(select(McpServerRecord).where(McpServerRecord.tenant_id == tenant_id, McpServerRecord.id == server_id))
        row = result.scalar_one_or_none()
        return _to_mcp_server(row) if row else None

    async def list(self, *, tenant_id: str) -> list[McpServer]:
        result = await self._session.execute(select(McpServerRecord).where(McpServerRecord.tenant_id == tenant_id).order_by(McpServerRecord.name))
        return [_to_mcp_server(row) for row in result.scalars().all()]

    async def update(self, *, tenant_id: str, server_id: str, **changes: object) -> McpServer | None:
        result = await self._session.execute(select(McpServerRecord).where(McpServerRecord.tenant_id == tenant_id, McpServerRecord.id == server_id))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        for key, value in changes.items():
            setattr(row, key, value)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_mcp_server(row)

    async def delete(self, *, tenant_id: str, server_id: str) -> bool:
        result = await self._session.execute(select(McpServerRecord).where(McpServerRecord.tenant_id == tenant_id, McpServerRecord.id == server_id))
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.commit()
        return True


class SqlAlchemyMcpToolRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_discovered(self, *, tenant_id: str, server_id: str, tools: list[McpToolDescriptor], discovered_at: datetime) -> list[McpTool]:
        result = await self._session.execute(select(McpToolRecord).where(McpToolRecord.tenant_id == tenant_id, McpToolRecord.server_id == server_id))
        rows_by_name = {row.name: row for row in result.scalars().all()}
        for row in rows_by_name.values():
            row.is_stale = True
        for descriptor in tools:
            row = rows_by_name.get(descriptor.name)
            if row is None:
                row = McpToolRecord(id=str(uuid4()), tenant_id=tenant_id, server_id=server_id, name=descriptor.name, description=descriptor.description, input_schema=descriptor.input_schema, allowed=False, is_stale=False, last_discovered_at=discovered_at)
                self._session.add(row)
            else:
                row.description = descriptor.description
                row.input_schema = descriptor.input_schema
                row.is_stale = False
                row.last_discovered_at = discovered_at
        await self._session.commit()
        result = await self._session.execute(select(McpToolRecord).where(McpToolRecord.tenant_id == tenant_id, McpToolRecord.server_id == server_id))
        return [_to_mcp_tool(row) for row in result.scalars().all()]

    async def list(self, *, tenant_id: str, server_id: str, include_stale: bool = False) -> list[McpTool]:
        statement = select(McpToolRecord).where(McpToolRecord.tenant_id == tenant_id, McpToolRecord.server_id == server_id)
        if not include_stale:
            statement = statement.where(McpToolRecord.is_stale == False)  # noqa: E712
        result = await self._session.execute(statement.order_by(McpToolRecord.name))
        return [_to_mcp_tool(row) for row in result.scalars().all()]

    async def find_by_id(self, *, tenant_id: str, tool_id: str) -> McpTool | None:
        result = await self._session.execute(select(McpToolRecord).where(McpToolRecord.tenant_id == tenant_id, McpToolRecord.id == tool_id))
        row = result.scalar_one_or_none()
        return _to_mcp_tool(row) if row else None

    async def set_allowed(self, *, tenant_id: str, tool_id: str, allowed: bool) -> McpTool | None:
        result = await self._session.execute(select(McpToolRecord).where(McpToolRecord.tenant_id == tenant_id, McpToolRecord.id == tool_id))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.allowed = allowed
        await self._session.commit()
        await self._session.refresh(row)
        return _to_mcp_tool(row)


class SqlAlchemyMcpInvocationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **values: object) -> McpInvocation:
        row = McpInvocationRecord(id=str(uuid4()), **values)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_mcp_invocation(row)

    async def list(self, *, tenant_id: str, server_id: str | None = None, status: McpInvocationStatus | None = None, user_id: str | None = None, created_after: datetime | None = None, created_before: datetime | None = None, limit: int = 100) -> list[McpInvocation]:
        statement = select(McpInvocationRecord).where(McpInvocationRecord.tenant_id == tenant_id)
        if server_id is not None:
            statement = statement.where(McpInvocationRecord.server_id == server_id)
        if status is not None:
            statement = statement.where(McpInvocationRecord.status == status)
        if user_id is not None:
            statement = statement.where(McpInvocationRecord.user_id == user_id)
        if created_after is not None:
            statement = statement.where(McpInvocationRecord.created_at >= created_after)
        if created_before is not None:
            statement = statement.where(McpInvocationRecord.created_at <= created_before)
        result = await self._session.execute(statement.order_by(McpInvocationRecord.created_at.desc()).limit(limit))
        return [_to_mcp_invocation(row) for row in result.scalars().all()]

    async def prune(self, *, tenant_id: str, before: datetime) -> int:
        from sqlalchemy import delete as sa_delete
        result = await self._session.execute(sa_delete(McpInvocationRecord).where(McpInvocationRecord.tenant_id == tenant_id, McpInvocationRecord.created_at < before))
        await self._session.commit()
        return cast(int, result.rowcount or 0)


# --- RagQueryJob ORM + Repository --------------------------------------------


class RagQueryJobRecord(Base):
    __tablename__ = "rag_query_jobs"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    request: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    webhook_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_rag_query_jobs_tenant_id", "tenant_id"),
        Index("ix_rag_query_jobs_status", "status"),
    )


def _to_rag_query_job(row: RagQueryJobRecord) -> "RagQueryJob":
    from app.domain.rag.query_job import RagQueryJob, RagQueryJobStatus
    return RagQueryJob(
        id=row.id,
        tenant_id=row.tenant_id,
        user_id=row.user_id,
        status=RagQueryJobStatus(row.status),
        request=dict(row.request),
        result=dict(row.result) if row.result is not None else None,
        error=row.error,
        webhook_url=row.webhook_url,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


class SqlAlchemyRagQueryJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, job: "RagQueryJob") -> None:
        row = RagQueryJobRecord(
            id=job.id,
            tenant_id=job.tenant_id,
            user_id=job.user_id,
            status=job.status.value,
            request=job.request,
            result=job.result,
            error=job.error,
            webhook_url=job.webhook_url,
            created_at=job.created_at,
            completed_at=job.completed_at,
        )
        self._session.add(row)
        await self._session.commit()

    async def get_by_id_and_tenant(self, job_id: str, tenant_id: str) -> "RagQueryJob | None":
        result = await self._session.execute(
            select(RagQueryJobRecord).where(
                RagQueryJobRecord.id == job_id,
                RagQueryJobRecord.tenant_id == tenant_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_rag_query_job(row) if row else None

    async def update_running(self, job_id: str) -> None:
        result = await self._session.execute(
            select(RagQueryJobRecord).where(RagQueryJobRecord.id == job_id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            row.status = "running"
            await self._session.commit()

    async def update_completed(self, job_id: str, result_data: dict) -> None:
        result = await self._session.execute(
            select(RagQueryJobRecord).where(RagQueryJobRecord.id == job_id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            row.status = "completed"
            row.result = result_data
            row.completed_at = utc_now()
            await self._session.commit()

    async def update_failed(self, job_id: str, error: str) -> None:
        result = await self._session.execute(
            select(RagQueryJobRecord).where(RagQueryJobRecord.id == job_id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            row.status = "failed"
            row.error = error
            row.completed_at = utc_now()
            await self._session.commit()
