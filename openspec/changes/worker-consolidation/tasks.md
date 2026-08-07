# Tasks: worker-consolidation

## 1. Dependency

- [x] 1.0 Relax `redis[asyncio]` constraint from `>=8.1.0` to `>=7.4.1` in `apps/api/pyproject.toml` to allow python-bullmq compatibility
- [x] 1.1 Add `"bullmq==3.0.4"` to `[project].dependencies` in `apps/api/pyproject.toml` after the `redis[asyncio]` entry
- [x] 1.2 Run `uv sync` in `apps/api/` and verify no dependency conflicts; confirm `import bullmq` resolves

## 2. Enqueue — confidence_service.py

- [x] 2.1 Replace `enqueue_calibration` manual `lpush` in `apps/api/app/application/confidence_service.py` with `bullmq.Queue("calibration", {"connection": redis_opts}).add("calibrate", data, job_opts)`
- [x] 2.2 Replace `enqueue_synthetic` manual `lpush` in `apps/api/app/application/confidence_service.py` with `bullmq.Queue("synthetic-fixture", {"connection": redis_opts}).add("generate-synthetic", data, job_opts)`
- [x] 2.3 Remove the inline `aioredis.from_url` / `r.lpush` / `r.aclose` blocks from both enqueue methods; keep the `redis_url` parameter to build `Queue` connection options

## 3. Ingestion worker rewrite

- [x] 3.1 Rewrite `apps/api/app/workers/ingestion_worker.py` — replace `IngestionWorker` class with a `create_ingestion_workers(settings, session_factory, redis_opts)` factory that returns a list of `bullmq.Worker` instances for `ingestion.parse`, `ingestion.chunk`, `ingestion.embed`, `ingestion.index`, `ingestion.validate`
- [x] 3.2 Implement each stage handler (`handle_parse`, `handle_chunk`, `handle_embed`, `handle_index`, `handle_validate`) — open an `AsyncSession`, call the existing stage function, enqueue the next stage via `bullmq.Queue.add()`, close session
- [x] 3.3 Add `memory.summarize` and `memory.prune` workers to the factory with concurrency `3` and `1` respectively; implement their handlers calling `summarize_conversation` and `prune_expired_memory` directly
- [x] 3.4 Replace `enqueue_memory_summarize` standalone function — rewrite as a module-level async function that uses `bullmq.Queue("memory.summarize", ...).add(...)` instead of raw `lpush`/`hset`
- [x] 3.5 Configure all workers with `default_job_options = {"attempts": 3, "backoff": {"type": "exponential", "delay": 5000}}`
- [x] 3.6 Add `on_failed` callback to ingestion stage workers — call `_mark_failed` (set lifecycle to `FAILED`) only when `job.attemptsMade >= job.opts.get("attempts", 3)`

## 4. Tool-execution worker

- [x] 4.1 Create `apps/api/app/workers/tool_worker.py` — implement `handle_tool_execution(job, token)` that extracts `tenant_id`, `tool_definition_id`, `input_data`, `trace_id`, `query_id` from `job.data` and calls `McpRuntimeService.invoke_tool` directly
- [x] 4.2 Add `create_tool_worker(settings, session_factory, redis_opts) -> Worker` factory in `tool_worker.py` with concurrency `5`

## 5. Calibration and synthetic-fixture workers

- [x] 5.1 Create `apps/api/app/workers/calibration_worker.py` — implement `handle_calibration(job, token)` that extracts `tenant_id`, `profile_id`, `fixture_id` from `job.data` and calls `CalibrationRunner.run(...)` directly with repos constructed from `session_factory`
- [x] 5.2 Implement `handle_synthetic_fixture(job, token)` in `calibration_worker.py` that extracts `tenant_id`, `profile_id`, `kb_id`, `count`, `trace_id` and calls `generate_synthetic_fixture(...)` directly
- [x] 5.3 Add `create_calibration_workers(settings, session_factory, redis_opts) -> list[Worker]` factory in `calibration_worker.py` — returns workers for `calibration` (concurrency `2`) and `synthetic-fixture` (concurrency `2`)

## 6. Worker entrypoint

- [x] 6.1 Rewrite `apps/api/app/workers/main.py` — build shared `redis_opts` from `REDIS_URL`, create session factory, call all three worker factories, collect all 10 `Worker` instances into one list
- [x] 6.2 Register `SIGINT`/`SIGTERM` handlers in `main.py` that call `await worker.close()` on each instance and exit cleanly
- [x] 6.3 Log startup summary listing all 10 active queue names

## 7. TypeScript worker removal

- [x] 7.1 Delete `apps/worker/src/infrastructure/queue/processors/tool-execution.processor.ts`
- [x] 7.2 Delete `apps/worker/src/infrastructure/queue/processors/calibration.processor.ts`
- [x] 7.3 Delete `apps/worker/src/infrastructure/queue/processors/synthetic-fixture.processor.ts`
- [x] 7.4 Delete `apps/worker/src/infrastructure/queue/create-workers.ts`
- [x] 7.5 Delete `apps/worker/src/infrastructure/config/env.ts`
- [x] 7.6 Delete `apps/worker/src/application/use-cases/get-worker-summary.ts` and `get-worker-summary.test.ts`
- [x] 7.7 Delete `apps/worker/src/index.ts`
- [x] 7.8 Delete remaining `apps/worker/` root files (`package.json`, `tsconfig.json`, etc.) and confirm the directory is gone

## 8. Tests

- [x] 8.1 Add a unit test in `apps/api/tests/workers/test_ingestion_worker.py` — mock `bullmq.Worker` and `bullmq.Queue`, verify that all 7 ingestion/memory workers are created with correct queue names and concurrency
- [x] 8.2 Add a unit test verifying `handle_parse` calls `parse_document` and enqueues to `ingestion.chunk` on success; verify `handle_parse` raises and does NOT enqueue on stage failure
- [x] 8.3 Add a unit test in `apps/api/tests/workers/test_tool_worker.py` — mock `McpRuntimeService.invoke_tool`, verify `handle_tool_execution` passes correct arguments
- [x] 8.4 Add a unit test in `apps/api/tests/workers/test_calibration_worker.py` — mock `CalibrationRunner.run` and `generate_synthetic_fixture`, verify both handlers pass correct arguments
- [x] 8.5 Add a unit test in `apps/api/tests/application/test_confidence_service_enqueue.py` — mock `bullmq.Queue.add`, verify `enqueue_calibration` and `enqueue_synthetic` call `Queue.add` with correct queue name, job name, and data; verify no `lpush` calls remain
- [x] 8.6 Run `pytest apps/api/tests/workers/ apps/api/tests/application/test_confidence_service_enqueue.py` and confirm all new tests pass
