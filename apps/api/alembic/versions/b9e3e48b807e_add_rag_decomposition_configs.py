"""add_rag_decomposition_configs

Revision ID: b9e3e48b807e
Revises: 20260805_02
Create Date: 2026-08-06 03:44:36.487325
"""
from alembic import op
import sqlalchemy as sa

revision = 'b9e3e48b807e'
down_revision = '20260805_02'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'rag_decomposition_configs',
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('tenant_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('knowledge_base_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('model_profile_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('system_prompt', sa.String(), nullable=False),
        sa.Column('user_prompt_template', sa.String(), nullable=False),
        sa.Column('max_sub_queries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('max_depth', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('min_complexity_score', sa.Float(), nullable=False, server_default='0.6'),
        sa.Column('guardrails_json', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['rag_knowledge_bases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['model_profile_id'], ['rag_model_profiles.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'knowledge_base_id', name='uq_decomp_config_tenant_kb'),
    )

def downgrade() -> None:
    op.drop_table('rag_decomposition_configs')
