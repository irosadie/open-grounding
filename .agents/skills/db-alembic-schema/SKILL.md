---
name: db-alembic-schema
description: Write or modify SQLAlchemy ORM models in apps/api/app/infrastructure/ and execute safe Alembic migrations. Use for database model, relation, index, enum changes, or schema-to-domain-layer sync.
---

# Skill: DB Alembic Schema

## Context (Required)
- Folder scope + code samples: `references/context.md`
- Execution checklist: `templates/checklist.md`

Apply schema changes minimally and safely using SQLAlchemy ORM models and Alembic migrations.

## Naming Conventions

### Tables & Columns

| Category | Table Prefix | Example |
|----------|-------------|---------|
| Master / reference data | `master_` | `master_service_types` |
| Transaction / business data | `business_` | `business_shipments` |
| Membership data | `member_` | `member_profiles` |
| User / auth data | *(no prefix)* | `users`, `auth_sessions` |
| System config data | *(no prefix)* | `configurations` |

- Table names: `snake_case` plural (e.g., `users`, `auth_sessions`)
- Column names: `snake_case` (e.g., `created_at`, `is_active`)

### Boolean Fields — prefix `is` or `has`
### Enum Values — SCREAMING_SNAKE_CASE

If a field has a fixed set of values, declare a Python `StrEnum` in `apps/api/app/domain/models.py` as the source of truth. Use `Enum(PythonEnum)` in the SQLAlchemy column.

```python
# domain/models.py (source of truth)
class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
```

```python
# infrastructure/database.py — use Enum(StrEnum)
status: Mapped[UserStatus] = mapped_column(Enum(UserStatus, name="UserStatus"), default=UserStatus.ACTIVE, nullable=False)
```

### Required Standard Fields

```python
id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)
deleted_at: Mapped[datetime | None] = mapped_column("deleted_at", DateTime(timezone=False), nullable=True)
```

## Workflow

1. Read `apps/api/app/infrastructure/database.py` to understand existing ORM records.
2. Read `apps/api/app/domain/models.py` to ensure entities and StrEnums are in sync.
3. Identify breaking vs non-breaking changes.
4. Write minimal diff to the ORM record class.
5. Run: `uv run alembic revision --autogenerate -m "<description>"`
6. Review the generated migration file in `alembic/versions/`.
7. Run: `uv run alembic upgrade head`
8. If a new entity/field is added, sync `domain/models.py` and `domain/repositories.py`.

## Prohibitions

- **NEVER** rename a table, column, or enum without a clear requirement.
- **NEVER** drop an existing column or relation without documenting the migration impact.
- **NEVER** leave placeholders or names that violate the prefix convention.
- **NEVER** edit files outside the ORM/migration scope unless the task requires it.
- **NEVER** run `alembic downgrade` on a shared database without explicit confirmation.

## Pre-Completion Checklist

- [ ] Table naming follows the category prefix
- [ ] Table name is `snake_case` plural
- [ ] Column names are `snake_case`
- [ ] Boolean fields prefixed `is` or `has`
- [ ] Enum values in SCREAMING_SNAKE_CASE
- [ ] Standard fields present: id, created_at, updated_at
- [ ] `StrEnum` declared in `domain/models.py` (if new enum)
- [ ] `uv run alembic revision --autogenerate -m "<desc>" run
- [ ] Migration file reviewed
- [ ] `uv run alembic upgrade head` passes
- [ ] `uv run mypy app` passes
- [ ] Every file ends with a newline (EOF)
