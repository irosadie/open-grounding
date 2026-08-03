"""Add the tenant-scoped RAG knowledge-catalog tables.

Revision ID: 20260803_01
Revises: 20260801_01
Create Date: 2026-08-03

Additive migration creating nine tenant-owned catalog tables. Every table
carries a non-null tenant_id FK to tenants.id, tenant-local uniqueness, and
indexes for tenant-scoped lookups. Document versions are immutable; index
generations are versioned and never overwrite an active generation in place.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260803_01"
down_revision = "20260801_01"
branch_labels = None
depends_on = None

TENANT_FK = "tenant_id"
_VSTATES = [
    "RECEIVED", "STORED", "QUEUED", "PARSING", "NORMALIZING", "CLASSIFYING", "CHUNKING",
    "EMBEDDING", "INDEXING", "VALIDATING", "READY", "REJECTED", "QUARANTINED", "NEEDS_REVIEW",
    "FAILED", "SUPERSEDED", "DELETING", "DELETED",
]


def upgrade() -> None:
    bind = op.get_bind()
    kb = postgresql.ENUM("ACTIVE", "ARCHIVED", "DELETED", name="KnowledgeBaseStatus", create_type=False)
    st = postgresql.ENUM("UPLOAD", "CONNECTOR", name="KnowledgeSourceType", create_type=False)
    vs = postgresql.ENUM(*_VSTATES, name="DocumentVersionLifecycleState", create_type=False)
    gs = postgresql.ENUM("PENDING", "ACTIVE", "FAILED", "SUPERSEDED", "DELETING", "DELETED", name="IndexGenerationStatus", create_type=False)
    js = postgresql.ENUM("PENDING", "RUNNING", "COMPLETED", "FAILED", name="IngestionJobStatus", create_type=False)
    os_ = postgresql.ENUM("PENDING", "DISPATCHED", "FAILED", name="OutboxEventStatus", create_type=False)
    for enum in (kb, st, vs, gs, js, os_):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "rag_knowledge_bases",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", kb, nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint([TENANT_FK], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_rag_knowledge_bases_tenant_slug"),
    )
    op.create_index("ix_rag_knowledge_bases_tenant_id", "rag_knowledge_bases", [TENANT_FK])
    op.create_index("ix_rag_knowledge_bases_status", "rag_knowledge_bases", ["status"])

    op.create_table(
        "rag_knowledge_sources",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("source_type", st, nullable=False, server_default="UPLOAD"),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("config_ref", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint([TENANT_FK], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["rag_knowledge_bases.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_rag_knowledge_sources_tenant_id", "rag_knowledge_sources", [TENANT_FK])

    op.create_table(
        "rag_documents",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint([TENANT_FK], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["rag_knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["rag_knowledge_sources.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_rag_documents_tenant_id", "rag_documents", [TENANT_FK])

    op.create_table(
        "rag_document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("lifecycle_state", vs, nullable=False, server_default="RECEIVED"),
        sa.Column("content_checksum", sa.String(128), nullable=False),
        sa.Column("source_revision", sa.String(512), nullable=True),
        sa.Column("pipeline_fingerprint", sa.String(512), nullable=True),
        sa.Column("object_key_raw", sa.String(1024), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("mime_type", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint([TENANT_FK], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["rag_documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "document_id", "version_number", name="uq_rag_doc_versions_tenant_doc_version"),
    )
    op.create_index("ix_rag_document_versions_tenant_id", "rag_document_versions", [TENANT_FK])
    op.create_index("ix_rag_document_versions_doc_id", "rag_document_versions", ["document_id"])

    op.create_table(
        "rag_model_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("profile_kind", sa.String(60), nullable=False),
        sa.Column("provider", sa.String(255), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=True),
        sa.Column("version", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint([TENANT_FK], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_rag_model_profiles_tenant_id", "rag_model_profiles", [TENANT_FK])

    op.create_table(
        "rag_index_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("embedding_profile_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("sparse_profile_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("collection", sa.String(255), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("distance_metric", sa.String(50), nullable=False),
        sa.Column("version", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint([TENANT_FK], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["embedding_profile_id"], ["rag_model_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sparse_profile_id"], ["rag_model_profiles.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_rag_index_profiles_tenant_id", "rag_index_profiles", [TENANT_FK])

    op.create_table(
        "rag_index_generations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("index_profile_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("status", gs, nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint([TENANT_FK], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_version_id"], ["rag_document_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["index_profile_id"], ["rag_index_profiles.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_rag_index_generations_tenant_id", "rag_index_generations", [TENANT_FK])
    op.create_index("ix_rag_index_generations_status", "rag_index_generations", ["status"])

    op.create_table(
        "rag_ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("generation_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("stage", sa.String(120), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(512), nullable=False),
        sa.Column("trace_id", sa.String(120), nullable=True),
        sa.Column("status", js, nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint([TENANT_FK], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_version_id"], ["rag_document_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generation_id"], ["rag_index_generations.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_rag_ingestion_jobs_tenant_idem"),
    )
    op.create_index("ix_rag_ingestion_jobs_tenant_id", "rag_ingestion_jobs", [TENANT_FK])

    op.create_table(
        "rag_outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("resource_id", sa.String(512), nullable=True),
        sa.Column("generation_id", sa.String(512), nullable=True),
        sa.Column("idempotency_key", sa.String(512), nullable=False),
        sa.Column("trace_id", sa.String(120), nullable=True),
        sa.Column("payload", postgresql.JSON(), nullable=False),
        sa.Column("status", os_, nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("dispatched_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint([TENANT_FK], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_rag_outbox_events_tenant_id", "rag_outbox_events", [TENANT_FK])
    op.create_index("ix_rag_outbox_events_status", "rag_outbox_events", ["status"])


def downgrade() -> None:
    op.drop_index("ix_rag_outbox_events_status", table_name="rag_outbox_events")
    op.drop_index("ix_rag_outbox_events_tenant_id", table_name="rag_outbox_events")
    op.drop_table("rag_outbox_events")
    op.drop_index("ix_rag_ingestion_jobs_tenant_id", table_name="rag_ingestion_jobs")
    op.drop_table("rag_ingestion_jobs")
    op.drop_index("ix_rag_index_generations_status", table_name="rag_index_generations")
    op.drop_index("ix_rag_index_generations_tenant_id", table_name="rag_index_generations")
    op.drop_table("rag_index_generations")
    op.drop_index("ix_rag_index_profiles_tenant_id", table_name="rag_index_profiles")
    op.drop_table("rag_index_profiles")
    op.drop_index("ix_rag_model_profiles_tenant_id", table_name="rag_model_profiles")
    op.drop_table("rag_model_profiles")
    op.drop_index("ix_rag_document_versions_doc_id", table_name="rag_document_versions")
    op.drop_index("ix_rag_document_versions_tenant_id", table_name="rag_document_versions")
    op.drop_table("rag_document_versions")
    op.drop_index("ix_rag_documents_tenant_id", table_name="rag_documents")
    op.drop_table("rag_documents")
    op.drop_index("ix_rag_knowledge_sources_tenant_id", table_name="rag_knowledge_sources")
    op.drop_table("rag_knowledge_sources")
    op.drop_index("ix_rag_knowledge_bases_status", table_name="rag_knowledge_bases")
    op.drop_index("ix_rag_knowledge_bases_tenant_id", table_name="rag_knowledge_bases")
    op.drop_table("rag_knowledge_bases")
    for name in ("OutboxEventStatus", "IngestionJobStatus", "IndexGenerationStatus", "DocumentVersionLifecycleState", "KnowledgeSourceType", "KnowledgeBaseStatus"):
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
