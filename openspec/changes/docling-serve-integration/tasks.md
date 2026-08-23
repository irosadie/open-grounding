# Tasks: docling-serve-integration

## 1. Settings

- [x] 1.1 Add `docling_serve_url: str | None = None` to `Settings` in `apps/api/app/core/settings.py`
- [x] 1.2 Add `docling_serve_timeout_seconds: float = 120.0` to `Settings`
- [x] 1.3 Add `docling_serve_poll_interval_seconds: float = 3.0` to `Settings`
- [x] 1.4 Add `@field_validator("docling_serve_url")` — validate non-empty HTTP/HTTPS URL using `httpx.URL` when set, raise `ValueError` with clear message if invalid
- [x] 1.5 Add `@field_validator("docling_serve_timeout_seconds", "docling_serve_poll_interval_seconds")` — validate positive float, same pattern as `rag_query_timeout_seconds`

## 2. DoclingServeAdapter

- [x] 2.1 Create `apps/api/app/infrastructure/rag/parsers/docling_serve_adapter.py`
- [x] 2.2 Define `DoclingServeAdapter.__init__(self, *, base_url: str, expected_tenant_id: str, profile: ParserProfile, http_client: httpx.AsyncClient, poll_interval: float, timeout: float)`
- [x] 2.3 Implement tenant scope assertion via `assert_tenant_scope` before any HTTP call
- [x] 2.4 Implement MIME type guard using `SUPPORTED_MIME_TYPES` before any HTTP call
- [x] 2.5 Implement `_submit(source: bytes, mime_type: str) -> str` — POST multipart to `/v1/convert/file/async`, return `task_id`, raise `DomainError("DOCLING_SERVE_SUBMIT_ERROR", ...)` on non-2xx with status + body in `details`
- [x] 2.6 Implement `_poll(task_id: str) -> None` — GET `/v1/status/poll/{task_id}` with immediate first poll then `asyncio.sleep(poll_interval)`; raise `DomainError("DOCLING_SERVE_TASK_FAILED", ...)` with `task_id` and `error_message` in `details` on `failed`; raise `DomainError("DOCLING_SERVE_TIMEOUT", ...)` with `task_id` and elapsed seconds on timeout; raise `DomainError("DOCLING_SERVE_POLL_ERROR", ...)` on non-2xx poll response
- [x] 2.7 Implement `_fetch_result(task_id: str) -> dict` — GET `/v1/result/{task_id}`, raise `DomainError("DOCLING_SERVE_RESULT_ERROR", ...)` on non-2xx
- [x] 2.8 Implement `_map_to_parsed_document(result: dict) -> ParsedDocument` — map non-empty `md_content` lines to `DocumentElement(type="paragraph", ...)` with deterministic IDs; populate `ParserQualitySummary` from `confidence` object (`mean_score` → `aggregate_confidence`, `parse_score` → `text_coverage`, `layout_score` → `page_coverage`); handle absent `confidence` gracefully with `None` / `0.0` defaults
- [x] 2.9 Wire `parse()` method: assert scope → guard MIME → submit → poll → fetch → map → return `ParsedDocument`

## 3. Parse Stage Integration

- [x] 3.1 Add module-level `_http_client: httpx.AsyncClient | None = None` and `_get_http_client(settings: Settings) -> httpx.AsyncClient` lazy initialiser in `parse.py` — configure with `httpx.Timeout(connect=10.0, read=settings.docling_serve_timeout_seconds, write=60.0, pool=5.0)`
- [x] 3.2 Update `_parse_with_docling_or_fallback()` signature to accept `settings: Settings`
- [x] 3.3 Add serve adapter branch: when `settings.docling_serve_url` is not `None`, instantiate `DoclingServeAdapter` with shared client and call `parse()` — propagate errors without swallowing
- [x] 3.4 Wrap `DoclingServeAdapter.parse()` call in `tracer.op("ingestion.parse.docling_serve", version_id=..., task_id=..., chars=..., elapsed_seconds=...)` span
- [x] 3.5 Pass `settings` from `parse_document()` into `_parse_with_docling_or_fallback()`

## 4. Tests

- [x] 4.1 Unit test: `DoclingServeAdapter.parse()` happy path — mock `httpx.AsyncClient`, assert returns `ParsedDocument` with correct elements and `ParserQualitySummary` populated from `confidence`
- [x] 4.2 Unit test: timeout path — mock poll never reaching terminal status → `DomainError(DOCLING_SERVE_TIMEOUT)` with `task_id` and elapsed in `details`
- [x] 4.3 Unit test: failed task path — mock poll returns `failed` → `DomainError(DOCLING_SERVE_TASK_FAILED)` with `error_message` in `details`
- [x] 4.4 Unit test: submit HTTP error → `DomainError(DOCLING_SERVE_SUBMIT_ERROR)` with status and body in `details`
- [x] 4.5 Unit test: poll HTTP error → `DomainError(DOCLING_SERVE_POLL_ERROR)`
- [x] 4.6 Unit test: result fetch HTTP error → `DomainError(DOCLING_SERVE_RESULT_ERROR)`
- [x] 4.7 Unit test: tenant mismatch → raises before any HTTP call (assert `httpx.AsyncClient.post` not called)
- [x] 4.8 Unit test: unsupported MIME type → raises before any HTTP call
- [x] 4.9 Unit test: empty `md_content` → `ParsedDocument` with zero elements, no raise
- [x] 4.10 Unit test: absent `confidence` in result → `ParserQualitySummary` with `None` / `0.0` defaults, no raise
- [x] 4.11 Unit test: parse stage routing — `DOCLING_SERVE_URL` set → `DoclingServeAdapter` used, `DoclingParserAdapter` NOT instantiated
- [x] 4.12 Unit test: parse stage routing — `DOCLING_SERVE_URL` absent → existing in-process path unchanged
- [x] 4.13 Unit test: Settings validator — invalid URL → `ValueError` at init
- [x] 4.14 Unit test: Settings validator — `docling_serve_timeout_seconds=0` → `ValueError` at init
- [x] 4.15 Unit test: shared client — `_get_http_client()` called twice returns same instance

## 5. Verification

- [x] 5.1 Run `cd apps/api && uv run pytest tests/ -x -q` — all tests pass
- [x] 5.2 Set `DOCLING_SERVE_URL=http://localhost:5001` in `.env`, trigger ingestion with a PDF, confirm `ingestion.parse.docling_serve` span appears in dev trace output (`RAG_DEV_TRACE=summary`)
- [x] 5.3 Unset `DOCLING_SERVE_URL`, re-trigger ingestion — confirm fallback to in-process adapter with no errors
