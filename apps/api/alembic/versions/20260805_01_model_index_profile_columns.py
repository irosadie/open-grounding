"""Add name, modality, config_json to model profiles; add name, reranker, chunking to index profiles.

Revision ID: 20260805_01
Revises: 20260804_03
Create Date: 2026-08-05
"""

import sqlalchemy as sa

from alembic import op

revision = "20260805_01"
down_revision = "20260804_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # rag_model_profiles — add name, modality, config_json
    op.add_column("rag_model_profiles", sa.Column("name", sa.String(255), nullable=True))
    op.add_column("rag_model_profiles", sa.Column("modality", sa.String(60), nullable=True, server_default="TEXT"))
    op.add_column("rag_model_profiles", sa.Column("config_json", sa.Text(), nullable=True))

    # backfill name from model column for existing rows
    op.execute("UPDATE rag_model_profiles SET name = model WHERE name IS NULL")

    # make name non-nullable after backfill
    op.alter_column("rag_model_profiles", "name", nullable=False)

    # rag_index_profiles — add name, reranker_profile_id, chunking fields
    op.add_column("rag_index_profiles", sa.Column("name", sa.String(255), nullable=True))
    op.add_column(
        "rag_index_profiles",
        sa.Column(
            "reranker_profile_id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            sa.ForeignKey("rag_model_profiles.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column("rag_index_profiles", sa.Column("chunking_strategy", sa.String(60), nullable=True, server_default="RECURSIVE"))
    op.add_column("rag_index_profiles", sa.Column("chunk_size_tokens", sa.Integer(), nullable=True, server_default="400"))
    op.add_column("rag_index_profiles", sa.Column("chunk_overlap_tokens", sa.Integer(), nullable=True, server_default="50"))
    op.add_column("rag_index_profiles", sa.Column("parent_chunk_size", sa.Integer(), nullable=True, server_default="1500"))

    # backfill name for existing index profiles
    op.execute("UPDATE rag_index_profiles SET name = collection WHERE name IS NULL")
    op.alter_column("rag_index_profiles", "name", nullable=False)

    # indexes
    op.create_index("ix_rag_model_profiles_is_active", "rag_model_profiles", ["is_active"])
    op.create_index("ix_rag_index_profiles_is_active", "rag_index_profiles", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_rag_index_profiles_is_active", table_name="rag_index_profiles")
    op.drop_index("ix_rag_model_profiles_is_active", table_name="rag_model_profiles")

    op.drop_column("rag_index_profiles", "parent_chunk_size")
    op.drop_column("rag_index_profiles", "chunk_overlap_tokens")
    op.drop_column("rag_index_profiles", "chunk_size_tokens")
    op.drop_column("rag_index_profiles", "chunking_strategy")
    op.drop_column("rag_index_profiles", "reranker_profile_id")
    op.drop_column("rag_index_profiles", "name")

    op.drop_column("rag_model_profiles", "config_json")
    op.drop_column("rag_model_profiles", "modality")
    op.drop_column("rag_model_profiles", "name")
