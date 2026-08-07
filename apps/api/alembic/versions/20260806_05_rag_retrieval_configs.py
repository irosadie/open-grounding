"""Add per-index-profile retrieval configuration."""

import sqlalchemy as sa
from alembic import op

revision = "20260806_05"
down_revision = "20260806_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_retrieval_configs",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("index_profile_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("dense_weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("sparse_weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("fusion_k", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("dense_candidates", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("sparse_candidates", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("fused_candidates", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["index_profile_id"], ["rag_index_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "index_profile_id", name="uq_retrieval_config_tenant_profile"),
    )


def downgrade() -> None:
    op.drop_table("rag_retrieval_configs")
