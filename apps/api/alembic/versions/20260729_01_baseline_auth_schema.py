"""Create the baseline auth schema for new installations.

Existing Prisma databases with this schema must use `alembic stamp 20260729_01`
instead of running this revision, then use `alembic upgrade head` for future changes.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260729_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    user_role = postgresql.ENUM("USER", "ADMIN", name="UserRole", create_type=False)
    user_status = postgresql.ENUM("ACTIVE", "SUSPENDED", name="UserStatus", create_type=False)
    user_role.create(op.get_bind(), checkfirst=True)
    user_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="USER"),
        sa.Column("status", user_status, nullable=False, server_default="ACTIVE"),
        sa.Column("photo", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("auth_sessions")
    op.drop_table("users")
    postgresql.ENUM(name="UserStatus").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="UserRole").drop(op.get_bind(), checkfirst=True)
