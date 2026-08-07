# Tasks: async-rag-query

## 1. Migration

- [x] 1.1 Create Alembic migration in `apps/api/alembic/versions/` — add `rag_query_jobs` table with columns: `id` (UUID PK), `tenant_id` (UUID FK → tenants, NOT NULL), `user_id` (UUID FK → users, NOT NULL), `status` (VARCHAR(20), NOT NULL, default `'pending'`), `request` (JSONB, NOT NULL), `result` (JSONB, nullable), `error` (TEXT, nullable), `webhook_url` (VARCHAR(2048), nullable), `created_at` (TIMESTAMPTZ, NOT NULL, default `now()`), `completed_at` (TIMESTAMPTZ, nullable)
- [x] 1.2 Add indexes in the migration: `ix_rag_query_jobs_tenant_id` on `tenant_id`, `ix_rag_query_jobs_status` on `status`
- [x] 1.3 Add `downgrade()` to the migration that drops `rag_query_jobs`
- [ ] 1.4 Run `alembic upgrade head` and confirm the table is created; run `alembic downgrade -1` and confirm it is dropped

## 2. Domain Entity

- [x] 2.1 Create `apps/api/app/domain/rag/query_job.py` — define `RagQueryJobStatus(StrEnum)` with values `pending`, `running`, `completed`, `failed`
- [x] 2.2 Define `RagQueryJob` as a frozen dataclass in `query_job.py` with fields: `id: str`, `tenant_id: str`, `user_id: str`, `status: RagQueryJobStatus`, `request: dict[str, Any]`, `result: dict[str, Any] | None`, `error: str | None`, `webhook_url: str | None`, `created_at: datetime`, `completed_at: datetime | None`

## 3. Infrastructure

- [x] 3.1 Add `RagQueryJobRecord` ORM model to `apps/api/app/infrastructure/rag_catalog.py` — map all columns from the migration; import `RagQueryJob` and `RagQueryJobStatus` from `app.domain.rag.query_job`
- [x] 3.2 Implement `SqlAlchemyRagQueryJobRepository` in `rag_catalog.py` with method `create(self, job: RagQueryJob) -> None` — inserts a new row
- [x] 3.3 Implement `get_by_id_and_tenant(self, job_id: str, tenant_id: str) -> RagQueryJob | None` — SELECT WHERE id AND tenant_id; return `None` if not found
- [x] 3.4 Implement `update_running(self, job_id: str) -> None` — UPDATE status=`running`
- [x] 3.5 Implement `update_completed(self, job_id: str, result: dict) -> None` — UPDATE status=`completed`, result=result, completed_at=utc_now()
- [x] 3.6 Implement `update_failed(self, job_id: str, error: str) -> None` — UPDATE status=`failed`, error=error, completed_at=utc_now()

## 4. HTTP Schemas

- [x] 4.1 Add `AsyncRagQueryRequest(BaseModel)` to `apps/api/app/interfaces/http/schemas.py`
- [x] 4.2 Add `AsyncRagQueryResponse(BaseModel)` to `schemas.py` — fields: `jobId: str`, `conversationId: str`
- [x] 4.3 Add `RagQueryJobResponse(BaseModel)` to `schemas.py` — fields: `jobId: str`, `status: str`, `result: dict[str, Any] | None`, `error: str | None`, `createdAt: str`, `completedAt: str | None`

## 5. HTTP Routes

- [x] 5.1 Add `POST /rag/query/async` route to `apps/api/app/interfaces/http/routes.py`
- [x] 5.2 Add `GET /rag/query/jobs/{job_id}` route

## 6. Worker

- [x] 6.1 Create `apps/api/app/workers/query_worker.py` — implement `handle_rag_query(job: Job, token: str) -> None`
- [x] 6.2 Implement `_fire_webhook(url: str | None, job_id: str, status: str, result, error: str | None) -> None`
- [x] 6.3 Implement `create_query_worker(settings, session_factory, redis_opts) -> Worker` factory
- [x] 6.4 Import `create_query_worker` in `apps/api/app/workers/main.py` and add it to the worker list

## 7. Tests

- [x] 7.1 Add `apps/api/tests/workers/test_async_rag_query.py` — success path test
- [x] 7.2 Add test for failure path
- [x] 7.3 Add test for `_fire_webhook` — assert POST called with correct URL and JSON payload
- [x] 7.4 Add test for `_fire_webhook` when `url=None`
- [x] 7.5 Add test: POST `/rag/query/async` with valid payload returns 202 with `jobId` / `conversationId`
- [x] 7.6 Add test: POST `/rag/query/async` with `webhook_url="http://..."` returns 422
- [x] 7.7 Add test: GET `/rag/query/jobs/{job_id}` returns 200 with correct fields
- [x] 7.8 Add test: GET `/rag/query/jobs/{job_id}` returns 404 for cross-tenant job
- [x] 7.9 Run pytest and confirm all tests pass
