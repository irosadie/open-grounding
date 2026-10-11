# Tasks: kb-parser-config

## 1. Domain Entity

- [x] 1.1 Add `parser: str` (default `"auto"`) and `docling_serve_url: str | None` (default `None`) to `IngestionConfig` dataclass in `apps/api/app/domain/rag/catalog.py`
- [x] 1.2 Update `INGESTION_CONFIG_DEFAULTS` with `parser="auto"` and `docling_serve_url=None`
- [x] 1.3 Update `IngestionConfigRepository.upsert()` protocol to accept `parser: str` and `docling_serve_url: str | None`

## 2. Database Migration

- [x] 2.1 Create `apps/api/alembic/versions/20260823_01_kb_parser_config.py` — add `parser VARCHAR(32) NOT NULL DEFAULT 'auto'` and `docling_serve_url VARCHAR(2048) NULL` to `rag_kb_ingestion_configs`
- [x] 2.2 Implement `downgrade()` to drop both columns
- [x] 2.3 Run `uv run alembic upgrade head` and verify migration applies cleanly (verified via `uv run python -m alembic upgrade head`; the console wrapper is unavailable in this environment)

## 3. Infrastructure (ORM + Repository)

- [x] 3.1 Add `parser` and `docling_serve_url` columns to `IngestionConfigRecord` in `apps/api/app/infrastructure/rag_catalog.py`
- [x] 3.2 Update `_to_ingestion_config()` to map new columns
- [x] 3.3 Update `SqlAlchemyIngestionConfigRepository.upsert()` to accept and persist `parser` and `docling_serve_url`

## 4. Application Service

- [x] 4.1 Add `parser: str = "auto"` and `docling_serve_url: str | None = None` to `IngestionConfigService.upsert_config()` signature
- [x] 4.2 Add `IngestionConfigResult.parser` and `IngestionConfigResult.docling_serve_url` fields
- [x] 4.3 Update `_to_result()` to include new fields
- [x] 4.4 Add validation in `upsert_config()`: reject unknown `parser` values with `DomainError("VALIDATION_ERROR", ..., 422)`
- [x] 4.5 Add validation: when `parser="docling_serve"`, `docling_serve_url` must be non-empty HTTP/HTTPS URL, else `DomainError("VALIDATION_ERROR", ..., 422)`

## 5. API Layer

- [x] 5.1 Add `parser: Literal["auto", "docling_serve", "docling_inprocess", "pdfminer"] = "auto"` and `docling_serve_url: str | None = None` to `IngestionConfigWriteRequest` in `schemas.py`
- [x] 5.2 Add `parser: str` and `docling_serve_url: str | None` to `IngestionConfigResponse` in `schemas.py`
- [x] 5.3 Update route handler in `routes.py` to pass `parser` and `docling_serve_url` to service
- [x] 5.4 Update `_to_response()` (or equivalent) to include new fields in response

## 6. Parse Stage

- [x] 6.1 Update `_parse_with_docling_or_fallback()` signature to accept `cfg: IngestionConfig`
- [x] 6.2 Add `"docling_serve"` branch: use `cfg.docling_serve_url` first, fallback to `settings.docling_serve_url`; raise `DomainError("DOCLING_SERVE_URL_NOT_CONFIGURED", ..., 500)` if neither set
- [x] 6.3 Add `"docling_inprocess"` branch: use `DoclingParserAdapter` directly, propagate `PARSER_NOT_INSTALLED` without pdfminer fallback
- [x] 6.4 Add `"pdfminer"` branch: call `_extract_text()` directly
- [x] 6.5 Keep `"auto"` branch as existing chain (serve → in-process → pdfminer)
- [x] 6.6 Pass `cfg` from `parse_document()` into `_parse_with_docling_or_fallback()`

## 7. Frontend — Shared Packages

- [x] 7.1 Add `parser` (`z.enum(["auto", "docling_serve", "docling_inprocess", "pdfminer"]).default("auto")`) and `doclingServeUrl` (`z.string().nullable().default(null)`) to `ingestionConfigSchema` in `packages/schemas/ingestion-config.ts`
- [x] 7.2 Add `parser: string` and `doclingServeUrl: string | null` to `IngestionConfigResponse` in `packages/types/ingestion-config-response.ts`

## 8. Frontend — Hook

- [x] 8.1 Add `parser` and `docling_serve_url` fields to the `mutationFn` data mapping in `apps/web/hooks/transactions/use-ingestion-config/index.ts`

## 9. Frontend — UI

- [x] 9.1 Add `parser` select field (options: Auto, Docling Serve, Docling In-Process, pdfminer) to ingestion config form in `apps/web/app/console/knowledge-bases/[id]/ingestion/ingestion-content.tsx`
- [x] 9.2 Add conditional `docling_serve_url` text input — visible only when `parser === "docling_serve"`
- [x] 9.3 Display current `parser` and `doclingServeUrl` values when loading existing config

## 10. Tests

- [x] 10.1 Unit test: `upsert_config()` with valid `parser="docling_serve"` + URL → persisted correctly
- [x] 10.2 Unit test: `upsert_config()` with `parser="docling_serve"` + no URL → `DomainError(VALIDATION_ERROR)`
- [x] 10.3 Unit test: `upsert_config()` with unknown `parser` value → `DomainError(VALIDATION_ERROR)`
- [x] 10.4 Unit test: parse stage `parser="docling_serve"` uses KB URL over Settings URL
- [x] 10.5 Unit test: parse stage `parser="docling_serve"` falls back to Settings URL when KB URL absent
- [x] 10.6 Unit test: parse stage `parser="docling_serve"` with no URL → `DomainError(DOCLING_SERVE_URL_NOT_CONFIGURED)`
- [x] 10.7 Unit test: parse stage `parser="docling_inprocess"` → `DoclingParserAdapter` used, no serve adapter
- [x] 10.8 Unit test: parse stage `parser="pdfminer"` → `_extract_text()` called directly
- [x] 10.9 Unit test: parse stage `parser="auto"` → existing chain preserved

## 11. Verification

- [x] 11.1 Run `uv run alembic upgrade head` — migration applies cleanly (verified via `uv run python -m alembic upgrade head`)
- [x] 11.2 Run `cd apps/api && uv run python -m pytest tests/ -x -q` — all tests pass
- [ ] 11.3 Manual: set `parser="docling_serve"` + URL on a KB via API, trigger ingestion, confirm serve adapter used
- [ ] 11.4 Manual: set `parser="auto"` on a KB, confirm fallback chain works as before

> 11.3–11.4 are kept pending because no live docling-serve/API ingestion environment was available in this session; the equivalent adapter-selection paths are covered by the automated tests above.
