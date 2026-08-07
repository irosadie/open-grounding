"""Add MCP server, tool registry, and invocation audit tables."""

import sqlalchemy as sa

from alembic import op

revision = "20260806_04"
down_revision = "20260806_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DO $$ BEGIN CREATE TYPE \"McpTransport\" AS ENUM ('stdio', 'http', 'sse'); EXCEPTION WHEN duplicate_object THEN NULL; END $$"))
    bind.execute(sa.text("DO $$ BEGIN CREATE TYPE \"McpServerStatus\" AS ENUM ('unknown', 'connected', 'error'); EXCEPTION WHEN duplicate_object THEN NULL; END $$"))
    bind.execute(sa.text("DO $$ BEGIN CREATE TYPE \"McpInvocationStatus\" AS ENUM ('success', 'error', 'timeout', 'denied'); EXCEPTION WHEN duplicate_object THEN NULL; END $$"))

    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("transport", sa.Text(), nullable=False),
        sa.Column("command", sa.String(1024), nullable=True),
        sa.Column("args", sa.JSON(), nullable=False),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("auth_type", sa.String(20), nullable=True),
        sa.Column("credential_ref", sa.String(255), nullable=True),
        sa.Column("headers_json", sa.JSON(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_payload_bytes", sa.Integer(), nullable=False, server_default="1048576"),
        sa.Column("allow_insecure", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("last_error", sa.String(2048), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mcp_servers_tenant_id", "mcp_servers", ["tenant_id"])

    op.create_table(
        "mcp_tools",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("server_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(4000), nullable=False),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_discovered_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["server_id"], ["mcp_servers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "server_id", "name", name="uq_mcp_tools_tenant_server_name"),
    )
    op.create_index("ix_mcp_tools_tenant_server", "mcp_tools", ["tenant_id", "server_id"])

    op.create_table(
        "mcp_invocations",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("server_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("tool_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("args_json", sa.JSON(), nullable=False),
        sa.Column("args_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("result_text", sa.String(4096), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["server_id"], ["mcp_servers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tool_id"], ["mcp_tools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "created_at", name="uq_mcp_invocations_tenant_created_at"),
    )
    op.create_index("ix_mcp_invocations_tenant_created_at", "mcp_invocations", ["tenant_id", "created_at"])
    op.create_index("ix_mcp_invocations_tenant_server_status", "mcp_invocations", ["tenant_id", "server_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_mcp_invocations_tenant_server_status", table_name="mcp_invocations")
    op.drop_index("ix_mcp_invocations_tenant_created_at", table_name="mcp_invocations")
    op.drop_table("mcp_invocations")
    op.drop_index("ix_mcp_tools_tenant_server", table_name="mcp_tools")
    op.drop_table("mcp_tools")
    op.drop_index("ix_mcp_servers_tenant_id", table_name="mcp_servers")
    op.drop_table("mcp_servers")
    bind = op.get_bind()
    sa.Enum(name="McpInvocationStatus").drop(bind, checkfirst=True)
    sa.Enum(name="McpServerStatus").drop(bind, checkfirst=True)
    sa.Enum(name="McpTransport").drop(bind, checkfirst=True)
