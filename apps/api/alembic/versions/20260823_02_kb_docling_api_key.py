"""Add docling_serve_api_key_enc column to rag_kb_ingestion_configs.

Revision ID: 20260823_02
Revises: 20260823_01
Create Date: 2026-08-23

Additive migration adding one column to rag_kb_ingestion_configs:
- docling_serve_api_key_enc: TEXT NULL — AES-256-GCM encrypted API key for
  docling-serve authentication. NULL means no key configured. Plain-text key
  is never stored; encryption/decryption handled by app/infrastructure/crypto.py.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260823_02"
down_revision = "20260823_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rag_kb_ingestion_configs",
        sa.Column(
            "docling_serve_api_key_enc",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("rag_kb_ingestion_configs", "docling_serve_api_key_enc")
