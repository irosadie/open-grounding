"""Add bounded RAG conversation message history.

Revision ID: 20260804_03
Revises: 20260804_02
Create Date: 2026-08-04
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260804_03"
down_revision = "20260804_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    speaker = postgresql.ENUM("USER", "ASSISTANT", name="ConversationSpeaker", create_type=False)
    speaker.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "rag_conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("speaker", speaker, nullable=False),
        sa.Column("content", sa.String(8_000), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["rag_conversations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_rag_conversation_messages_tenant_conversation", "rag_conversation_messages", ["tenant_id", "conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_rag_conversation_messages_tenant_conversation", table_name="rag_conversation_messages")
    op.drop_table("rag_conversation_messages")
    postgresql.ENUM(name="ConversationSpeaker").drop(op.get_bind(), checkfirst=True)
