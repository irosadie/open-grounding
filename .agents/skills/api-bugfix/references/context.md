# Context: API Bugfix

## Target Folders

```
apps/api/app/interfaces/http/          → routes.py, schemas.py, dependencies.py, errors.py
apps/api/app/application/              → {domain}_service.py, dtos.py
apps/api/app/domain/                   → models.py, repositories.py, errors.py, use_cases/
apps/api/app/infrastructure/            → database.py
docs/openapi.json                      → generated OpenAPI spec
```

## Impact Map

Check in this order:
1. Is the bug in request validation? (Pydantic schema in schemas.py)
2. Is the bug in orchestration / response mapping? (service)
3. Is the bug in a use-case business rule? (use_cases/)
4. Is the bug in repository / side effect? (infrastructure/database.py)
5. Does the user-visible endpoint behavior change?

## Key Patterns

- Layer boundaries must stay clean during a bugfix
- Minimal touch beats broad refactor
- Response or error contract changes trigger OpenAPI regeneration via `uv run python -m app.export_openapi`
- Request shape changes trigger Pydantic schema audit in `interfaces/http/schemas.py`

## Active Surface Examples

- `apps/api/app/interfaces/http/routes.py`
- `apps/api/app/application/auth_service.py`
- `apps/api/app/domain/use_cases/`
- `docs/openapi.json`
