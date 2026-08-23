"""Add tenants and tenant_memberships tables with indexes and constraints.

Revision ID: 20260801_01
Revises: 20260729_01
Create Date: 2026-08-01

This is an additive migration — it creates two new tables without modifying
existing users or auth_sessions. Required indexes and a unique constraint on
(tenant_id, user_id) prevent duplicate memberships and support tenant-scoped
lookups.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260801_01"
down_revision = "20260729_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tenant_status = postgresql.ENUM("ACTIVE", "DISABLED", name="TenantStatus", create_type=False)
    membership_status = postgresql.ENUM("ACTIVE", "INACTIVE", name="TenantMembershipStatus", create_type=False)
    tenant_status.create(op.get_bind(), checkfirst=True)
    membership_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", tenant_status, nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tenants_status", "tenants", ["status"])

    op.create_table(
        "tenant_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("status", membership_status, nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_tenant_memberships_tenant_user"),
    )
    op.create_index("ix_tenant_memberships_tenant_id", "tenant_memberships", ["tenant_id"])
    op.create_index("ix_tenant_memberships_user_id", "tenant_memberships", ["user_id"])
    op.create_index("ix_tenant_memberships_status", "tenant_memberships", ["status"])


def downgrade() -> None:
    op.drop_index("ix_tenant_memberships_status", table_name="tenant_memberships")
    op.drop_index("ix_tenant_memberships_user_id", table_name="tenant_memberships")
    op.drop_index("ix_tenant_memberships_tenant_id", table_name="tenant_memberships")
    op.drop_table("tenant_memberships")
    op.drop_index("ix_tenants_status", table_name="tenants")
    op.drop_table("tenants")
    postgresql.ENUM(name="TenantMembershipStatus").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="TenantStatus").drop(op.get_bind(), checkfirst=True)
