"""Add rag_provider_credentials table for encrypted provider API keys.

Revision ID: 20260805_02
Revises: 20260805_01
Create Date: 2026-08-05
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260805_02"
down_revision = "20260805_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_provider_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("provider", sa.String(60), nullable=False),
        sa.Column("key_name", sa.String(120), nullable=False),
        sa.Column("value_enc", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "provider", "key_name", name="uq_provider_credentials_tenant_provider_key"),
    )
    op.create_index("ix_rag_provider_credentials_tenant_id", "rag_provider_credentials", ["tenant_id"])
    op.create_index("ix_rag_provider_credentials_provider", "rag_provider_credentials", ["tenant_id", "provider"])


def downgrade() -> None:
    op.drop_index("ix_rag_provider_credentials_provider", table_name="rag_provider_credentials")
    op.drop_index("ix_rag_provider_credentials_tenant_id", table_name="rag_provider_credentials")
    op.drop_table("rag_provider_credentials")
