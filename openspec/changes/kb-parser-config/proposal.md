# Proposal: kb-parser-config

## Why

The docling-serve integration is currently controlled by a server-side env var
(`DOCLING_SERVE_URL`) that applies globally to all ingestion jobs. There is no way for
an admin to enable or disable docling-serve on a per-knowledge-base basis without
restarting the server. Per-KB parser configuration stored in the database gives admins
fine-grained control over which parser is used for each KB, without touching env vars
or deployment config.

## What Changes

- Extend `IngestionConfig` domain entity with two new fields:
  - `parser`: `"auto" | "docling_serve" | "docling_inprocess" | "pdfminer"` (default `"auto"`)
  - `docling_serve_url`: `str | None` (default `None`) — KB-level override for the serve URL
- Extend `IngestionConfigRecord` (SQLAlchemy ORM) with the same two columns.
- Add Alembic migration to add `parser` and `docling_serve_url` columns to `rag_kb_ingestion_configs`.
- Update `IngestionConfigRepository.upsert()` protocol and implementation to accept the new fields.
- Update `IngestionConfigService.upsert_config()` to accept and validate the new fields.
- Update parse stage to read parser config from `IngestionConfig` and select adapter accordingly:
  - `"docling_serve"` → use `DoclingServeAdapter` with KB-level URL (fallback to `Settings.docling_serve_url`)
  - `"docling_inprocess"` → use `DoclingParserAdapter`
  - `"pdfminer"` → use pdfminer fallback directly
  - `"auto"` → existing fallback chain (serve → in-process → pdfminer)
- Update API schema (request/response) and route for ingestion config upsert to expose new fields.
- Update frontend ingestion config form to show parser selector and optional URL field.

## Capabilities

### New Capabilities

- `kb-parser-config`: Per-KB parser selection and docling-serve URL stored in DB,
  editable by admin, consumed by the parse stage to select the correct adapter.

### Modified Capabilities

- `docling-parser-integration`: Parse stage adapter selection now reads from
  `IngestionConfig.parser` instead of only checking `Settings.docling_serve_url`.
- `kb-ingestion-settings`: Ingestion config entity, repository, service, and API
  gain `parser` and `docling_serve_url` fields.

## Impact

| Area | Change |
|---|---|
| `apps/api/app/domain/rag/catalog.py` | Add `parser` and `docling_serve_url` to `IngestionConfig` + `INGESTION_CONFIG_DEFAULTS` |
| `apps/api/app/infrastructure/rag_catalog.py` | Add columns to `IngestionConfigRecord`, update `_to_ingestion_config`, update `upsert` |
| `apps/api/app/domain/rag/catalog.py` | Update `IngestionConfigRepository` protocol |
| `apps/api/app/application/ingestion_config_service.py` | Accept + validate new fields |
| `apps/api/app/interfaces/http/schemas.py` | Add `parser` + `docling_serve_url` to request/response schemas |
| `apps/api/app/interfaces/http/routes.py` | Pass new fields through to service |
| `apps/api/app/workers/stages/parse.py` | Read `cfg.parser` + `cfg.docling_serve_url` to select adapter |
| `apps/api/alembic/versions/` | New migration: add columns to `rag_kb_ingestion_configs` |
| `apps/web/` | Update ingestion settings form/hook/schema to expose parser config |
