## Why

Developer visibility into the RAG pipeline is essentially zero during development — log level is hardcoded to `INFO`, LLM prompts are never logged, ingestion stage timing is invisible, and query plan decisions (route, decomposition, planner activation) are silent. Debugging pipeline behavior requires either adding temporary print statements or guessing from output. This blocks fast iteration on ingestion config, chunking strategy, prompt tuning, and retrieval quality.

## What Changes

- Introduce a `DevTracer` utility (`apps/api/app/core/dev_trace.py`) — the single source of truth for all dev trace emission; handles mode detection, formatting, and stdout output
- Add `RAG_DEV_TRACE` env flag to `Settings`: `off` (default) | `summary` | `verbose`
- Instrument ingestion pipeline stages (parse, chunk, embed, index, validate) with per-operation timing traces
- Instrument query pipeline (plan, decompose, planner, evidence build, LLM context, generation) with per-step traces
- In `verbose` mode: emit full structured JSON per event including prompt previews (last 300 chars of system + user prompt), token counts, chunk counts, sub-query list
- In `summary` mode: emit single-line human-readable summary per stage/step with key metrics only
- No impact on production behavior — tracer is a no-op when `RAG_DEV_TRACE` is unset or `off`

## Capabilities

### New Capabilities

- `dev-trace-logging`: Structured dev observability layer for ingestion and query pipelines, activated via `RAG_DEV_TRACE=summary|verbose`, emitting per-operation timing and LLM context visibility to stdout

### Modified Capabilities

- `rag-ingestion-orchestration-and-indexing`: Ingestion stage workers now emit dev trace events per operation (parse, chunk, embed, index, validate) when tracer is active
- `rag-grounded-answer-generation`: Generation service emits LLM context trace (prompt preview, token estimate) in verbose mode
- `rag-query-decomposition`: Decomposer emits sub-query count and list in trace
- `rag-query-task-planner`: Planner emits task breakdown in trace
- `rag-query-security-and-planning`: `plan_query` result (route, standalone) emitted in trace

## Impact

- **New file:** `apps/api/app/core/dev_trace.py` — `DevTracer` class + `get_tracer()` singleton factory
- **Modified:** `apps/api/app/core/settings.py` — add `RAG_DEV_TRACE: Literal["off", "summary", "verbose"] = "off"`
- **Modified:** `apps/api/app/workers/stages/parse.py`, `chunk.py`, `embed.py`, `index.py`, `validate.py` — wrap key operations with `tracer.op()`
- **Modified:** `apps/api/app/application/rag_query_service.py` — trace plan, decompose, evidence, generation steps
- **Modified:** `apps/api/app/application/query_decomposer.py` — trace LLM call + result
- **Modified:** `apps/api/app/application/query_planner.py` — trace LLM call + task breakdown
- **Modified:** `apps/api/app/application/rag_generation.py` — trace prompt assembly + LLM call
- **No API contract changes**, no schema changes, no migration needed
- **Zero production overhead** — all trace code guarded by `if self._enabled` check before any work
