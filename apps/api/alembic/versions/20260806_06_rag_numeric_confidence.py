"""Add calibration persistence and answer-run feature vectors."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "20260806_06"
down_revision = "20260806_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DO $$ BEGIN CREATE TYPE \"CalibrationSource\" AS ENUM ('OPERATOR_LABELED', 'SYNTHETIC_BOOTSTRAP'); EXCEPTION WHEN duplicate_object THEN NULL; END $$"))
    bind.execute(sa.text("DO $$ BEGIN CREATE TYPE \"ConfidenceLabel\" AS ENUM ('SUPPORTED', 'PARTIALLY_SUPPORTED', 'UNSUPPORTED', 'ABSTAIN'); EXCEPTION WHEN duplicate_object THEN NULL; END $$"))
    op.add_column("rag_answer_runs", sa.Column("feature_vector", JSONB(), nullable=True))
    op.create_table(
        "calibration_fixture",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("retrieval_profile_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("version", sa.String(120), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("entry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Uuid(as_uuid=False), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["retrieval_profile_id"], ["rag_index_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_calibration_fixture_active_profile", "calibration_fixture", ["tenant_id", "retrieval_profile_id"], unique=True, postgresql_where=sa.text("is_active = true"))
    op.create_table(
        "calibration_fixture_entry",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("fixture_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("answer_run_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("evidence_chunk_ids", sa.ARRAY(sa.Uuid(as_uuid=False)), nullable=False),
        sa.Column("answer", sa.String(), nullable=False),
        sa.Column("confidence_label", sa.Text(), nullable=False),
        sa.Column("annotator_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("annotated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["fixture_id"], ["calibration_fixture.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["answer_run_id"], ["rag_answer_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["annotator_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "calibration_model_version",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("retrieval_profile_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("fixture_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("artifact_path", sa.String(1024), nullable=False),
        sa.Column("feature_names", JSONB(), nullable=False),
        sa.Column("threshold_used", sa.Float(), nullable=False),
        sa.Column("precision_at_threshold", sa.Float(), nullable=False),
        sa.Column("recall_at_threshold", sa.Float(), nullable=False),
        sa.Column("f1_at_threshold", sa.Float(), nullable=False),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("promoted_by", sa.Uuid(as_uuid=False), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["retrieval_profile_id"], ["rag_index_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fixture_id"], ["calibration_fixture.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["promoted_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_calibration_model_active_profile", "calibration_model_version", ["tenant_id", "retrieval_profile_id"], unique=True, postgresql_where=sa.text("is_active = true"))
    op.create_table(
        "confidence_config",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("tenant_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("retrieval_profile_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("feature_weights", JSONB(), nullable=True),
        sa.Column("abstention_threshold", sa.Float(), nullable=False, server_default="0.35"),
        sa.Column("emit_numeric_score", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("min_labeled_entries", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("active_model_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", sa.Uuid(as_uuid=False), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["retrieval_profile_id"], ["rag_index_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["active_model_id"], ["calibration_model_version.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "retrieval_profile_id", name="uq_confidence_config_tenant_profile"),
    )


def downgrade() -> None:
    op.drop_table("confidence_config")
    op.drop_index("uq_calibration_model_active_profile", table_name="calibration_model_version")
    op.drop_table("calibration_model_version")
    op.drop_table("calibration_fixture_entry")
    op.drop_index("uq_calibration_fixture_active_profile", table_name="calibration_fixture")
    op.drop_table("calibration_fixture")
    op.drop_column("rag_answer_runs", "feature_vector")
    bind = op.get_bind()
    sa.Enum(name="ConfidenceLabel").drop(bind, checkfirst=True)
    sa.Enum(name="CalibrationSource").drop(bind, checkfirst=True)
