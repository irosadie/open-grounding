"""add rag planner configs

Revision ID: 20260806_03
Revises: b9e3e48b807e
"""

from alembic import op
import sqlalchemy as sa

revision = "20260806_03"
down_revision = ("20260806_02", "20260806_04")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_planner_configs",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("model_profile_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("system_prompt", sa.String(), nullable=False),
        sa.Column("user_prompt_template", sa.String(), nullable=False),
        sa.Column("max_tasks", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("task_timeout_seconds", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("task_types_json", sa.JSON(), nullable=False, server_default='["RAG", "MCP", "GENERAL"]'),
        sa.Column("mcp_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("guardrails_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["rag_knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_profile_id"], ["rag_model_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "knowledge_base_id", name="uq_planner_config_tenant_kb"),
    )


def downgrade() -> None:
    op.drop_table("rag_planner_configs")
