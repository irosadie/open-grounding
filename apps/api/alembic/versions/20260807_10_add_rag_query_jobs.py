"""add rag_query_jobs table

Revision ID: 20260807_10
Revises: 20260807_09
Create Date: 2026-08-07

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260807_10"
down_revision = "20260807_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_query_jobs",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("request", postgresql.JSONB(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("webhook_url", sa.String(2048), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_rag_query_jobs_tenant_id", "rag_query_jobs", ["tenant_id"])
    op.create_index("ix_rag_query_jobs_status", "rag_query_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_rag_query_jobs_status", table_name="rag_query_jobs")
    op.drop_index("ix_rag_query_jobs_tenant_id", table_name="rag_query_jobs")
    op.drop_table("rag_query_jobs")
