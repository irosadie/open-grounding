"""add metadata_json to document versions

Revision ID: 20260807_09
Revises: 20260807_08
Create Date: 2026-08-07

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260807_09"
down_revision = "20260807_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rag_document_versions",
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("rag_document_versions", "metadata_json")
