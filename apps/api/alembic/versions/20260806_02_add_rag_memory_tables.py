"""add_rag_memory_tables

Revision ID: 20260806_02
Revises: 20260806_01
Create Date: 2026-08-06 21:02:01.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '20260806_02'
down_revision = '20260806_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # rag_memory_configs
    op.create_table(
        'rag_memory_configs',
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('tenant_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('knowledge_base_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('summarization_model_profile_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('embedding_profile_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('retention_days', sa.Integer(), nullable=False, server_default='90'),
        sa.Column('retrieval_top_k', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('min_turns_to_summarize', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('system_prompt', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=False), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['rag_knowledge_bases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['summarization_model_profile_id'], ['rag_model_profiles.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['embedding_profile_id'], ['rag_model_profiles.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'knowledge_base_id', name='uq_memory_config_tenant_kb'),
    )

    # rag_memory_chunks
    op.create_table(
        'rag_memory_chunks',
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('tenant_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('knowledge_base_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('conversation_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('summary', sa.String(), nullable=False),
        sa.Column('qdrant_point_id', sa.String(120), nullable=False),
        sa.Column('embedding_profile_id', sa.String(120), nullable=False),
        sa.Column('turn_count', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['rag_knowledge_bases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conversation_id'], ['rag_conversations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_memory_chunks_tenant_kb_user', 'rag_memory_chunks', ['tenant_id', 'knowledge_base_id', 'user_id'])
    op.create_index('ix_memory_chunks_expires_at', 'rag_memory_chunks', ['expires_at'])

    # add summarized column to rag_conversations
    op.add_column('rag_conversations', sa.Column('summarized', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('rag_conversations', 'summarized')
    op.drop_index('ix_memory_chunks_expires_at', table_name='rag_memory_chunks')
    op.drop_index('ix_memory_chunks_tenant_kb_user', table_name='rag_memory_chunks')
    op.drop_table('rag_memory_chunks')
    op.drop_table('rag_memory_configs')
