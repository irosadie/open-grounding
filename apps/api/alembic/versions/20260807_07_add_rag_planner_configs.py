"""add_rag_planner_configs

Revision ID: 20260807_07
Revises: 20260806_06
Create Date: 2026-08-07 06:35:49.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20260807_07'
down_revision = '20260806_06'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'rag_planner_configs',
        sa.Column('id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('tenant_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('knowledge_base_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('model_profile_id', sa.UUID(as_uuid=False), nullable=False),
        sa.Column('system_prompt', sa.String(), nullable=False),
        sa.Column('user_prompt_template', sa.String(), nullable=False),
        sa.Column('max_tasks', sa.Integer(), nullable=False, server_default=sa.text('4')),
        sa.Column('task_timeout_seconds', sa.Integer(), nullable=False, server_default=sa.text('15')),
        sa.Column('task_types_json', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('mcp_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('guardrails_json', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=False), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=False), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['rag_knowledge_bases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['model_profile_id'], ['rag_model_profiles.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'knowledge_base_id', name='uq_planner_config_tenant_kb'),
    )
    op.create_index('ix_rag_planner_configs_tenant_id', 'rag_planner_configs', ['tenant_id'], unique=False)
    op.create_index('ix_rag_planner_configs_kb_id', 'rag_planner_configs', ['knowledge_base_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_rag_planner_configs_kb_id', table_name='rag_planner_configs')
    op.drop_index('ix_rag_planner_configs_tenant_id', table_name='rag_planner_configs')
    op.drop_table('rag_planner_configs')
