---
name: docs-openapi
description: Manage OpenAPI quality via FastAPI annotations (tags, summaries, response_model, descriptions, examples) and export the spec to docs/openapi.json. Use when endpoints, request/response schemas, or API contracts change.
---

# Skill: Docs OpenAPI

## Context (Required)
- Output file: `docs/openapi.json`
- Export script: `apps/api/app/export_openapi.py`
- Source of truth: the FastAPI application itself

Use this skill to manage OpenAPI documentation quality. The OpenAPI spec is **auto-generated** from the FastAPI application — there are no hand-written split YAML files. The source of truth is the FastAPI app (routes, Pydantic models, tags, descriptions).

## Workflow

1. Read the API contract or finalized endpoints to document.
2. Ensure each route has proper FastAPI annotations:
   - `tags` on the `APIRouter` (feature name)
   - `summary` on each route handler
   - `description` on each route handler (if needed)
   - `response_model` for explicit response typing
   - `responses` dict for error responses
3. Ensure Pydantic schemas have `Field(description=...)` and `model_config` with `json_schema_extra` for examples.
4. Run `uv run python -m app.export_openapi` to regenerate `docs/openapi.json`.
5. Verify the spec is valid and consumable by Scalar/Swagger.

## Route Annotation Pattern

```python
from fastapi import APIRouter, status

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

@auth_router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Creates a new user account with the provided credentials.",
    responses={
        409: {"description": "Email already registered"},
    },
)
async def register(payload: RegisterRequest, service: AuthServiceDependency) -> dict[str, object]:
    ...
```

## Schema Annotation Pattern

```python
from pydantic import BaseModel, Field

class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120, description="User display name")
    email: EmailStr = Field(max_length=255, description="User email address")
    password: str = Field(min_length=8, max_length=128, description="User password")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"name": "John Doe", "email": "john@example.com", "password": "securepassword"}
            ]
        }
    }
```

## Export Command

```bash
uv run python -m app.export_openapi
```

This runs `apps/api/app/export_openapi.py` which calls `create_app().openapi()` and writes the result to `docs/openapi.json`.

## Prohibitions

- **NEVER** hand-write OpenAPI YAML files — the spec is auto-generated from FastAPI.
- **NEVER** edit `docs/openapi.json` directly — it is a generated artifact. Edit the FastAPI app and re-export.
- **NEVER** leave a route without a `tags` or `summary` — these drive the OpenAPI documentation.
- **NEVER** leave a response body without an explicit schema or `response_model`.

## Pre-Completion Checklist

- [ ] Every new route has `tags`, `summary`, and `description`
- [ ] Every new Pydantic schema has `Field(description=...)`
- [ ] `response_model` or explicit return type on routes that need it
- [ ] Error responses documented via `responses` dict
- [ ] `uv run python -m app.export_openapi` run
- [ ] `docs/openapi.json` regenerated and valid
- [ ] Every file ends with a newline (EOF)
