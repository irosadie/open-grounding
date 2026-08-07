# Proposal: async-rag-query

## Summary

Add an async execution path for RAG queries: `POST /rag/query/async` enqueues the job to BullMQ, returns 202 immediately, and a new Python worker calls the existing `RagQueryService.query()` to process it. Results are stored in a new `rag_query_jobs` table and retrievable via `GET /rag/query/jobs/:jobId`. Optional per-request webhook support fires the result to a caller-supplied URL on completion.

## Problem

`POST /rag/query` is synchronous — the HTTP connection stays open for 10–30 seconds while retrieval and LLM generation run inline. This causes:

1. **Client timeouts** — mobile clients, serverless runtimes, and API gateways frequently time out before the response arrives.
2. **No retry safety** — a dropped connection loses the work entirely; there is no way to recover the result.
3. **Blocked threads** — long-running LLM calls occupy FastAPI worker threads, reducing throughput for all other requests.
4. **No observability** — callers have no way to check whether a slow query is still running or has silently failed.

## Solution

Introduce an async query path built on the BullMQ infrastructure from `worker-consolidation`:

- `POST /rag/query/async` — validates the request, creates a `rag_query_jobs` row, enqueues a job on the `rag.query` BullMQ queue, and returns `202 { jobId, conversationId }` immediately.
- `GET /rag/query/jobs/:jobId` — returns current job status and, when complete, the full query result. Scoped to the authenticated tenant.
- A new `rag-query` BullMQ Worker (Python, concurrency 10) calls `RagQueryService.query()` directly, stores the result, and optionally fires a webhook.

The synchronous `POST /rag/query` endpoint is **not removed** — both paths coexist.

## Goals

- Return 202 within ~50ms regardless of retrieval or LLM latency
- Persist job state and result so clients can poll or receive webhook
- Call existing `RagQueryService.query()` directly — no duplication of business logic
- Scope all job access to the authenticated tenant (cross-tenant 404)
- Webhook URL must be `https://` only; fire-and-forget with 10s timeout
- Retry: 2 attempts, exponential backoff 3000ms

## Non-Goals

- Removing or changing `POST /rag/query` (sync path stays)
- Streaming results via SSE or WebSocket
- Webhook signature/HMAC verification
- Job cancellation
- Frontend UI for job polling (this change is API-only)
- Rate limiting on the async endpoint beyond existing tenant auth

## Dependencies

- **worker-consolidation** must be complete: `python-bullmq 3.0.4` installed, Python worker running

## Affected Areas

| Area | Change |
|---|---|
| `apps/api/alembic/versions/` | New migration: `rag_query_jobs` table |
| `apps/api/app/domain/rag/` | New `RagQueryJob` entity + `RagQueryJobStatus` enum |
| `apps/api/app/infrastructure/rag_catalog.py` | New `RagQueryJobRecord` ORM model + `SqlAlchemyRagQueryJobRepository` |
| `apps/api/app/interfaces/http/schemas.py` | New request/response Pydantic schemas |
| `apps/api/app/interfaces/http/routes.py` | 2 new endpoints: `POST /rag/query/async`, `GET /rag/query/jobs/{job_id}` |
| `apps/api/app/workers/query_worker.py` | New file — BullMQ Worker for `rag.query` queue |
| `apps/api/app/workers/main.py` | Add `rag.query` worker to startup |

## Risk

Low. `RagQueryService.query()` already exists and is tested. The new async path is purely additive — no existing endpoints or business logic change. The `rag_query_jobs` table is append-only from the HTTP layer and updated only by the worker, so there is no write contention. Webhook dispatch is fire-and-forget and cannot affect job state.
