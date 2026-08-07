# Spec: worker-consolidation

## Overview

This spec defines the requirements for consolidating the TypeScript BullMQ worker and the manual-Redis Python worker into a single Python worker process backed by `python-bullmq 3.0.4`.

---

## ADDED Requirements

### Requirement: bullmq-python-dependency

The `python-bullmq` package at version `3.0.4` SHALL be added to the core dependencies of `apps/api/pyproject.toml` using the pinned specifier `bullmq==3.0.4`.

#### Scenario: bullmq listed in pyproject dependencies

**Given** the file `apps/api/pyproject.toml` exists  
**When** the `[project]` `dependencies` array is inspected  
**Then** it SHALL contain an entry matching `bullmq==3.0.4`

#### Scenario: bullmq installs without conflict

**Given** the Python environment has all existing `apps/api` dependencies installed  
**When** `uv sync` or `pip install bullmq==3.0.4` is executed  
**Then** it SHALL succeed with no dependency conflicts  
**And** `import bullmq` SHALL resolve without error

---

### Requirement: proper-bullmq-worker-ingestion

The ingestion worker (`apps/api/app/workers/ingestion_worker.py`) MUST be rewritten to use `bullmq.Worker` for all queue consumption, replacing all manual `RPOPLPUSH`, `HGET`, `HSET`, and `LPUSH` Redis calls.

#### Scenario: ingestion worker uses bullmq.Worker class

**Given** the file `apps/api/app/workers/ingestion_worker.py` exists  
**When** its imports and class definition are inspected  
**Then** it SHALL import `Worker` from `bullmq`  
**And** it SHALL NOT contain any direct calls to `rpoplpush`, `hget`, `hset`, or `lpush`

#### Scenario: ingestion worker registers all pipeline queues

**Given** the consolidated worker is initialised  
**When** the BullMQ worker instances are created  
**Then** one `bullmq.Worker` instance SHALL be registered for each of:  
`ingestion.parse`, `ingestion.chunk`, `ingestion.embed`, `ingestion.index`, `ingestion.validate`

#### Scenario: parse stage executes on job receipt

**Given** a job is placed on the `ingestion.parse` queue with fields `documentVersionId`, `tenantId`, `knowledgeBaseId`, `userId`  
**When** the worker picks up the job  
**Then** it SHALL call `parse_document(document_version_id, tenant_id, session, settings)`  
**And** on success it SHALL enqueue a new job onto `ingestion.chunk` via `bullmq.Queue`  
**And** the BullMQ job SHALL be marked completed

#### Scenario: stage failure triggers BullMQ retry

**Given** a job is placed on any ingestion stage queue  
**When** the stage handler raises an unhandled exception  
**Then** the `bullmq.Worker` SHALL mark the job as failed  
**And** BullMQ SHALL apply the configured retry/backoff policy  
**And** the document version lifecycle state SHALL be set to `FAILED` only after all retries are exhausted

#### Scenario: enqueue_next uses bullmq.Queue

**Given** an ingestion stage completes successfully  
**When** the worker enqueues the job to the next stage  
**Then** it SHALL use `bullmq.Queue.add()` to enqueue  
**And** it SHALL NOT use raw `lpush` or `hset` to push to the next queue

---

### Requirement: proper-bullmq-worker-memory

The memory jobs (`memory.summarize`, `memory.prune`) MUST be consumed via `bullmq.Worker` instances and enqueued via `bullmq.Queue`.

#### Scenario: memory.summarize worker registered

**Given** the consolidated worker is initialised  
**When** the BullMQ worker instances are created  
**Then** one `bullmq.Worker` instance SHALL be registered for `memory.summarize`

#### Scenario: memory.prune worker registered

**Given** the consolidated worker is initialised  
**When** the BullMQ worker instances are created  
**Then** one `bullmq.Worker` instance SHALL be registered for `memory.prune`

#### Scenario: enqueue_memory_summarize uses bullmq.Queue

**Given** the application layer calls `enqueue_memory_summarize`  
**When** the method executes  
**Then** it SHALL use `bullmq.Queue.add()` on the `memory.summarize` queue  
**And** it SHALL NOT call `lpush` or `hset` directly on the Redis connection

---

### Requirement: tool-execution-python-worker

A Python `bullmq.Worker` MUST be registered for the `tool-execution` queue. It SHALL call the Python application layer directly, with no HTTP call to the internal API.

#### Scenario: tool-execution worker registered

**Given** the consolidated worker is initialised  
**When** the BullMQ worker instances are created  
**Then** one `bullmq.Worker` instance SHALL be registered for `tool-execution`

#### Scenario: tool-execution job dispatches to application layer

**Given** a job is placed on the `tool-execution` queue with fields `tenant_id`, `tool_slug`, `tool_definition_id`, `input_data`, `trace_id`, `query_id`  
**When** the worker picks up the job  
**Then** it SHALL call the Python tool-execution application logic directly (e.g. via `McpRuntimeService.invoke_tool` or equivalent)  
**And** it SHALL NOT make any HTTP request to `POST /internal/tools/execute`

#### Scenario: tool-execution concurrency matches previous TypeScript worker

**Given** the `tool-execution` BullMQ worker is created  
**When** its concurrency setting is inspected  
**Then** it SHALL be set to `5`, matching the previous TypeScript worker

---

### Requirement: calibration-python-worker

A Python `bullmq.Worker` MUST be registered for the `calibration` queue. It SHALL call the Python application layer directly, with no HTTP call to the internal API.

#### Scenario: calibration worker registered

**Given** the consolidated worker is initialised  
**When** the BullMQ worker instances are created  
**Then** one `bullmq.Worker` instance SHALL be registered for `calibration`

#### Scenario: calibration job dispatches to application layer

**Given** a job is placed on the `calibration` queue with fields `tenant_id`, `profile_id`, `fixture_id`, `trace_id`  
**When** the worker picks up the job  
**Then** it SHALL call `CalibrationRunner.run(tenant_id, retrieval_profile_id, fixture_id)` directly  
**And** it SHALL NOT make any HTTP request to `POST /internal/confidence/calibrate`

#### Scenario: calibration concurrency matches previous TypeScript worker

**Given** the `calibration` BullMQ worker is created  
**When** its concurrency setting is inspected  
**Then** it SHALL be set to `2`, matching the previous TypeScript worker

---

### Requirement: synthetic-fixture-python-worker

A Python `bullmq.Worker` MUST be registered for the `synthetic-fixture` queue. It SHALL call the Python application layer directly, with no HTTP call to the internal API.

#### Scenario: synthetic-fixture worker registered

**Given** the consolidated worker is initialised  
**When** the BullMQ worker instances are created  
**Then** one `bullmq.Worker` instance SHALL be registered for `synthetic-fixture`

#### Scenario: synthetic-fixture job dispatches to application layer

**Given** a job is placed on the `synthetic-fixture` queue with fields `tenant_id`, `profile_id`, `kb_id`, `count`, `trace_id`  
**When** the worker picks up the job  
**Then** it SHALL call `generate_synthetic_fixture(...)` directly  
**And** it SHALL NOT make any HTTP request to `POST /internal/confidence/fixtures/generate-synthetic`

#### Scenario: synthetic-fixture concurrency matches previous TypeScript worker

**Given** the `synthetic-fixture` BullMQ worker is created  
**When** its concurrency setting is inspected  
**Then** it SHALL be set to `2`, matching the previous TypeScript worker

---

### Requirement: bullmq-queue-enqueue-replaces-manual-redis

All call sites that currently enqueue jobs via raw `lpush`/`hset` (in `confidence_service.py` and `ingestion_worker.py`) MUST be replaced with `bullmq.Queue.add()`.

#### Scenario: confidence_service enqueue_calibration uses Queue

**Given** `ConfidenceService.enqueue_calibration` is called  
**When** the method body is executed  
**Then** it SHALL use `bullmq.Queue("calibration", ...).add(...)` to push the job  
**And** it SHALL NOT call `r.lpush("bull:calibration:wait", ...)`

#### Scenario: confidence_service enqueue_synthetic uses Queue

**Given** `ConfidenceService.enqueue_synthetic` is called  
**When** the method body is executed  
**Then** it SHALL use `bullmq.Queue("synthetic-fixture", ...).add(...)` to push the job  
**And** it SHALL NOT call `r.lpush("bull:synthetic-fixture:wait", ...)`

---

### Requirement: typescript-worker-removed

The `apps/worker/` directory MUST be deleted in its entirety. No TypeScript worker process SHALL remain in the repository.

#### Scenario: apps/worker directory does not exist after change

**Given** the worker-consolidation change is applied  
**When** the repository file tree is inspected  
**Then** `apps/worker/` SHALL NOT exist

#### Scenario: no internal API calls remain in worker code

**Given** the worker-consolidation change is applied  
**When** all files under `apps/api/app/workers/` are inspected  
**Then** there SHALL be no references to `INTERNAL_API_URL`, `X-Internal-Secret`, or `callInternalApi`

---

### Requirement: queue-names-preserved

All BullMQ queue names MUST remain identical to those used before the consolidation. No producer code SHALL need to change.

#### Scenario: all 10 queue names match previous names

**Given** the consolidated worker is initialised  
**When** the registered worker queue names are enumerated  
**Then** they SHALL exactly match:  
`ingestion.parse`, `ingestion.chunk`, `ingestion.embed`, `ingestion.index`, `ingestion.validate`,  
`tool-execution`, `calibration`, `synthetic-fixture`, `memory.summarize`, `memory.prune`

---

### Requirement: worker-entrypoint-starts-all-workers

The worker entrypoint (`apps/api/app/workers/main.py`) MUST start all consolidated BullMQ workers and handle `SIGINT`/`SIGTERM` for graceful shutdown.

#### Scenario: main.py starts consolidated worker

**Given** `python -m app.workers.main` is executed  
**When** the process starts  
**Then** all 10 `bullmq.Worker` instances SHALL be active  
**And** the process SHALL log that all queues are listening

#### Scenario: SIGTERM causes graceful shutdown

**Given** the worker process is running  
**When** `SIGTERM` is sent to the process  
**Then** each `bullmq.Worker` SHALL call its `close()` method  
**And** the process SHALL exit cleanly with code 0

---

### Requirement: retry-and-backoff-configured

All `bullmq.Worker` instances MUST be configured with a default retry and backoff policy so transient failures do not permanently lose jobs.

#### Scenario: workers have retry attempts configured

**Given** any `bullmq.Worker` instance is created  
**When** its job options are inspected  
**Then** it SHALL have at least `attempts: 3` configured  
**And** it SHALL use exponential backoff between retries
