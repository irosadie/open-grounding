"""Prepare catalog and answer traces for document hard deletion.

The original answer-trace schema made both source references non-null and
therefore prevented deleting a document version while preserving answer
history. Document rows also lacked a soft-delete marker. This migration makes
those references nullable so the delete worker can retain trace rows while
removing the source graph.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260918_03"
down_revision = "20260918_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rag_documents",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    with op.batch_alter_table("rag_index_generations") as batch_op:
        batch_op.drop_constraint(
            "rag_index_generations_document_version_id_fkey",
            type_="foreignkey",
        )
        batch_op.alter_column("document_version_id", existing_type=sa.UUID(as_uuid=False), nullable=True)
        batch_op.create_foreign_key(
            "fk_rag_index_generations_document_version_id",
            "rag_document_versions",
            ["document_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.alter_column(
        "rag_answer_citations",
        "chunk_id",
        existing_type=sa.UUID(as_uuid=False),
        nullable=True,
    )
    op.alter_column(
        "rag_answer_citations",
        "document_version_id",
        existing_type=sa.UUID(as_uuid=False),
        nullable=True,
    )
    op.alter_column(
        "rag_selected_evidence",
        "chunk_id",
        existing_type=sa.UUID(as_uuid=False),
        nullable=True,
    )


def downgrade() -> None:
    with op.batch_alter_table("rag_index_generations") as batch_op:
        batch_op.drop_constraint(
            "fk_rag_index_generations_document_version_id",
            type_="foreignkey",
        )
        batch_op.alter_column("document_version_id", existing_type=sa.UUID(as_uuid=False), nullable=False)
        batch_op.create_foreign_key(
            "rag_index_generations_document_version_id_fkey",
            "rag_document_versions",
            ["document_version_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.alter_column(
        "rag_selected_evidence",
        "chunk_id",
        existing_type=sa.UUID(as_uuid=False),
        nullable=False,
    )
    op.alter_column(
        "rag_answer_citations",
        "document_version_id",
        existing_type=sa.UUID(as_uuid=False),
        nullable=False,
    )
    op.alter_column(
        "rag_answer_citations",
        "chunk_id",
        existing_type=sa.UUID(as_uuid=False),
        nullable=False,
    )
    op.drop_column("rag_documents", "deleted_at")
