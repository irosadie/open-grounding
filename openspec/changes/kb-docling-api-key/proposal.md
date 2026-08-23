# Proposal: kb-docling-api-key

## Why

The `DoclingServeAdapter` currently sends requests to docling-serve without any
authentication header. When docling-serve is deployed with access control (e.g. a
reverse proxy requiring `X-Api-Key`), every request fails with 401/403. Since
docling-serve URL is already stored per-KB in `IngestionConfig`, the API key must
also be stored per-KB — a single global env var is insufficient when different KBs
point to different docling-serve instances with different keys.

API keys are credentials and must be encrypted at rest using the same AES-256-GCM
pattern already used for provider credentials (`app/infrastructure/crypto.py`).

## What Changes

- Add `docling_serve_api_key_enc: str | None` column to `rag_kb_ingestion_configs`
  (encrypted at rest, never returned plain-text in API responses).
- Extend `IngestionConfig` domain entity with `docling_serve_api_key_enc: str | None`.
- Extend `IngestionConfigService.upsert_config()` to accept `docling_serve_api_key: str | None`,
  encrypt it using `crypto.encrypt()` before persisting.
- Add `IngestionConfigService.get_api_key_decrypted()` — internal method for parse
  stage use only, never exposed via HTTP.
- Extend `DoclingServeAdapter` to accept an optional `api_key: str | None` and inject
  `X-Api-Key: {key}` header on every HTTP request when set.
- Update parse stage to decrypt KB api key and pass it to `DoclingServeAdapter`.
- API write request accepts `docling_serve_api_key: str | None` (plain text, write-only).
- API read response returns `docling_serve_api_key_set: bool` — never the plain-text value.
- Frontend: password input for API key (write-only), show "Key saved" indicator when set.

## Capabilities

### Modified Capabilities

- `kb-parser-config`: `IngestionConfig` gains `docling_serve_api_key_enc` (encrypted),
  service gains encrypt-on-write + decrypt-for-worker, DB migration adds column.
- `kb-ingestion-settings`: API write request gains `docling_serve_api_key` (write-only),
  response gains `docling_serve_api_key_set: bool`.
- `rag-docling-serve-adapter`: Adapter gains optional `api_key` injected as
  `X-Api-Key` header on every request.

## Impact

| Area | Change |
|---|---|
| `apps/api/app/domain/rag/catalog.py` | Add `docling_serve_api_key_enc: str | None` to `IngestionConfig` |
| `apps/api/app/infrastructure/rag_catalog.py` | Add column to ORM, update mapper + upsert |
| `apps/api/app/application/ingestion_config_service.py` | Encrypt on write, add `get_api_key_decrypted()` |
| `apps/api/app/interfaces/http/schemas.py` | Add write field + `docling_serve_api_key_set` bool to response |
| `apps/api/app/interfaces/http/routes.py` | Pass key to service, mask in response |
| `apps/api/app/infrastructure/rag/parsers/docling_serve_adapter.py` | Accept + inject `X-Api-Key` header |
| `apps/api/app/workers/stages/parse.py` | Decrypt key, pass to `_run_serve_adapter` |
| `apps/api/alembic/versions/` | New migration: add `docling_serve_api_key_enc` column |
| `apps/web/` | Password input for API key + `keySet` indicator |
