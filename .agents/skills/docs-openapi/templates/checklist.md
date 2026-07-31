# Checklist: docs-openapi

## Preparation

- [ ] Check `apps/api/app/interfaces/http/routes.py` for routes that need annotations
- [ ] Check `apps/api/app/interfaces/http/schemas.py` for schemas that need descriptions

## Route Annotations

- [ ] Every new route has `tags` (via APIRouter)
- [ ] Every new route has `summary`
- [ ] Every new route has `description` (if behavior is non-obvious)
- [ ] `response_model` or explicit return type on routes that need it
- [ ] Error responses documented via `responses` dict

## Schema Annotations

- [ ] Every new field has `Field(description=...)`
- [ ] Request schemas have `model_config` with `json_schema_extra` examples

## Export

- [ ] `uv run python -m app.export_openapi` run
- [ ] `docs/openapi.json` regenerated
- [ ] Spec is valid and consumable by Scalar/Swagger

## Finalization

- [ ] Every file ends with a newline (EOF)
- [ ] No hand-written OpenAPI YAML files created
- [ ] `docs/openapi.json` not edited directly
