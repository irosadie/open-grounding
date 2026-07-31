# Context: docs-openapi

## Target Files

```
apps/api/app/interfaces/http/routes.py    → route annotations (tags, summary, description, responses)
apps/api/app/interfaces/http/schemas.py   → Pydantic schema annotations (Field description, examples)
apps/api/app/export_openapi.py            → export script
docs/openapi.json                         → generated OpenAPI spec (DO NOT EDIT DIRECTLY)
```

## How OpenAPI is Generated

The OpenAPI spec is auto-generated from the FastAPI application:

1. `create_app()` builds the FastAPI app with all routers, schemas, and annotations
2. `app.openapi()` produces the OpenAPI dict
3. `apps/api/app/export_openapi.py` writes it to `docs/openapi.json`

There are no hand-written split YAML files. The source of truth is the FastAPI app.

## Route Annotation Checklist

- `APIRouter(tags=["FeatureName"])` — groups routes in docs
- `@router.post("/path", summary="Short description")` — shows in docs
- `@router.post("/path", description="Longer description")` — optional
- `@router.post("/path", response_model=MyDto)` — explicit response typing
- `@router.post("/path", responses={409: {"description": "..."}})` — error responses

## Schema Annotation Checklist

- `Field(description="...")` on each field
- `model_config = {"json_schema_extra": {"examples": [...]}}` for request examples

## Commands

```bash
uv run python -m app.export_openapi    # regenerate docs/openapi.json
```
