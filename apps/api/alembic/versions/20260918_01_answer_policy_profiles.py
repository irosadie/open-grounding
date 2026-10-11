"""Add versioned answer behavior and guardrail profiles.

Revision ID: 20260918_01
Revises: 20260823_02
Create Date: 2026-09-18
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260918_01"
down_revision = "20260823_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    policy_scope = postgresql.ENUM("DEPLOYMENT", "TENANT", "KNOWLEDGE_BASE", name="PolicyScope")
    response_style = postgresql.ENUM("CONCISE", "BALANCED", "DETAILED", name="ResponseStyle")
    source_policy = postgresql.ENUM("DOCUMENT_ONLY", "DOCUMENT_OR_MCP", "DOCUMENT_MCP_GENERAL", name="AnswerSourcePolicy")
    greeting_policy = postgresql.ENUM("ALLOW_UNGROUNDED", "REQUIRE_ALLOWED_SOURCE", "REFUSE", name="GreetingPolicy")
    no_evidence_action = postgresql.ENUM("ABSTAIN", "REFUSE", "ANSWER_UNGROUNDED", name="NoEvidenceAction")
    for enum_type in (policy_scope, response_style, source_policy, greeting_policy, no_evidence_action):
        enum_type.create(bind, checkfirst=True)
    policy_scope_column = postgresql.ENUM("DEPLOYMENT", "TENANT", "KNOWLEDGE_BASE", name="PolicyScope", create_type=False)
    response_style_column = postgresql.ENUM("CONCISE", "BALANCED", "DETAILED", name="ResponseStyle", create_type=False)
    source_policy_column = postgresql.ENUM(
        "DOCUMENT_ONLY", "DOCUMENT_OR_MCP", "DOCUMENT_MCP_GENERAL", name="AnswerSourcePolicy", create_type=False
    )
    greeting_policy_column = postgresql.ENUM(
        "ALLOW_UNGROUNDED", "REQUIRE_ALLOWED_SOURCE", "REFUSE", name="GreetingPolicy", create_type=False
    )
    no_evidence_action_column = postgresql.ENUM(
        "ABSTAIN", "REFUSE", "ANSWER_UNGROUNDED", name="NoEvidenceAction", create_type=False
    )

    op.create_table(
        "rag_answer_behavior_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("version", sa.String(120), nullable=False),
        sa.Column("scope", policy_scope_column, nullable=False),
        sa.Column("persona", sa.Text(), nullable=False, server_default=""),
        sa.Column("response_style", response_style_column, nullable=False, server_default="BALANCED"),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False, server_default="1024"),
        sa.Column("source_policy", source_policy_column, nullable=False, server_default="DOCUMENT_MCP_GENERAL"),
        sa.Column("greeting_policy", greeting_policy_column, nullable=False, server_default="ALLOW_UNGROUNDED"),
        sa.Column("no_evidence_action", no_evidence_action_column, nullable=False, server_default="ANSWER_UNGROUNDED"),
        sa.Column("require_citations", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allow_mcp_sources", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("effective_from", sa.DateTime(), nullable=True),
        sa.Column("effective_to", sa.DateTime(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["rag_knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "scope", "knowledge_base_id", "version", name="uq_rag_answer_behavior_scope_version"),
    )
    op.create_index("ix_rag_answer_behavior_tenant_active", "rag_answer_behavior_profiles", ["tenant_id", "is_active"])
    op.create_index("ix_rag_answer_behavior_tenant_kb", "rag_answer_behavior_profiles", ["tenant_id", "knowledge_base_id"])

    op.create_table(
        "rag_guardrail_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("version", sa.String(120), nullable=False),
        sa.Column("scope", policy_scope_column, nullable=False),
        sa.Column("input_rules", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("tool_rules", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("output_rules", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("max_tool_calls", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("max_tool_timeout_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_tool_payload_bytes", sa.Integer(), nullable=False, server_default="1048576"),
        sa.Column("max_mcp_freshness_seconds", sa.Integer(), nullable=False, server_default="900"),
        sa.Column("require_tool_confirmation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["rag_knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "scope", "knowledge_base_id", "version", name="uq_rag_guardrail_scope_version"),
    )
    op.create_index("ix_rag_guardrail_tenant_active", "rag_guardrail_profiles", ["tenant_id", "is_active"])
    op.create_index("ix_rag_guardrail_tenant_kb", "rag_guardrail_profiles", ["tenant_id", "knowledge_base_id"])

    op.create_table(
        "rag_policy_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("policy_kind", sa.String(32), nullable=False),
        sa.Column("policy_version", sa.String(120), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("changes", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("trace_id", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["rag_knowledge_bases.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_rag_policy_audit_tenant_created", "rag_policy_audit_events", ["tenant_id", "created_at"])
    op.create_index("ix_rag_policy_audit_tenant_kind", "rag_policy_audit_events", ["tenant_id", "policy_kind"])

    op.execute(
        sa.text(
            """
            INSERT INTO rag_answer_behavior_profiles
                (id, tenant_id, version, scope, persona, response_style, max_output_tokens,
                 source_policy, greeting_policy, no_evidence_action, require_citations,
                 allow_mcp_sources, is_active)
            SELECT gen_random_uuid(), t.id, 'migrated-default-v1', 'DEPLOYMENT', '', 'BALANCED', 1024,
                   'DOCUMENT_MCP_GENERAL', 'ALLOW_UNGROUNDED', 'ANSWER_UNGROUNDED', true, true, true
            FROM tenants t
            WHERE NOT EXISTS (
                SELECT 1 FROM rag_answer_behavior_profiles p
                WHERE p.tenant_id = t.id AND p.scope = 'DEPLOYMENT' AND p.knowledge_base_id IS NULL
                  AND p.version = 'migrated-default-v1'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO rag_guardrail_profiles
                (id, tenant_id, version, scope, input_rules, tool_rules, output_rules,
                 max_tool_calls, max_tool_timeout_seconds, max_tool_payload_bytes,
                 max_mcp_freshness_seconds, require_tool_confirmation, is_active)
            SELECT gen_random_uuid(), t.id, 'platform-baseline-v1', 'DEPLOYMENT',
                   '["BLOCK_POLICY_BYPASS", "BLOCK_SECRET_EXTRACTION"]'::json,
                   '["REQUIRE_PERMISSION", "VALIDATE_ARGUMENTS", "BOUND_CALLS"]'::json,
                   '["BLOCK_SECRET_DISCLOSURE", "VALIDATE_SCHEMA", "VALIDATE_PROVENANCE"]'::json,
                   4, 30, 1048576, 900, false, true
            FROM tenants t
            WHERE NOT EXISTS (
                SELECT 1 FROM rag_guardrail_profiles p
                WHERE p.tenant_id = t.id AND p.scope = 'DEPLOYMENT' AND p.knowledge_base_id IS NULL
                  AND p.version = 'platform-baseline-v1'
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_rag_policy_audit_tenant_kind", table_name="rag_policy_audit_events")
    op.drop_index("ix_rag_policy_audit_tenant_created", table_name="rag_policy_audit_events")
    op.drop_table("rag_policy_audit_events")
    op.drop_index("ix_rag_guardrail_tenant_kb", table_name="rag_guardrail_profiles")
    op.drop_index("ix_rag_guardrail_tenant_active", table_name="rag_guardrail_profiles")
    op.drop_table("rag_guardrail_profiles")
    op.drop_index("ix_rag_answer_behavior_tenant_kb", table_name="rag_answer_behavior_profiles")
    op.drop_index("ix_rag_answer_behavior_tenant_active", table_name="rag_answer_behavior_profiles")
    op.drop_table("rag_answer_behavior_profiles")
    bind = op.get_bind()
    for enum_name in ("NoEvidenceAction", "GreetingPolicy", "AnswerSourcePolicy", "ResponseStyle", "PolicyScope"):
        postgresql.ENUM(name=enum_name).drop(bind, checkfirst=True)
