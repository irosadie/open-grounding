# Design: worker-consolidation

## Architecture Overview

Before this change, two separate processes handle background jobs:

```
[BullMQ Producer]
      │
      ├─ bull:tool-execution:wait ──► [TypeScript Worker] ──HTTP──► POST /internal/tools/execute ──► Python
      ├─ bull:calibration:wait ──────► [TypeScript Worker] ──HTTP──► POST /internal/confidence/calibrate ──► Python
      ├─ bull:synthetic-fixture:wait ► [TypeScript Worker] ──HTTP──► POST /internal/confidence/fixtures/generate-synthetic ──► Python
      │
      └─ bull:ingestion.*:wait ──────► [Python Worker] (manual RPOPLPUSH/HGET/HSET/LPUSH)
         bull:memory.*:wait ─────────► [Python Worker] (manual RPOPLPUSH/HGET/HSET/LPUSH)
```

After this change, a single Python process handles all queues via proper BullMQ:

```
[BullMQ Producer]
      │
      ├─ bull:tool-execution:wait ─────────────────────────────────────────┐
      ├─ bull:calibration:wait ─────────────────────────────────────────── │
      ├─ bull:synthetic-fixture:wait ──────────────────────────────────── │
      ├─ bull:ingestion.parse:wait ────────────────────────────────────── │
      ├─ bull:ingestion.chunk:wait ────────────────────────────────────── ▼
      ├─ bull:ingestion.embed:wait ──────────► [Python Worker Process]
      ├─ bull:ingestion.index:wait ──────────►   bullmq.Worker × 10
      ├─ bull:ingestion.validate:wait ────────►   (python-bullmq 3.0.4)
      ├─ bull:memory.summarize:wait ──────────►   direct Python fn calls
      └─ bull:memory.prune:wait ──────────────►   no HTTP, no raw Redis
```

---

## Dependency

**`python-bullmq 3.0.4`** (PyPI: `bullmq`)

- Official Python port, MIT license, released 2026-08-05
- Pure Python, ~1 MB, depends only on `redis`
- Shares the same Lua scripts as the TypeScript `bullmq` package — fully interoperable at the Redis level
- API: `Queue`, `Worker`, `Job` — mirrors the TypeScript surface

Add to `apps/api/pyproject.toml`:

```toml
"bullmq==3.0.4",
```

Place after the existing `redis[asyncio]>=8.1.0` entry to keep dependency grouping logical.

---

## File-by-File Changes

### `apps/api/pyproject.toml`

Add `"bullmq==3.0.4"` to `[project].dependencies`. No other changes.

---

### `apps/api/app/workers/ingestion_worker.py` — full rewrite

Replace the hand-rolled `IngestionWorker` class with a factory function that creates `bullmq.Worker` instances for all ingestion and memory queues.

**Key design decisions:**

- Each stage gets its own `bullmq.Worker` instance. This gives independent concurrency control and clean separation of concerns.
- Stage-to-stage chaining uses `bullmq.Queue.add()` — same as any producer would. This keeps the job lifecycle entirely within BullMQ's Lua-managed state machine.
- Job data shape is preserved exactly: `documentVersionId`, `tenantId`, `knowledgeBaseId`, `userId` — TypeScript producers do not need to change.
- `memory.summarize` concurrency: `3` (I/O-bound, can overlap safely).
- `memory.prune` concurrency: `1` (database bulk-delete, should not overlap).
- Ingestion stages concurrency: `4` each (balanced for CPU/IO mix).
- Default job options: `attempts=3`, `backoff={type: "exponential", delay: 5000}`.

**`enqueue_memory_summarize`** remains a public method on the worker module (or a standalone function) so call sites in the application layer can enqueue without importing BullMQ directly. It is implemented as a thin wrapper around `bullmq.Queue("memory.summarize").add(...)`.

**Session lifecycle:** Each job handler opens a new `AsyncSession` via the session factory, uses it for the stage, and closes it. This matches the previous pattern and avoids session leaking across job boundaries.

**Error handling:** Unhandled exceptions bubble up to `bullmq.Worker`, which marks the job failed and triggers retry per the configured backoff. `_mark_failed` (set lifecycle to `FAILED`) is called only from the `on_failed` callback after all retry attempts are exhausted, identified by `job.attemptsMade >= job.opts.attempts`.

```python
# Sketch of the new structure (not final code — implementation task will produce final)

from bullmq import Worker, Queue, Job

def create_ingestion_workers(settings, session_factory, redis_url) -> list[Worker]:
    opts = {"attempts": 3, "backoff": {"type": "exponential", "delay": 5000}}

    async def handle_parse(job: Job, token: str) -> None:
        async with session_factory() as session:
            await parse_document(job.data["documentVersionId"], job.data["tenantId"], session, settings)
        q = Queue("ingestion.chunk", {"connection": redis_opts})
        await q.add("chunk", job.data, opts)

    # ... chunk, embed, index, validate follow the same pattern ...

    return [
        Worker("ingestion.parse",    handle_parse,    {"connection": redis_opts, "concurrency": 4}),
        Worker("ingestion.chunk",    handle_chunk,    {"connection": redis_opts, "concurrency": 4}),
        Worker("ingestion.embed",    handle_embed,    {"connection": redis_opts, "concurrency": 4}),
        Worker("ingestion.index",    handle_index,    {"connection": redis_opts, "concurrency": 4}),
        Worker("ingestion.validate", handle_validate, {"connection": redis_opts, "concurrency": 4}),
        Worker("memory.summarize",   handle_memory_summarize, {"connection": redis_opts, "concurrency": 3}),
        Worker("memory.prune",       handle_memory_prune,     {"connection": redis_opts, "concurrency": 1}),
    ]
```

---

### `apps/api/app/workers/tool_worker.py` — new file

New module that creates `bullmq.Worker` for `tool-execution`. Calls `McpRuntimeService.invoke_tool` directly. Requires a `session_factory` and `settings` to construct dependencies.

```python
# Sketch
from bullmq import Worker, Job
from app.application.mcp_runtime_service import McpRuntimeService

async def handle_tool_execution(job: Job, token: str) -> dict:
    data = job.data
    # build TenantContext, construct McpRuntimeService with session_factory
    # call service.invoke_tool(tenant=..., tool_id=data["tool_definition_id"], arguments=data["input_data"])
    ...

def create_tool_worker(settings, session_factory, redis_opts) -> Worker:
    return Worker("tool-execution", handle_tool_execution,
                  {"connection": redis_opts, "concurrency": 5})
```

---

### `apps/api/app/workers/calibration_worker.py` — new file

New module that creates `bullmq.Worker` for `calibration` and `synthetic-fixture`. Calls `CalibrationRunner.run` and `generate_synthetic_fixture` directly.

```python
# Sketch
from bullmq import Worker, Job
from app.application.calibration_service import CalibrationRunner, generate_synthetic_fixture

async def handle_calibration(job: Job, token: str) -> dict:
    data = job.data
    # construct CalibrationRunner with repos from session_factory
    # call runner.run(tenant_id=data["tenant_id"], retrieval_profile_id=data["profile_id"], fixture_id=data["fixture_id"])
    ...

async def handle_synthetic_fixture(job: Job, token: str) -> dict:
    data = job.data
    # call generate_synthetic_fixture(...)
    ...

def create_calibration_workers(settings, session_factory, redis_opts) -> list[Worker]:
    return [
        Worker("calibration",       handle_calibration,      {"connection": redis_opts, "concurrency": 2}),
        Worker("synthetic-fixture", handle_synthetic_fixture, {"connection": redis_opts, "concurrency": 2}),
    ]
```

---

### `apps/api/app/workers/main.py` — update entrypoint

Replace the current `IngestionWorker`-based main with one that:
1. Builds the shared `redis_opts` dict from `REDIS_URL`
2. Creates the session factory
3. Calls all worker factory functions to collect all 10 `Worker` instances
4. Registers `SIGINT`/`SIGTERM` handlers that call `worker.close()` on each instance
5. Awaits all workers via `asyncio.gather`

---

### `apps/api/app/application/confidence_service.py` — update enqueue methods

Replace the two manual-Redis enqueue methods:

| Method | Before | After |
|---|---|---|
| `enqueue_calibration` | `r.lpush("bull:calibration:wait", json.dumps(payload))` | `Queue("calibration", {connection}).add("calibrate", data, opts)` |
| `enqueue_synthetic` | `r.lpush("bull:synthetic-fixture:wait", json.dumps(payload))` | `Queue("synthetic-fixture", {connection}).add("generate-synthetic", data, opts)` |

The `redis_url` parameter stays on both methods — it is passed by the route handler and used to construct the `Queue` connection options.

---

### `apps/worker/` — delete

The entire `apps/worker/` directory is deleted. This includes:
- `src/index.ts`
- `src/application/use-cases/get-worker-summary.ts`
- `src/application/use-cases/get-worker-summary.test.ts`
- `src/infrastructure/config/env.ts`
- `src/infrastructure/queue/create-workers.ts`
- `src/infrastructure/queue/processors/tool-execution.processor.ts`
- `src/infrastructure/queue/processors/calibration.processor.ts`
- `src/infrastructure/queue/processors/synthetic-fixture.processor.ts`
- `package.json`, `tsconfig.json`, and any other config files

---

### `docker-compose.yml` — no change

The TypeScript worker was not defined as a compose service. The compose file requires no modification.

---

## Concurrency Summary

| Queue | Concurrency | Rationale |
|---|---|---|
| `ingestion.parse` | 4 | I/O + CPU mix (file read + Docling) |
| `ingestion.chunk` | 4 | CPU-light text splitting |
| `ingestion.embed` | 4 | I/O-bound (fastembed + Qdrant) |
| `ingestion.index` | 4 | I/O-bound (DB + Qdrant write) |
| `ingestion.validate` | 4 | I/O-bound (DB read/write) |
| `tool-execution` | 5 | Matches previous TS worker |
| `calibration` | 2 | Matches previous TS worker, CPU-bound |
| `synthetic-fixture` | 2 | Matches previous TS worker |
| `memory.summarize` | 3 | I/O-bound (LLM call) |
| `memory.prune` | 1 | Bulk DB delete — serial to avoid contention |

---

## Retry Policy

All workers use:

```python
default_job_options = {
    "attempts": 3,
    "backoff": {"type": "exponential", "delay": 5000},
}
```

Ingestion stage failures only set lifecycle to `FAILED` after the final attempt, using the BullMQ `on_failed` callback with the `job.attemptsMade` guard.

---

## Migration Safety

- Queue names are identical — any in-flight jobs at deployment time will be picked up by the new Python workers without data loss.
- Job data shapes are unchanged — all existing producers (frontend, API routes) continue to work.
- The `python-bullmq` library uses the same Lua scripts as the TypeScript `bullmq` package, so Redis key structure is fully compatible.
- The TypeScript worker can be stopped first, then the Python worker started, with no message loss (jobs remain in the `wait` list between deploys).
