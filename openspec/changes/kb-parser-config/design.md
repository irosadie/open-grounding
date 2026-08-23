# Design: kb-parser-config

## Context

See `proposal.md` — Why for motivation.

Current state:
- `IngestionConfig` is a frozen dataclass in `app/domain/rag/catalog.py` with quality
  gate thresholds + `auto_review` flag.
- `IngestionConfigRecord` is a SQLAlchemy ORM model in `app/infrastructure/rag_catalog.py`
  backed by `rag_kb_ingestion_configs` table.
- `parse_document()` already loads `kb_config` from DB before parsing. The config is
  available in `_parse_with_docling_or_fallback()` — just not used for adapter selection yet.
- Latest migration: `20260808_01_kb_ingestion_config.py`. New migration will be
  `20260823_01_kb_parser_config.py`.
- Frontend: `apps/web/app/console/knowledge-bases/[id]/ingestion/ingestion-content.tsx`
  + hook at `apps/web/hooks/transactions/use-ingestion-config/index.ts`.

## Goals / Non-Goals

**Goals:**
- Add `parser` + `docling_serve_url` to domain entity, ORM, migration, service, API, frontend.
- Parse stage reads `cfg.parser` to select adapter — no more global env-only selection.
- `"auto"` preserves current behaviour exactly — zero breaking change for existing KBs.

**Non-Goals:**
- Removing `Settings.docling_serve_url` — it remains as global fallback for `"auto"` and
  `"docling_serve"` without KB-level URL.
- Supporting per-KB poll interval or timeout (deferred).
- UI for creating KBs with parser config in the same step (upsert flow is sufficient).

## Decisions

### 1. `parser` as `str` with allowed-values validation in service, not a DB enum

Using a Python `Literal` type alias and validating in the service layer keeps the DB
portable and avoids Alembic enum migration complexity. `VARCHAR(32) NOT NULL DEFAULT 'auto'`
is simple, reversible, and readable.

Allowed values: `"auto"`, `"docling_serve"`, `"docling_inprocess"`, `"pdfminer"`.

### 2. `docling_serve_url` is nullable VARCHAR(2048) — no FK, no encryption

It is a configuration URL, not a credential. No encryption needed. Length 2048 matches
browser URL limit. NULL = not configured.

### 3. Parse stage passes `cfg` into `_parse_with_docling_or_fallback()`

`cfg` is already loaded in `parse_document()`. Pass it alongside `settings` so the
helper can branch on `cfg.parser`. This is a minimal, surgical change — no new function,
no new abstraction.

### 4. `docling_serve` with no URL → explicit error, not silent fallback

If admin sets `parser="docling_serve"` on a KB but neither `cfg.docling_serve_url` nor
`Settings.docling_serve_url` is set, the job fails with a clear
`DOCLING_SERVE_URL_NOT_CONFIGURED` error. Silent fallback to pdfminer would mask
misconfiguration and produce unexpected lower-quality results.

### 5. Frontend: extend existing ingestion config form

The existing `ingestion-content.tsx` form already handles quality thresholds. Add a
`parser` select and conditional `docling_serve_url` text input below the existing
fields. Reuse existing `use-ingestion-config` hook — just extend the Zod schema and
types.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Existing KBs get `parser='auto'` after migration — behaviour unchanged | `DEFAULT 'auto'` in migration ensures zero-impact upgrade |
| Admin sets `docling_serve` but serve is down | Job fails with clear error; BullMQ retries. Same as current behaviour. |
| Frontend shows URL field for non-docling_serve parsers | Conditional render: URL input only visible when `parser === "docling_serve"` |
| `docling_serve_url` in DB is plaintext | It's a URL, not a secret. Acceptable. |

## Migration Plan

1. Add Alembic migration `20260823_01_kb_parser_config.py`:
   - `ALTER TABLE rag_kb_ingestion_configs ADD COLUMN parser VARCHAR(32) NOT NULL DEFAULT 'auto'`
   - `ALTER TABLE rag_kb_ingestion_configs ADD COLUMN docling_serve_url VARCHAR(2048) NULL`
   - Downgrade removes both columns.
2. Update domain → infrastructure → service → API → frontend in order.
3. No queue changes, no index changes, no other table changes.

**Rollback:** Alembic downgrade removes columns. Frontend and API changes are backward
compatible with old DB schema if rolled back before migration.

## Open Questions

None.
