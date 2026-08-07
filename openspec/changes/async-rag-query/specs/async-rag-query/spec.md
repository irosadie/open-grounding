# Spec: async-rag-query

## Overview

This spec defines the requirements for adding an asynchronous execution path for RAG queries. The change introduces a BullMQ-backed async endpoint, a job status polling endpoint, a Python worker, a new `rag_query_jobs` database table, and optional per-request webhook delivery. The synchronous `POST /rag/query` endpoint is unaffected.

**Dependency:** `worker-consolidation` must be complete — `python-bullmq 3.0.4` must be installed and the Python worker process must be running.

---

## ADDED Requirements

### Requirement: rag-query-jobs-table

A `rag_query_jobs` table SHALL exist in the database with columns for job identity, tenant scoping, status, request payload, result, error, webhook URL, and timestamps. An Alembic migration SHALL create this table.

#### Scenario: migration creates rag_query_jobs table

**Given** the Alembic migration for `async-rag-query` is applied  
**When** the database schema is inspected  
**Then** a table named `rag_query_jobs` SHALL exist  
**And** it SHALL have columns: `id` (UUID PK), `tenant_id` (UUID FK → tenants), `user_id` (UUID FK → users), `status` (VARCHAR), `request` (JSONB), `result` (JSONB nullable), `error` (TEXT nullable), `webhook_url` (VARCHAR nullable), `created_at` (TIMESTAMPTZ), `completed_at` (TIMESTAMPTZ nullable)

#### Scenario: migration is reversible

**Given** the Alembic migration for `async-rag-query` has been applied  
**When** `alembic downgrade -1` is executed  
**Then** the `rag_query_jobs` table SHALL be dropped  
**And** the database SHALL return to its pre-migration state

#### Scenario: tenant_id index exists

**Given** the migration has been applied  
**When** the indexes on `rag_query_jobs` are inspected  
**Then** an index SHALL exist on the `tenant_id` column

---

### Requirement: rag-query-job-domain-entity

A `RagQueryJob` domain entity and `RagQueryJobStatus` enum SHALL be defined in the domain layer. They SHALL not import SQLAlchemy or any infrastructure module.

#### Scenario: RagQueryJobStatus has required values

**Given** the `RagQueryJobStatus` enum is inspected  
**When** its members are enumerated  
**Then** it SHALL contain exactly: `pending`, `running`, `completed`, `failed`

#### Scenario: RagQueryJob is a frozen dataclass

**Given** the `RagQueryJob` class is inspected  
**When** an instance is created  
**Then** it SHALL be immutable (frozen dataclass or equivalent)  
**And** it SHALL carry fields: `id`, `tenant_id`, `user_id`, `status`, `request`, `result`, `error`, `webhook_url`, `created_at`, `completed_at`

---

### Requirement: rag-query-job-repository

A `SqlAlchemyRagQueryJobRepository` SHALL be implemented in `apps/api/app/infrastructure/rag_catalog.py`. It SHALL map ORM records to domain entities and never expose raw ORM records to callers.

#### Scenario: create inserts a pending job row

**Given** a `RagQueryJob` with `status=pending` is provided  
**When** `SqlAlchemyRagQueryJobRepository.create(job)` is called  
**Then** a row SHALL be inserted into `rag_query_jobs`  
**And** the row's `status` SHALL be `pending`

#### Scenario: get_by_id_and_tenant returns None for wrong tenant

**Given** a job exists with `tenant_id = A`  
**When** `get_by_id_and_tenant(job_id, tenant_id=B)` is called  
**Then** it SHALL return `None`

#### Scenario: get_by_id_and_tenant returns job for correct tenant

**Given** a job exists with `tenant_id = A`  
**When** `get_by_id_and_tenant(job_id, tenant_id=A)` is called  
**Then** it SHALL return a `RagQueryJob` domain entity with the correct field values

#### Scenario: update_completed sets status and result

**Given** a job exists with `status=running`  
**When** `update_completed(job_id, result={...})` is called  
**Then** the row's `status` SHALL be `completed`  
**And** `result` SHALL be the provided dict  
**And** `completed_at` SHALL be set to a non-null UTC timestamp

#### Scenario: update_failed sets status and error

**Given** a job exists with `status=running`  
**When** `update_failed(job_id, error="message")` is called  
**Then** the row's `status` SHALL be `failed`  
**And** `error` SHALL be the provided string  
**And** `completed_at` SHALL be set to a non-null UTC timestamp

---

### Requirement: async-query-endpoint

A `POST /rag/query/async` endpoint SHALL be added. It SHALL validate the request, create a `rag_query_jobs` row, enqueue a job on the `rag.query` BullMQ queue, and return HTTP 202 with `{ jobId, conversationId }`.

#### Scenario: valid request returns 202 with jobId

**Given** an authenticated tenant user  
**When** `POST /rag/query/async` is called with a valid request body  
**Then** the response status SHALL be `202`  
**And** the response body SHALL contain `jobId` (a UUID string) and `conversationId` (a UUID string)

#### Scenario: job row is created with pending status

**Given** an authenticated tenant user  
**When** `POST /rag/query/async` is called with a valid request body  
**Then** a row SHALL exist in `rag_query_jobs` with `status=pending` and the returned `jobId`

#### Scenario: job is enqueued on rag.query queue

**Given** an authenticated tenant user  
**When** `POST /rag/query/async` is called with a valid request body  
**Then** a BullMQ job SHALL be added to the `rag.query` queue  
**And** the BullMQ job ID SHALL equal the returned `jobId`

#### Scenario: unauthenticated request is rejected

**Given** no valid auth token is provided  
**When** `POST /rag/query/async` is called  
**Then** the response status SHALL be `401`

#### Scenario: webhook_url with http:// is rejected

**Given** an authenticated tenant user  
**When** `POST /rag/query/async` is called with `webhook_url` set to an `http://` URL  
**Then** the response status SHALL be `422`  
**And** the response SHALL contain a validation error referencing `webhook_url`

#### Scenario: missing message field is rejected

**Given** an authenticated tenant user  
**When** `POST /rag/query/async` is called without a `message` field  
**Then** the response status SHALL be `422`

#### Scenario: empty knowledge_base_ids is rejected

**Given** an authenticated tenant user  
**When** `POST /rag/query/async` is called with `knowledge_base_ids = []`  
**Then** the response status SHALL be `422`

---

### Requirement: job-status-endpoint

A `GET /rag/query/jobs/{job_id}` endpoint SHALL be added. It SHALL return the current job status and result for jobs belonging to the authenticated tenant. It SHALL return `404` for job IDs that do not exist or belong to a different tenant.

#### Scenario: pending job returns status pending

**Given** a job with `status=pending` exists for the authenticated tenant  
**When** `GET /rag/query/jobs/{job_id}` is called  
**Then** the response status SHALL be `200`  
**And** `status` SHALL be `pending`  
**And** `result` SHALL be `null`  
**And** `completedAt` SHALL be `null`

#### Scenario: completed job returns status and result

**Given** a job with `status=completed` and a non-null `result` exists for the authenticated tenant  
**When** `GET /rag/query/jobs/{job_id}` is called  
**Then** the response status SHALL be `200`  
**And** `status` SHALL be `completed`  
**And** `result` SHALL be the stored result object  
**And** `completedAt` SHALL be a non-null ISO 8601 string

#### Scenario: failed job returns status and error

**Given** a job with `status=failed` and a non-null `error` exists for the authenticated tenant  
**When** `GET /rag/query/jobs/{job_id}` is called  
**Then** the response status SHALL be `200`  
**And** `status` SHALL be `failed`  
**And** `error` SHALL be a non-null string

#### Scenario: cross-tenant job returns 404

**Given** a job exists for tenant A  
**When** `GET /rag/query/jobs/{job_id}` is called by an authenticated user of tenant B  
**Then** the response status SHALL be `404`

#### Scenario: non-existent job returns 404

**Given** a job ID that does not exist in `rag_query_jobs`  
**When** `GET /rag/query/jobs/{job_id}` is called  
**Then** the response status SHALL be `404`

#### Scenario: unauthenticated request is rejected

**Given** no valid auth token is provided  
**When** `GET /rag/query/jobs/{job_id}` is called  
**Then** the response status SHALL be `401`

---

### Requirement: rag-query-bullmq-worker

A `bullmq.Worker` for the `rag.query` queue SHALL be implemented in `apps/api/app/workers/query_worker.py`. It SHALL call `RagQueryService.query()` directly and update `rag_query_jobs` on completion or failure.

#### Scenario: worker is registered for rag.query queue

**Given** the worker entrypoint is initialised  
**When** the BullMQ worker instances are enumerated  
**Then** one `bullmq.Worker` instance SHALL be registered for the `rag.query` queue

#### Scenario: worker sets status to running on pickup

**Given** a job exists in `rag_query_jobs` with `status=pending`  
**When** the `rag.query` worker picks up the job  
**Then** `rag_query_jobs.status` SHALL be updated to `running` before `RagQueryService.query()` is called

#### Scenario: successful job updates status to completed

**Given** `RagQueryService.query()` returns a result without raising  
**When** the worker finishes processing the job  
**Then** `rag_query_jobs.status` SHALL be `completed`  
**And** `rag_query_jobs.result` SHALL contain the query response  
**And** `rag_query_jobs.completed_at` SHALL be set

#### Scenario: failed job updates status to failed

**Given** `RagQueryService.query()` raises an exception  
**When** the worker's exception handler runs  
**Then** `rag_query_jobs.status` SHALL be `failed`  
**And** `rag_query_jobs.error` SHALL contain the error message string  
**And** `rag_query_jobs.completed_at` SHALL be set

#### Scenario: worker concurrency is 10

**Given** the `rag.query` BullMQ worker is created  
**When** its concurrency setting is inspected  
**Then** it SHALL be set to `10`

#### Scenario: worker retry is configured to 2 attempts with exponential backoff

**Given** the `rag.query` BullMQ worker job options are inspected  
**When** the retry policy is read  
**Then** `attempts` SHALL be `2`  
**And** `backoff.type` SHALL be `exponential`  
**And** `backoff.delay` SHALL be `3000`

---

### Requirement: worker-entrypoint-includes-query-worker

The worker entrypoint (`apps/api/app/workers/main.py`) MUST include the `rag.query` worker in its startup list.

#### Scenario: main.py starts rag.query worker

**Given** `python -m app.workers.main` is executed  
**When** the process starts  
**Then** a `bullmq.Worker` for `rag.query` SHALL be active alongside all pre-existing workers

---

### Requirement: webhook-delivery

If `webhook_url` is provided in the async query request, the worker SHALL POST the job result or error to that URL after the job completes or fails. Webhook delivery SHALL be fire-and-forget and SHALL NOT affect job status.

#### Scenario: webhook is called on completion

**Given** the async query request included a valid `webhook_url`  
**When** the worker completes the job successfully  
**Then** an HTTP POST SHALL be sent to `webhook_url`  
**And** the request body SHALL be JSON with fields: `jobId`, `status="completed"`, `result`, `error=null`

#### Scenario: webhook is called on failure

**Given** the async query request included a valid `webhook_url`  
**When** the worker marks the job as failed  
**Then** an HTTP POST SHALL be sent to `webhook_url`  
**And** the request body SHALL be JSON with fields: `jobId`, `status="failed"`, `result=null`, `error`

#### Scenario: webhook timeout does not affect job status

**Given** the webhook POST times out after 10 seconds  
**When** the timeout is reached  
**Then** the job status in `rag_query_jobs` SHALL remain `completed` or `failed` (unchanged)  
**And** no exception SHALL propagate from the webhook call

#### Scenario: missing webhook_url skips delivery

**Given** the async query request did not include `webhook_url`  
**When** the worker finishes processing  
**Then** no outbound HTTP request SHALL be made for webhook delivery

#### Scenario: webhook uses https only

**Given** a request with `webhook_url = "http://example.com/hook"`  
**When** `POST /rag/query/async` validates the request  
**Then** the request SHALL be rejected with status `422` before any job is created
