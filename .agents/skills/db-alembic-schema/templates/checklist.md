# Checklist: DB Alembic Schema

- [ ] Read `.agents/settings.json`
- [ ] Read `references/context.md`
- [ ] Read `apps/api/app/infrastructure/database.py` before any change
- [ ] Read `apps/api/app/domain/models.py` — ensure StrEnum sync
- [ ] Table naming: prefix matches the category
- [ ] Table name is `snake_case` plural
- [ ] Column names are `snake_case`
- [ ] Boolean fields prefixed `is` or `has`
- [ ] Enum values in SCREAMING_SNAKE_CASE
- [ ] Standard fields present: id, created_at, updated_at
- [ ] Relations: `ForeignKey` + `relationship` correct
- [ ] Indexes on FKs and frequently queried fields
- [ ] `StrEnum` declared in `domain/models.py` (if new enum)
- [ ] `uv run alembic revision --autogenerate -m "<desc>" run
- [ ] Migration file reviewed before applying
- [ ] `uv run alembic upgrade head` passes
- [ ] `uv run mypy app` passes
- [ ] Every file ends with a newline (EOF)
