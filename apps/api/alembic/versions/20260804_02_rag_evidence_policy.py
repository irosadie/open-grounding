"""Add server-enforced RAG evidence policy metadata.

Revision ID: 20260804_02
Revises: 20260804_01
Create Date: 2026-08-04
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260804_02"
down_revision = "20260804_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    classification = postgresql.ENUM("PUBLIC", "INTERNAL", "CONFIDENTIAL", name="Classification", create_type=False)
    classification.create(op.get_bind(), checkfirst=True)
    op.add_column("rag_document_versions", sa.Column("classification", classification, nullable=False, server_default="INTERNAL"))
    op.add_column("rag_document_versions", sa.Column("acl_principals", postgresql.JSON(), nullable=False, server_default=sa.text("'[]'::json")))
    op.add_column("rag_document_versions", sa.Column("effective_from", sa.DateTime(), nullable=True))
    op.add_column("rag_document_versions", sa.Column("effective_to", sa.DateTime(), nullable=True))
    op.create_index("ix_rag_document_versions_classification", "rag_document_versions", ["classification"])


def downgrade() -> None:
    op.drop_index("ix_rag_document_versions_classification", table_name="rag_document_versions")
    op.drop_column("rag_document_versions", "effective_to")
    op.drop_column("rag_document_versions", "effective_from")
    op.drop_column("rag_document_versions", "acl_principals")
    op.drop_column("rag_document_versions", "classification")
    postgresql.ENUM(name="Classification").drop(op.get_bind(), checkfirst=True)
