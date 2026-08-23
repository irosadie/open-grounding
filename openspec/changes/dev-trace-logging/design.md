## Context

The RAG pipeline (ingestion + query) is a multi-stage async system built on BullMQ workers and FastAPI. During development, there is no visibility into what happens inside each stage — log level is hardcoded to `INFO`, LLM prompts are never logged, ingestion stage timing is invisible, and query plan decisions are silent. Every module uses stdlib `logging` independently with no shared utility.

The pipeline has two distinct flows:
- **Ingestion**: `parse → chunk → embed → index → validate` — five BullMQ workers, each chaining to the next
- **Query**: `plan → (decompose | plan_tasks) → retrieve → evidence → generate` — orchestrated in `RagQueryService`, with optional LLM calls in decomposer and planner before the main generation call

Current constraints:
- All workers run as async Python (asyncio + bullmq)
- `Settings` (pydantic-settings) is the single config source; env vars are the injection point
- No existing debug/trace infrastructure; `logging.basicConfig(level=INFO)` hardcoded in `workers/main.py`
- `RAG_RUNTIME_MODE` already exists but is unused for log control

## Goals / Non-Goals

**Goals:**
- Single `DevTracer` utility — one place to add/change trace behaviour, zero duplication
- Two modes: `summary` (human-readable one-liners) and `verbose` (NDJSON, machine-parseable)
- Per-operation timing via async context manager wrapping the actual work
- LLM prompt visibility with last-300-char tail only (system + user)
- Zero overhead when disabled — no string formatting, no I/O, no timing calls
- Controlled by one env var: `RAG_DEV_TRACE=off|summary|verbose`
- Emits to stdout only (no file, no external sink)

**Non-Goals:**
- Not a production observability solution (no OpenTelemetry, no Langfuse, no metrics sink)
- Not a persistent trace store — stdout only, consumer's responsibility to redirect
- Not a replacement for existing `logging` — existing `logger.info/debug` calls are untouched
- No frontend visibility or UI changes
- No changes to API contracts, schemas, or DB models
- No test coverage required for trace output format (dev-only utility)

## Decisions

### D1: Single module `core/dev_trace.py` with singleton via `get_tracer()`

**Chosen:** One file, one class `DevTracer`, one `get_tracer()` factory that returns a module-level singleton initialised from `settings.RAG_DEV_TRACE` on first call.

**Alternatives considered:**
- _Middleware/decorator pattern_: Would require wrapping entire functions, losing per-operation granularity inside a stage
- _Separate logger name `dev_trace`_: Piggybacks on stdlib logging but forces `logging.DEBUG` globally to see output — pollutes other debug logs; also logging formatters are less flexible for JSON output
- _Context var (asyncio ContextVar)_: Useful for request-scoped tracing but unnecessary here — all trace events are fire-and-forget with no correlation needed across concurrent jobs

**Rationale:** Singleton is simplest. Ingestion workers are process-level singletons anyway. The tracer doesn't need request/job scope — it's a global dev switch.

### D2: Async context manager `tracer.op(event, **meta)` for timing

**Chosen:** `async with tracer.op("ingestion.embed", version_id=vid, count=n):` — the block wraps the actual work, duration is measured on `__aexit__`, event emitted there.

**Alternatives considered:**
- _Manual `start = time.monotonic()` + `tracer.emit()`_: More lines per instrumentation site, easy to forget the emit or get the timing wrong
- _Decorator `@tracer.traced`_: Can't easily inject dynamic meta (e.g. chunk count only known after the work runs)

**Rationale:** Context manager allows meta to be passed at entry and augmented at exit (e.g. actual count after processing). Keeps instrumentation at the call site minimal — one `async with` wrapping existing code.

### D3: Mode-conditional meta fields (verbose-only fields)

**Chosen:** `tracer.op()` accepts a `verbose_meta` kwarg dict. Fields in `verbose_meta` are only included when `mode == "verbose"`. This keeps summary lines concise without duplicating emit calls.

```python
async with tracer.op(
    "query.decompose",
    count=len(sub_queries),
    verbose_meta={"sub_queries": sub_queries},
):
```

**Rationale:** One instrumentation site per event, no `if tracer.mode == "verbose"` scattered in business code.

### D4: Prompt tail — last 300 chars, keys `system_tail` / `user_tail`

**Chosen:** `_tail(text, n=300)` helper in `dev_trace.py`. Passed as regular meta fields.

**Alternatives considered:**
- _First 300 chars_: Less useful — prompts typically have generic preamble at the start; the last 300 chars shows the actual query/evidence being sent
- _Full prompt in verbose_: Too large (evidence context alone can be 8k tokens / ~32k chars); would flood stdout

**Rationale:** Last 300 chars captures the operative part of the prompt — the actual question or final evidence block — which is what's needed for debugging.

### D5: Output to stdout, not stderr

**Chosen:** `print()` to stdout (or `sys.stdout.write`).

**Rationale:** Dev traces are structured data the developer may want to pipe (`| grep query.llm_context | jq`). stderr is for errors. stdout is correct for structured observability output.

## Implementation Map

```
apps/api/app/core/dev_trace.py          ← NEW: DevTracer + get_tracer()
apps/api/app/core/settings.py           ← ADD: RAG_DEV_TRACE field
apps/api/app/workers/stages/parse.py    ← INSTRUMENT: ingestion.parse
apps/api/app/workers/stages/chunk.py    ← INSTRUMENT: ingestion.chunk
apps/api/app/workers/stages/embed.py    ← INSTRUMENT: ingestion.embed
apps/api/app/workers/stages/index.py    ← INSTRUMENT: ingestion.index
apps/api/app/workers/stages/validate.py ← INSTRUMENT: ingestion.validate
apps/api/app/application/rag_query_service.py    ← INSTRUMENT: query.plan, query.evidence
apps/api/app/application/query_decomposer.py     ← INSTRUMENT: query.decompose
apps/api/app/application/query_planner.py        ← INSTRUMENT: query.plan_tasks
apps/api/app/application/rag_generation.py       ← INSTRUMENT: query.llm_context, query.generation
```

### `DevTracer` sketch

```python
class DevTracer:
    def __init__(self, mode: Literal["off", "summary", "verbose"]):
        self._mode = mode
        self._enabled = mode != "off"

    @property
    def enabled(self) -> bool: ...

    @property
    def mode(self) -> str: ...

    @contextlib.asynccontextmanager
    async def op(self, event: str, verbose_meta: dict | None = None, **meta):
        if not self._enabled:
            yield; return
        t0 = time.monotonic()
        yield
        ms = round((time.monotonic() - t0) * 1000, 1)
        self._emit(event, ms, meta, verbose_meta or {})

    def _emit(self, event, ms, meta, verbose_meta): ...
    def _format_summary(self, event, ms, meta) -> str: ...
    def _format_verbose(self, event, ms, meta, verbose_meta) -> str: ...
```

## Risks / Trade-offs

- **[Risk] Concurrent jobs interleave trace lines** → stdout lines from concurrent BullMQ workers (concurrency=4 for ingestion) may interleave. Mitigation: each `print()` is a single atomic write in CPython for reasonable line lengths; NDJSON consumers can filter by `version_id` or `job_id` in meta.

- **[Risk] Verbose mode in high-throughput embed stage** → embed stage processes batches; if concurrency=4 and batch=128 chunks each, verbose output could be large. Mitigation: tracer is dev-only; documented that `verbose` should not be used with large ingestion jobs without stdout redirection.

- **[Risk] `get_tracer()` called before settings initialised** → If imported at module level before settings are loaded. Mitigation: `get_tracer()` is lazy — first call initialises from settings; never called at import time.

- **[Trade-off] No job/request correlation ID in events** → Trace events have `version_id` or `query_id` as meta but no unified trace ID across all events for one job. Acceptable for dev use; full correlation would require propagating a trace context through every call which is out of scope.

## Open Questions

- Should `query_id` / `job_id` be automatically injected into every trace event, or left to the instrumentation site to pass as meta? (Recommendation: leave to site — keeps `DevTracer` generic.)
- Should `workers/main.py` print a startup banner when `RAG_DEV_TRACE` is active? (e.g. `[DEV] dev trace active mode=verbose`) — low effort, good UX signal.
