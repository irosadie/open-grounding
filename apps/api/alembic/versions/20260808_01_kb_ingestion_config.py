"""Add rag_kb_ingestion_configs table.

Revision ID: 20260808_01
Revises: 20260807_10
Create Date: 2026-08-08

Additive migration creating rag_kb_ingestion_configs with a FK to
rag_knowledge_bases. One row per KB, upsert semantics enforced by a unique
constraint on (tenant_id, knowledge_base_id). All threshold columns have
safe defaults matching QualityGate constructor defaults.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260808_01"
down_revision = "20260807_10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_kb_ingestion_configs",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "knowledge_base_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("rag_knowledge_bases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("min_text_coverage", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("max_invalid_char_ratio", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("min_aggregate_confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("min_page_coverage", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("auto_review", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.UniqueConstraint("tenant_id", "knowledge_base_id", name="uq_ingestion_config_tenant_kb"),
    )
    op.create_index(
        "ix_ingestion_config_kb",
        "rag_kb_ingestion_configs",
        ["knowledge_base_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_config_kb", table_name="rag_kb_ingestion_configs")
    op.drop_table("rag_kb_ingestion_configs")
