# Proposal: docling-serve-integration

## Why

The current `DoclingParserAdapter` runs docling conversion **in-process** inside the
ingestion worker, requiring the heavy ML dependency (`uv sync --extra parsing`) to be
installed in the API/worker image. This bloats the container, slows cold-start, and
couples the parser runtime to the worker process. A `docling-serve` instance is already
running at `http://localhost:5001` (Docker container, `quay.io/docling-project/docling-serve:latest`)
and exposes a stable async REST API — the right place to offload heavy PDF conversion.

## What Changes

- Add a new `DoclingServeAdapter` that calls `docling-serve` via HTTP instead of running
  docling in-process.
- The adapter uses the `/v1/convert/file/async` endpoint to submit a job and polls
  `/v1/status/poll/{task_id}` until completion, then fetches `/v1/result/{task_id}`.
- The adapter implements the same `DocumentParser` port as `DoclingParserAdapter` —
  same interface, drop-in replacement.
- The parse stage (`apps/api/app/workers/stages/parse.py`) is updated to prefer
  `DoclingServeAdapter` when `DOCLING_SERVE_URL` is set, falling back to the existing
  in-process adapter if not.
- `DOCLING_SERVE_URL` is added to `Settings` (env var, optional, default `None`).
- The `parsing` optional dependency in `pyproject.toml` remains unchanged — in-process
  fallback still works when docling-serve is not available.

## Capabilities

### New Capabilities

- `rag-docling-serve-adapter`: HTTP-based document parser adapter that delegates
  conversion to a remote `docling-serve` instance via async REST API, implements the
  `DocumentParser` port, and is selected by the parse stage when `DOCLING_SERVE_URL` is
  configured.

### Modified Capabilities

- `docling-parser-integration`: Parse stage selection logic changes — `DoclingServeAdapter`
  is now tried first when `DOCLING_SERVE_URL` is set, before falling back to the
  in-process `DoclingParserAdapter` or pdfminer.

## Impact

| Area | Change |
|---|---|
| `apps/api/app/infrastructure/rag/parsers/docling_serve_adapter.py` | New file — HTTP adapter |
| `apps/api/app/workers/stages/parse.py` | Update `_parse_with_docling_or_fallback` to check `DOCLING_SERVE_URL`; integrate dev_trace |
| `apps/api/app/core/settings.py` | Add `docling_serve_url`, `docling_serve_timeout_seconds`, `docling_serve_poll_interval_seconds` |
| `apps/api/pyproject.toml` | `httpx` already a core dep — no change needed |
| `apps/api/tests/` | Unit tests for `DoclingServeAdapter` (mocked `httpx`) + parse stage routing tests |
