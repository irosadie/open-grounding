"""Add tenant-scoped Projects and project ownership for RAG configuration."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260918_02"
down_revision = "20260918_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    project_status = postgresql.ENUM("ACTIVE", "ARCHIVED", name="ProjectStatus")
    project_status.create(bind, checkfirst=True)
    # The enum is created explicitly so retries after a partially applied
    # migration remain safe; prevent create_table from attempting it again.
    project_status_column = postgresql.ENUM(
        "ACTIVE", "ARCHIVED", name="ProjectStatus", create_type=False
    )

    op.create_table(
        "rag_projects",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", project_status_column, nullable=False, server_default="ACTIVE"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_rag_projects_tenant_slug"),
    )
    op.create_index("ix_rag_projects_tenant_status", "rag_projects", ["tenant_id", "status"])
    op.create_index("uq_rag_projects_tenant_default", "rag_projects", ["tenant_id"], unique=True, postgresql_where=sa.text("is_default = true"))

    op.create_table(
        "rag_project_migration_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("config_kind", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("legacy_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["rag_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["rag_knowledge_bases.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "project_id", "config_kind", name="uq_project_migration_review_kind"),
    )
    op.create_index("ix_project_migration_reviews_tenant_status", "rag_project_migration_reviews", ["tenant_id", "status"])

    op.create_table(
        "rag_project_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("reason_code", sa.String(96), nullable=False),
        sa.Column("metadata", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["rag_projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["rag_knowledge_bases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_project_audit_tenant_created", "rag_project_audit_events", ["tenant_id", "created_at"])

    op.add_column("rag_knowledge_bases", sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.create_foreign_key(
        "fk_rag_knowledge_bases_project_id",
        "rag_knowledge_bases",
        "rag_projects",
        ["project_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_rag_knowledge_bases_tenant_project", "rag_knowledge_bases", ["tenant_id", "project_id"])

    op.execute(
        sa.text(
            """
            INSERT INTO rag_projects (id, tenant_id, slug, name, status, is_default)
            SELECT gen_random_uuid(), t.id, 'default', 'Default Project', 'ACTIVE', true
            FROM tenants t
            WHERE NOT EXISTS (
                SELECT 1 FROM rag_projects p WHERE p.tenant_id = t.id AND p.is_default = true
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE rag_knowledge_bases kb
            SET project_id = p.id
            FROM rag_projects p
            WHERE kb.tenant_id = p.tenant_id
              AND p.is_default = true
              AND kb.project_id IS NULL
            """
        )
    )
    op.alter_column("rag_knowledge_bases", "project_id", nullable=False)
    op.execute(
        sa.text(
            """
            INSERT INTO rag_project_audit_events
                (id, tenant_id, project_id, action, reason_code, metadata)
            SELECT gen_random_uuid(), p.tenant_id, p.id, 'PROJECT_BACKFILL',
                   'MIGRATION_DEFAULT_PROJECT',
                   jsonb_build_object('knowledgeBaseCount', COUNT(kb.id))
            FROM rag_projects p
            LEFT JOIN rag_knowledge_bases kb ON kb.project_id = p.id
            WHERE p.is_default = true
            GROUP BY p.tenant_id, p.id
            """
        )
    )

    # Add the new policy scope without rewriting the already-applied policy migration.
    op.execute(sa.text("ALTER TYPE \"PolicyScope\" ADD VALUE IF NOT EXISTS 'PROJECT'"))

    for table, index_name, constraint_name in (
        ("rag_decomposition_configs", "ix_rag_decomposition_configs_tenant_project", "uq_decomp_config_tenant_project"),
        ("rag_planner_configs", "ix_rag_planner_configs_tenant_project", "uq_planner_config_tenant_project"),
        ("rag_memory_configs", "ix_rag_memory_configs_tenant_project", "uq_memory_config_tenant_project"),
    ):
        op.add_column(table, sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_project_id",
            table,
            "rag_projects",
            ["project_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(index_name, table, ["tenant_id", "project_id"])
        op.create_unique_constraint(constraint_name, table, ["tenant_id", "project_id"])

    op.add_column("rag_answer_behavior_profiles", sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.add_column("rag_guardrail_profiles", sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.add_column("rag_policy_audit_events", sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=True))
    for table in ("rag_answer_behavior_profiles", "rag_guardrail_profiles", "rag_policy_audit_events"):
        op.create_foreign_key(
            f"fk_{table}_project_id",
            table,
            "rag_projects",
            ["project_id"],
            ["id"],
            ondelete="SET NULL" if table == "rag_policy_audit_events" else "CASCADE",
        )
    op.create_index("ix_rag_answer_behavior_tenant_project", "rag_answer_behavior_profiles", ["tenant_id", "project_id"])
    op.create_index("ix_rag_guardrail_tenant_project", "rag_guardrail_profiles", ["tenant_id", "project_id"])
    op.create_index("ix_rag_policy_audit_tenant_project", "rag_policy_audit_events", ["tenant_id", "project_id"])

    # Preserve legacy configuration for review instead of selecting a winner
    # silently. One bounded review item is created per tenant and capability.
    for table, kind in (
        ("rag_decomposition_configs", "DECOMPOSITION"),
        ("rag_planner_configs", "PLANNER"),
        ("rag_memory_configs", "MEMORY"),
    ):
        op.execute(
            sa.text(
                f"""
                INSERT INTO rag_project_migration_reviews
                    (id, tenant_id, project_id, config_kind, status, legacy_count)
                SELECT gen_random_uuid(), p.tenant_id, p.id, '{kind}', 'OPEN', COUNT(*)
                FROM rag_projects p
                JOIN {table} legacy ON legacy.tenant_id = p.tenant_id
                WHERE p.is_default = true
                GROUP BY p.tenant_id, p.id
                HAVING COUNT(*) > 0
                """
            )
        )
    for table, kind in (
        ("rag_answer_behavior_profiles", "ANSWER_BEHAVIOR"),
        ("rag_guardrail_profiles", "GUARDRAILS"),
    ):
        op.execute(
            sa.text(
                f"""
                INSERT INTO rag_project_migration_reviews
                    (id, tenant_id, project_id, config_kind, status, legacy_count)
                SELECT gen_random_uuid(), p.tenant_id, p.id, '{kind}', 'OPEN', COUNT(*)
                FROM rag_projects p
                JOIN {table} legacy ON legacy.tenant_id = p.tenant_id
                WHERE p.is_default = true AND legacy.scope = 'KNOWLEDGE_BASE'
                GROUP BY p.tenant_id, p.id
                HAVING COUNT(*) > 0
                """
            )
        )


def downgrade() -> None:
    # This downgrade is intended for an isolated database only. Production rollback
    # re-enables compatibility and retains project data.
    for table, index_name in (
        ("rag_answer_behavior_profiles", "ix_rag_answer_behavior_tenant_project"),
        ("rag_guardrail_profiles", "ix_rag_guardrail_tenant_project"),
        ("rag_policy_audit_events", "ix_rag_policy_audit_tenant_project"),
    ):
        op.drop_index(index_name, table_name=table)
        op.drop_constraint(f"fk_{table}_project_id", table_name=table, type_="foreignkey")
        op.drop_column(table, "project_id")
    for table, index_name, constraint_name in (
        ("rag_decomposition_configs", "ix_rag_decomposition_configs_tenant_project", "uq_decomp_config_tenant_project"),
        ("rag_planner_configs", "ix_rag_planner_configs_tenant_project", "uq_planner_config_tenant_project"),
        ("rag_memory_configs", "ix_rag_memory_configs_tenant_project", "uq_memory_config_tenant_project"),
    ):
        op.drop_constraint(constraint_name, table_name=table, type_="unique")
        op.drop_index(index_name, table_name=table)
        op.drop_constraint(f"fk_{table}_project_id", table_name=table, type_="foreignkey")
        op.drop_column(table, "project_id")
    op.drop_index("ix_rag_knowledge_bases_tenant_project", table_name="rag_knowledge_bases")
    op.drop_constraint("fk_rag_knowledge_bases_project_id", table_name="rag_knowledge_bases", type_="foreignkey")
    op.drop_column("rag_knowledge_bases", "project_id")
    op.drop_index("ix_project_audit_tenant_created", table_name="rag_project_audit_events")
    op.drop_table("rag_project_audit_events")
    op.drop_index("ix_project_migration_reviews_tenant_status", table_name="rag_project_migration_reviews")
    op.drop_table("rag_project_migration_reviews")
    op.drop_index("uq_rag_projects_tenant_default", table_name="rag_projects")
    op.drop_index("ix_rag_projects_tenant_status", table_name="rag_projects")
    op.drop_table("rag_projects")
    postgresql.ENUM(name="ProjectStatus").drop(op.get_bind(), checkfirst=True)
