"""Add tenant-scoped RAG answer-run and citation traces.

Revision ID: 20260804_01
Revises: 20260803_02
Create Date: 2026-08-04
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260804_01"
down_revision = "20260803_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_answer_runs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("trace_id", sa.String(120), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("original_query", sa.String(8000), nullable=False),
        sa.Column("standalone_query", sa.String(8000), nullable=True),
        sa.Column("route", sa.String(30), nullable=False),
        sa.Column("evidence_level", sa.String(20), nullable=False),
        sa.Column("profile_snapshot", postgresql.JSON(), nullable=False),
        sa.Column("limitations", postgresql.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "trace_id", name="uq_rag_answer_runs_tenant_trace"),
    )
    op.create_index("ix_rag_answer_runs_tenant_id", "rag_answer_runs", ["tenant_id"])
    op.create_table(
        "rag_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_rag_conversations_tenant_id", "rag_conversations", ["tenant_id"])
    op.create_table(
        "rag_retrieval_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("answer_run_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("summary", postgresql.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["answer_run_id"], ["rag_answer_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "answer_run_id", name="uq_rag_retrieval_summaries_run"),
    )
    op.create_index("ix_rag_retrieval_summaries_tenant_id", "rag_retrieval_summaries", ["tenant_id"])
    op.create_table(
        "rag_selected_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("answer_run_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("metadata", postgresql.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["answer_run_id"], ["rag_answer_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["rag_chunks.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "answer_run_id", "chunk_id", name="uq_rag_selected_evidence_run_chunk"),
    )
    op.create_index("ix_rag_selected_evidence_tenant_id", "rag_selected_evidence", ["tenant_id"])
    op.create_table(
        "rag_answer_citations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("answer_run_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("citation_id", sa.String(32), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("locator", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["answer_run_id"], ["rag_answer_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["rag_chunks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_version_id"], ["rag_document_versions.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "answer_run_id", "citation_id", name="uq_rag_answer_citations_run_id"),
    )
    op.create_index("ix_rag_answer_citations_tenant_id", "rag_answer_citations", ["tenant_id"])
    op.create_table(
        "rag_validation_outcomes",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("answer_run_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("checks", postgresql.JSON(), nullable=False),
        sa.Column("repair_attempted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["answer_run_id"], ["rag_answer_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "answer_run_id", name="uq_rag_validation_outcomes_run"),
    )
    op.create_index("ix_rag_validation_outcomes_tenant_id", "rag_validation_outcomes", ["tenant_id"])
    op.create_table(
        "rag_answer_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("answer_run_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("comment", sa.String(2_000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["answer_run_id"], ["rag_answer_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_rag_answer_feedback_tenant_id", "rag_answer_feedback", ["tenant_id"])
    op.create_table(
        "rag_evaluation_results",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("profile_id", sa.String(120), nullable=False),
        sa.Column("fixture_id", sa.String(120), nullable=False),
        sa.Column("metrics", postgresql.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "profile_id", "fixture_id", name="uq_rag_evaluation_results_profile_fixture"),
    )
    op.create_index("ix_rag_evaluation_results_tenant_id", "rag_evaluation_results", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_rag_evaluation_results_tenant_id", table_name="rag_evaluation_results")
    op.drop_table("rag_evaluation_results")
    op.drop_index("ix_rag_answer_feedback_tenant_id", table_name="rag_answer_feedback")
    op.drop_table("rag_answer_feedback")
    op.drop_index("ix_rag_validation_outcomes_tenant_id", table_name="rag_validation_outcomes")
    op.drop_table("rag_validation_outcomes")
    op.drop_index("ix_rag_answer_citations_tenant_id", table_name="rag_answer_citations")
    op.drop_table("rag_answer_citations")
    op.drop_index("ix_rag_selected_evidence_tenant_id", table_name="rag_selected_evidence")
    op.drop_table("rag_selected_evidence")
    op.drop_index("ix_rag_retrieval_summaries_tenant_id", table_name="rag_retrieval_summaries")
    op.drop_table("rag_retrieval_summaries")
    op.drop_index("ix_rag_conversations_tenant_id", table_name="rag_conversations")
    op.drop_table("rag_conversations")
    op.drop_index("ix_rag_answer_runs_tenant_id", table_name="rag_answer_runs")
    op.drop_table("rag_answer_runs")
