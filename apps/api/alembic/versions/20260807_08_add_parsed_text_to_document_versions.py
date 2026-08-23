"""add parsed_text to document versions

Revision ID: 20260807_08_add_parsed_text_to_document_versions
Revises: 20260807_07_add_rag_planner_configs
Create Date: 2026-08-07

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260807_08"
down_revision = "20260807_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rag_document_versions",
        sa.Column("parsed_text", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("rag_document_versions", "parsed_text")
