"""Add rag_chunks and rag_stage_checkpoints tables for the ingestion pipeline.

Revision ID: 20260803_02
Revises: 20260803_01
Create Date: 2026-08-03

Additive migration. Creates chunk manifests (parent-child retrieval units with
lineage) and stage checkpoints (resumable pipeline progress with recovery
metadata). Both are tenant-scoped with FKs to the catalog tables.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260803_02"
down_revision = "20260803_01"
branch_labels = None
depends_on = None

TENANT_FK = "tenant_id"


def upgrade() -> None:
    bind = op.get_bind()
    chunk_type = postgresql.ENUM("PARENT", "CHILD", name="ChunkType", create_type=False)
    checkpoint_status = postgresql.ENUM(
        "PENDING", "IN_PROGRESS", "COMPLETED", "FAILED", "SKIPPED",
        name="StageCheckpointStatus", create_type=False,
    )
    chunk_type.create(bind, checkfirst=True)
    checkpoint_status.create(bind, checkfirst=True)

    op.create_table(
        "rag_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("generation_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("chunk_type", chunk_type, nullable=False, server_default="CHILD"),
        sa.Column("hierarchy_path", postgresql.JSON(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(60), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("source_offsets_start", sa.Integer(), nullable=True),
        sa.Column("source_offsets_end", sa.Integer(), nullable=True),
        sa.Column("chunker_version", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint([TENANT_FK], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_version_id"], ["rag_document_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generation_id"], ["rag_index_generations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["rag_chunks.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_rag_chunks_tenant_id", "rag_chunks", [TENANT_FK])
    op.create_index("ix_rag_chunks_generation_id", "rag_chunks", ["generation_id"])

    op.create_table(
        "rag_stage_checkpoints",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("generation_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("stage", sa.String(120), nullable=False),
        sa.Column("status", checkpoint_status, nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(512), nullable=False),
        sa.Column("trace_id", sa.String(120), nullable=True),
        sa.Column("checkpoint_data", postgresql.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint([TENANT_FK], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_version_id"], ["rag_document_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generation_id"], ["rag_index_generations.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "document_version_id", "stage", name="uq_rag_checkpoints_tenant_version_stage"),
    )
    op.create_index("ix_rag_stage_checkpoints_tenant_id", "rag_stage_checkpoints", [TENANT_FK])


def downgrade() -> None:
    op.drop_index("ix_rag_stage_checkpoints_tenant_id", table_name="rag_stage_checkpoints")
    op.drop_table("rag_stage_checkpoints")
    op.drop_index("ix_rag_chunks_generation_id", table_name="rag_chunks")
    op.drop_index("ix_rag_chunks_tenant_id", table_name="rag_chunks")
    op.drop_table("rag_chunks")
    postgresql.ENUM(name="StageCheckpointStatus").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="ChunkType").drop(op.get_bind(), checkfirst=True)
