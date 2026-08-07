# Tasks: async-rag-query

## 1. Migration

- [ ] 1.1 Create Alembic migration in `apps/api/alembic/versions/` — add `rag_query_jobs` table with columns: `id` (UUID PK), `tenant_id` (UUID FK → tenants, NOT NULL), `user_id` (UUID FK → users, NOT NULL), `status` (VARCHAR(20), NOT NULL, default `'pending'`), `request` (JSONB, NOT NULL), `result` (JSONB, nullable), `error` (TEXT, nullable), `webhook_url` (VARCHAR(2048), nullable), `created_at` (TIMESTAMPTZ, NOT NULL, default `now()`), `completed_at` (TIMESTAMPTZ, nullable)
- [ ] 1.2 Add indexes in the migration: `ix_rag_query_jobs_tenant_id` on `tenant_id`, `ix_rag_query_jobs_status` on `status`
- [ ] 1.3 Add `downgrade()` to the migration that drops `rag_query_jobs`
- [ ] 1.4 Run `alembic upgrade head` and confirm the table is created; run `alembic downgrade -1` and confirm it is dropped

## 2. Domain Entity

- [ ] 2.1 Create `apps/api/app/domain/rag/query_job.py` — define `RagQueryJobStatus(StrEnum)` with values `pending`, `running`, `completed`, `failed`
- [ ] 2.2 Define `RagQueryJob` as a frozen dataclass in `query_job.py` with fields: `id: str`, `tenant_id: str`, `user_id: str`, `status: RagQueryJobStatus`, `request: dict[str, Any]`, `result: dict[str, Any] | None`, `error: str | None`, `webhook_url: str | None`, `created_at: datetime`, `completed_at: datetime | None`

## 3. Infrastructure

- [ ] 3.1 Add `RagQueryJobRecord` ORM model to `apps/api/app/infrastructure/rag_catalog.py` — map all columns from the migration; import `RagQueryJob` and `RagQueryJobStatus` from `app.domain.rag.query_job`
- [ ] 3.2 Implement `SqlAlchemyRagQueryJobRepository` in `rag_catalog.py` with method `create(self, job: RagQueryJob) -> None` — inserts a new row
- [ ] 3.3 Implement `get_by_id_and_tenant(self, job_id: str, tenant_id: str) -> RagQueryJob | None` — SELECT WHERE id AND tenant_id; return `None` if not found
- [ ] 3.4 Implement `update_running(self, job_id: str) -> None` — UPDATE status=`running`
- [ ] 3.5 Implement `update_completed(self, job_id: str, result: dict) -> None` — UPDATE status=`completed`, result=result, completed_at=utc_now()
- [ ] 3.6 Implement `update_failed(self, job_id: str, error: str) -> None` — UPDATE status=`failed`, error=error, completed_at=utc_now()

## 4. HTTP Schemas

- [ ] 4.1 Add `AsyncRagQueryRequest(BaseModel)` to `apps/api/app/interfaces/http/schemas.py` — fields: `message: str` (min_length=1, max_length=8192), `knowledge_base_ids: list[str]` (min_length=1, max_length=20), `conversation_id: str | None = None`, `webhook_url: str | None = Field(default=None, max_length=2048)`, `mode: Literal["grounded"] = "grounded"`, `decomposition: dict[str, Any] | None = None`, `planner: dict[str, Any] | None = None`, `memory: dict[str, Any] | None = None`; add `field_validator` on `webhook_url` that raises `ValueError` if value does not start with `https://`
- [ ] 4.2 Add `AsyncRagQueryResponse(BaseModel)` to `schemas.py` — fields: `jobId: str`, `conversationId: str`
- [ ] 4.3 Add `RagQueryJobResponse(BaseModel)` to `schemas.py` — fields: `jobId: str`, `status: str`, `result: dict[str, Any] | None`, `error: str | None`, `createdAt: str`, `completedAt: str | None`

## 5. HTTP Routes

- [ ] 5.1 Add `POST /rag/query/async` route to `apps/api/app/interfaces/http/routes.py` — inject authenticated tenant context and DB session; generate `job_id = str(uuid4())` and `conversation_id` (use request value or generate new uuid4); call `SqlAlchemyRagQueryJobRepository.create()`; call `Queue("rag.query", {"connection": redis_opts}).add(job_id, job_data, {"jobId": job_id, "attempts": 2, "backoff": {"type": "exponential", "delay": 3000}})`; return `202 AsyncRagQueryResponse`
- [ ] 5.2 Add `GET /rag/query/jobs/{job_id}` route — inject authenticated tenant context and DB session; call `get_by_id_and_tenant(job_id, tenant_id)`; raise `404` if `None`; return `200 RagQueryJobResponse` mapping domain entity fields to camelCase response

## 6. Worker

- [ ] 6.1 Create `apps/api/app/workers/query_worker.py` — implement `handle_rag_query(job: Job, token: str) -> None`: open `AsyncSession` via `session_factory`; call `repo.update_running(job.data["job_id"])`; call `RagQueryService(session, settings).query(...)` with all fields from `job.data`; on success call `repo.update_completed(...)` then `_fire_webhook(..., "completed", result, None)`; on exception call `repo.update_failed(...)` then `_fire_webhook(..., "failed", None, str(exc))` and re-raise
- [ ] 6.2 Implement `_fire_webhook(url: str | None, job_id: str, status: str, result, error: str | None) -> None` in `query_worker.py` — if `url` is None return immediately; use `httpx.AsyncClient(timeout=10.0)` to POST JSON payload `{jobId, status, result, error}`; swallow all exceptions (fire-and-forget)
- [ ] 6.3 Implement `create_query_worker(settings, session_factory, redis_opts) -> Worker` factory in `query_worker.py` — return `Worker("rag.query", handle_rag_query, {"connection": redis_opts, "concurrency": 10})`
- [ ] 6.4 Import `create_query_worker` in `apps/api/app/workers/main.py` and add it to the worker list alongside the existing workers

## 7. Tests

- [ ] 7.1 Add `apps/api/tests/workers/test_query_worker.py` — mock `RagQueryService.query` to return a result dict; mock `SqlAlchemyRagQueryJobRepository`; call `handle_rag_query` with a fake job; assert `update_running` called first, then `update_completed` with the result; assert no exception raised
- [ ] 7.2 Add test for failure path in `test_query_worker.py` — mock `RagQueryService.query` to raise; assert `update_failed` called with error string; assert exception re-raised
- [ ] 7.3 Add test for `_fire_webhook` in `test_query_worker.py` — mock `httpx.AsyncClient.post`; assert POST called with correct URL and JSON payload; assert no exception raised when POST raises (fire-and-forget)
- [ ] 7.4 Add test for `_fire_webhook` when `url=None` — assert no HTTP call is made
- [ ] 7.5 Add `apps/api/tests/http/test_async_rag_query.py` — mock `Queue.add` and `SqlAlchemyRagQueryJobRepository.create`; POST to `/rag/query/async` with valid payload; assert 202 and `jobId` / `conversationId` in response
- [ ] 7.6 Add test: `POST /rag/query/async` with `webhook_url="http://..."` returns 422
- [ ] 7.7 Add test: `GET /rag/query/jobs/{job_id}` returns 200 with correct fields for own-tenant job
- [ ] 7.8 Add test: `GET /rag/query/jobs/{job_id}` returns 404 for cross-tenant job (mock `get_by_id_and_tenant` returning `None`)
- [ ] 7.9 Run `pytest apps/api/tests/workers/test_query_worker.py apps/api/tests/http/test_async_rag_query.py` and confirm all tests pass
