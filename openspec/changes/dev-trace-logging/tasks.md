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

- [ ] 4.1 Manual smoke test ingestion with `RAG_DEV_TRACE=summary` — confirm all 5 stage events appear on stdout in `[DEV] ingestion.<stage> ...` format
- [ ] 4.2 Manual smoke test ingestion with `RAG_DEV_TRACE=verbose` — confirm NDJSON lines with `version_id`, `ms`, and stage-specific fields
- [ ] 4.3 Manual smoke test query with `RAG_DEV_TRACE=summary` — confirm `query.plan`, `query.evidence`, `query.generation` summary lines appear
- [ ] 4.4 Manual smoke test query with `RAG_DEV_TRACE=verbose` — confirm NDJSON with `system_tail`, `user_tail`, `sub_queries` (if decomposition triggered), `tasks` (if planner triggered)
- [ ] 4.5 Confirm `RAG_DEV_TRACE=off` (default) produces zero trace output — no `[DEV]` lines on stdout during ingestion or query
