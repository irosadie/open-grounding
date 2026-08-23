# Context: API Code Review

## Target Folders

```
apps/api/app/interfaces/http/          → routes.py, schemas.py, dependencies.py, errors.py
apps/api/app/application/              → {domain}_service.py, dtos.py
apps/api/app/domain/                   → models.py, repositories.py, errors.py, use_cases/
apps/api/app/infrastructure/            → database.py
docs/openapi.json                      → generated OpenAPI spec
```

## Key Patterns

- routes must not jump straight to a repository
- route handlers must not hold business logic (they are the controller — thin)
- use cases must not know about HTTP concerns
- Pydantic schema/DTO/response shape changes trigger a contract drift audit
- OpenAPI is auto-generated — drift means the FastAPI annotations don't match the actual behavior

## Active Surface Examples

- Baseline routes: `apps/api/app/interfaces/http/routes.py`
- App assembly: `apps/api/app/main.py`
- Active OpenAPI: `docs/openapi.json`
