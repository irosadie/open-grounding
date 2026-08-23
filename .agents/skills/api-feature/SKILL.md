---
name: api-feature
description: Implement new backend features following Clean Architecture. Use for tasks involving new endpoints, use cases, entities, repositories, or application-layer changes.
---

# Skill: API Feature

## Context (Required)
- Folder scope + code examples: `references/context.md`
- Execution checklist: `templates/checklist.md`

Implement backend features professionally, following Clean Architecture (hybrid 4-hop: route handler → service → use_case → repository).

## Workflow

1. Read the API contract or requirement provided.

2. Read the guide for **each layer** before creating files there:
   - `.agents/guides/api-entity.md`
   - `.agents/guides/api-repository.md`
   - `.agents/guides/api-usecase.md`
   - `.agents/guides/api-service.md`
   - `.agents/guides/api-dto.md`
   - `.agents/guides/api-db-repository.md`
   - `.agents/guides/api-validator.md`
   - `.agents/guides/api-controller.md`
   - `.agents/guides/api-route.md`
   - `.agents/guides/api-error.md`

3. Create files **in order** by layer dependency:
   ```
   1. app/domain/models.py              — entity (@dataclass) + StrEnum (if new)
   2. app/domain/repositories.py        — Protocol interface
   3. app/domain/errors.py              — DomainError classmethod (if new error)
   4. app/domain/use_cases/{verb}_{domain}.py — use case (business rule)
   5. app/application/{domain}_service.py — service (orchestration + Entity→DTO)
   6. app/application/dtos.py           — Pydantic response model (if needed)
   7. app/infrastructure/database.py    — ORM record + SqlAlchemy{Domain}Repository + _to_* mapper
   8. alembic/versions/{date}_{nn}_{slug}.py — migration (if schema change)
   9. app/interfaces/http/schemas.py    — Pydantic request model
   10. app/interfaces/http/dependencies.py — Depends provider + Annotated alias
   11. app/interfaces/http/routes.py    — APIRouter handler
   12. app/main.py                      — app.include_router (if new router)
   ```

4. Error handling — do not catch in Service or route handler:
   ```
   Use case raises DomainError → @app.exception_handler(DomainError) → JSON response
   ```

## Prohibitions

- **NEVER** use untyped `Any` for domain fields.
- **NEVER** put business logic in the route handler.
- **NEVER** access SQLAlchemy in a use case.
- **NEVER** raise `HTTPException` from a use case — use `DomainError`.
- **NEVER** change files unrelated to the task.
- **NEVER** use plain `str` for fields with a fixed value set — declare a `StrEnum` in `domain/models.py`.

## Pre-Completion Checklist

- [ ] Entity + StrEnum created in `domain/models.py`
- [ ] Repository Protocol created in `domain/repositories.py`
- [ ] Use case created in `domain/use_cases/{verb}_{domain}.py`
- [ ] Service created in `application/{domain}_service.py`
- [ ] SQLAlchemy ORM record + repository created in `infrastructure/database.py`
- [ ] Pydantic request schema created in `interfaces/http/schemas.py`
- [ ] Dependencies provider + Annotated alias created in `interfaces/http/dependencies.py`
- [ ] Route handler created in `interfaces/http/routes.py`
- [ ] Router registered in `main.py`
- [ ] Alembic migration created (if schema changed)
- [ ] No untyped `Any`
- [ ] No business logic in route handler
- [ ] No SQLAlchemy in use case
- [ ] `uv run ruff check app tests` passes
- [ ] `uv run mypy app` passes
- [ ] `uv run pytest` passes
- [ ] All files end with a newline (EOF)
