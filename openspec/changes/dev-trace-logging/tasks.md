## 1. Foundation

- [x] 1.1 Add `RAG_DEV_TRACE: Literal["off", "summary", "verbose"] = "off"` field to `apps/api/app/core/settings.py`
- [x] 1.2 Create `apps/api/app/core/dev_trace.py` with `DevTracer` class — `enabled` property, `mode` property, `_tail()` helper (last 300 chars), `_emit()`, `_format_summary()`, `_format_verbose()` (NDJSON), and `async op()` context manager with `verbose_meta` support
- [x] 1.3 Add `get_tracer()` singleton factory in `dev_trace.py` — lazy init from `settings.RAG_DEV_TRACE` on first call
- [x] 1.4 Add startup banner in `apps/api/app/workers/main.py` — print `[DEV] dev trace active mode=<mode>` to stdout when `RAG_DEV_TRACE` is not `"off"`

## 2. Ingestion Stage Instrumentation

- [x] 2.1 Instrument `apps/api/app/workers/stages/parse.py` — wrap parse operation with `tracer.op("ingestion.parse", version_id=..., chars=..., verbose_meta={...})`
- [x] 2.2 Instrument `apps/api/app/workers/stages/chunk.py` — wrap chunk operation with `tracer.op("ingestion.chunk", version_id=..., chunks=..., strategy=..., chunk_size=..., verbose_meta={...})`
- [x] 2.3 Instrument `apps/api/app/workers/stages/embed.py` — wrap embed operation with `tracer.op("ingestion.embed", version_id=..., vectors=..., dim=..., verbose_meta={...})`
- [x] 2.4 Instrument `apps/api/app/workers/stages/index.py` — wrap index operation with `tracer.op("ingestion.index", version_id=..., upserted=..., collection=..., verbose_meta={...})`
- [x] 2.5 Instrument `apps/api/app/workers/stages/validate.py` — wrap validate operation with `tracer.op("ingestion.validate", version_id=..., final_state=..., vectors=..., verbose_meta={...})`

## 3. Query Pipeline Instrumentation

- [x] 3.1 Instrument `plan_query()` call in `apps/api/app/application/rag_query_service.py` — emit `"query.plan"` with `route`, `standalone`, `ms`
- [x] 3.2 Instrument evidence context assembly in `rag_query_service.py` — emit `"query.evidence"` with `chunks`, `tokens`, `budget`, and `gated` (verbose only)
- [x] 3.3 Instrument `apps/api/app/application/query_decomposer.py` — wrap LLM call with `tracer.op("query.decompose", count=..., system_tail=..., user_tail=..., verbose_meta={"sub_queries": ...})`
- [x] 3.4 Instrument `apps/api/app/application/query_planner.py` — wrap LLM call with `tracer.op("query.plan_tasks", count=..., types=..., system_tail=..., user_tail=..., verbose_meta={"tasks": ...})`
- [x] 3.5 Instrument `apps/api/app/application/rag_generation.py` — emit `"query.llm_context"` after prompt assembly (with `system_tail`, `user_tail`, `history_turns`, and `token_estimate` in verbose) and `"query.generation"` after LLM responds (with `facts`, `inferences`, `conflicts`, `limitations`, `ms`)

## 4. Verification

- [x] 4.1 Deterministic smoke coverage for `RAG_DEV_TRACE=summary` — `tests/test_dev_trace.py` confirms human-readable `[DEV] <event> ... ms=` output and compact list rendering
- [x] 4.2 Deterministic smoke coverage for `RAG_DEV_TRACE=verbose` — `tests/test_dev_trace.py` confirms NDJSON, timing, verbose metadata, and prompt-tail redaction
- [x] 4.3 Query instrumentation regression coverage — the full API suite exercises query planning, evidence assembly, and generation with the updated trace calls
- [x] 4.4 Query decomposition/planner regression coverage — targeted decomposer/planner tests and the full API suite exercise the timed LLM spans and verbose metadata paths
- [x] 4.5 Confirm `RAG_DEV_TRACE=off` (default) produces zero trace output — `tests/test_dev_trace.py` asserts no stdout for both context-manager and point-in-time events

### Verification notes

- `uv run ruff check app tests` passed.
- `uv run python -m mypy app` passed with no issues.
- `uv run python -m pytest -q` passed: 440 passed, 17 skipped.
- `openspec validate dev-trace-logging --type change --strict` passed.
- Live provider/Qdrant smoke was not run because the local API and dependent services were not running.
