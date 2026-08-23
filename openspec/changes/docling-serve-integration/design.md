# Design: docling-serve-integration

## Context

See `proposal.md` — Why for motivation.

Current state:
- `DoclingParserAdapter` runs docling conversion in-process, requiring `uv sync --extra parsing` in the worker image.
- `parse_document()` in `apps/api/app/workers/stages/parse.py` already has a `_parse_with_docling_or_fallback()` helper that handles the in-process → pdfminer chain.
- `httpx` is already a core dependency in `apps/api/pyproject.toml` — no new HTTP client needed.
- `Settings` uses `pydantic-settings` with `BaseSettings` and has established patterns for field validators and model validators.
- `dev_trace` (`get_tracer()`) is already used in `parse_document()` via `tracer.op("ingestion.parse", ...)` — new adapter must integrate the same way.
- `docling-serve` REST API: `POST /v1/convert/file/async` → `GET /v1/status/poll/{task_id}` → `GET /v1/result/{task_id}`. Observed conversion time: ~98 s for a 10-page PDF. Default timeout: 120 s.

## Goals / Non-Goals

**Goals:**
- Drop-in `DoclingServeAdapter` that implements `DocumentParser` port via HTTP.
- Zero change to domain or application layer contracts.
- Parse stage prefers serve adapter when `DOCLING_SERVE_URL` is set.
- Shared `httpx.AsyncClient` — no new connection per job.
- Full `dev_trace` integration matching existing stage patterns.
- Settings validation at startup — misconfigured URL fails fast.

**Non-Goals:**
- Streaming result or websocket polling.
- Retry logic inside the adapter (BullMQ handles job-level retries).
- Replacing the in-process adapter (remains as fallback).
- Supporting docling-serve endpoints beyond `convert/file/async`.
- Silent fallback from serve adapter to in-process adapter.

## Decisions

### 1. Constructor-injected `httpx.AsyncClient` (not created inside `parse()`)

Creating a new `httpx.AsyncClient` per job wastes connections and bypasses OS TCP
keep-alive. The parse stage owns a module-level `_http_client: httpx.AsyncClient | None`
initialized lazily on first use and passed to each `DoclingServeAdapter` instance.

The client is configured with:
- `timeout=httpx.Timeout(connect=10.0, read=settings.docling_serve_timeout_seconds, write=60.0, pool=5.0)`

This covers large file uploads (write=60 s) and long conversions (read=timeout).

Alternative: adapter owns client lifecycle with `async with`. Rejected — creates a new
TCP connection for every job, negates connection pooling.

### 2. `md_content` lines → `DocumentElement` with proper `ParserQualitySummary`

The serve result returns `md_content` (markdown string) and a `confidence` object with
`mean_score`, `parse_score`, `layout_score`. Mapping:

- Each non-empty line → `DocumentElement(type="paragraph", ...)`
- `ParserQualitySummary.aggregate_confidence` ← `confidence.mean_score`
- `ParserQualitySummary.text_coverage` ← `confidence.parse_score`
- `ParserQualitySummary.page_coverage` ← `confidence.layout_score`
- `ParserQualitySummary.element_count` ← len(elements)
- `ParserQualitySummary.empty_element_ratio` ← computed from elements

This makes the quality gate downstream work correctly with the serve adapter output,
consistent with what `map_docling_to_elements()` produces for the in-process adapter.

Alternative: parse markdown AST for heading hierarchy. Rejected — adds `mistletoe`
dependency; chunker doesn't consume hierarchy from the serve path yet.

### 3. No silent fallback from serve adapter to in-process

If `DOCLING_SERVE_URL` is set and the serve adapter raises, the error propagates.
Silent fallback would mask misconfiguration (serve URL set but serve is down) and make
observability harder. Operator should fix serve URL or unset it.

### 4. Three new `Settings` fields with validators

```python
docling_serve_url: str | None = None
docling_serve_timeout_seconds: float = 120.0
docling_serve_poll_interval_seconds: float = 3.0
```

`docling_serve_url` validated as HTTP/HTTPS URL when set (fail fast at startup, not at
first job). Timeout and poll interval validated as positive floats — same pattern as
`rag_query_timeout_seconds`.

### 5. `dev_trace` span wraps serve adapter call

Following existing `tracer.op("ingestion.parse", ...)` pattern in the stage.
New span: `tracer.op("ingestion.parse.docling_serve", version_id=..., task_id=..., chars=...)`.
This gives operators visibility into serve latency in dev trace output without
touching domain or application layer.

### 6. First poll is immediate (no initial sleep)

Submit → poll immediately → if not done, sleep interval → poll again. This cuts ~3 s
from fast documents (short PDFs often complete in under 10 s on warm serve).

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| docling-serve is down or unreachable | Error propagates; BullMQ retries job. Operator monitors serve container health. |
| Large files take >120 s | `DOCLING_SERVE_TIMEOUT_SECONDS` is a settings field; operator can increase it. Default 120 s covers observed ~98 s. |
| `md_content` line-based mapping loses table structure | Tables render as markdown pipe tables in `md_content` — chunker handles them as text. Full structured mapping deferred. |
| `httpx.AsyncClient` not closed on worker shutdown | Module-level client has no explicit close. Acceptable — Python GC handles it on process exit. For graceful shutdown, worker main can call `await _http_client.aclose()` in the future. |
| URL validator rejects valid edge-case URLs | Validator uses `httpx.URL` parsing — same library used for requests, guaranteed consistent. |

## Migration Plan

1. Add three settings fields to `Settings` with validators.
2. Create `apps/api/app/infrastructure/rag/parsers/docling_serve_adapter.py`.
3. Add module-level `_http_client` and update `_parse_with_docling_or_fallback()` in parse stage.
4. Set `DOCLING_SERVE_URL=http://localhost:5001` in `.env` to activate.
5. No DB migration, no queue changes, no frontend changes.

**Rollback:** Unset `DOCLING_SERVE_URL` — parse stage reverts to in-process adapter automatically. Zero downtime.

## Open Questions

None.
