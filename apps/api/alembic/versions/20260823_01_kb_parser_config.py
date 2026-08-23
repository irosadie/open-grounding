"""Add parser and docling_serve_url columns to rag_kb_ingestion_configs.

Revision ID: 20260823_01
Revises: 20260808_01
Create Date: 2026-08-23

Additive migration adding two columns to rag_kb_ingestion_configs:
- parser: VARCHAR(32) NOT NULL DEFAULT 'auto' — controls which parser adapter
  is used for ingestion jobs in this KB.
- docling_serve_url: VARCHAR(2048) NULL — optional KB-level override for the
  docling-serve base URL. Only used when parser='docling_serve'.

Existing rows get parser='auto' and docling_serve_url=NULL, preserving
current behaviour unchanged.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260823_01"
down_revision = "20260808_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rag_kb_ingestion_configs",
        sa.Column(
            "parser",
            sa.String(32),
            nullable=False,
            server_default="auto",
        ),
    )
    op.add_column(
        "rag_kb_ingestion_configs",
        sa.Column(
            "docling_serve_url",
            sa.String(2048),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("rag_kb_ingestion_configs", "docling_serve_url")
    op.drop_column("rag_kb_ingestion_configs", "parser")
