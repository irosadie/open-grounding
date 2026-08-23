# Proposal: worker-consolidation

## Summary

Consolidate the TypeScript BullMQ worker (`apps/worker/`) and the manual-Redis Python worker (`apps/api/app/workers/`) into a single, proper BullMQ Python worker powered by `python-bullmq 3.0.4`.

## Problem

The system currently runs two background worker processes with separate operational concerns:

1. **TypeScript worker** (`apps/worker/`) — three BullMQ processors (`tool-execution`, `calibration`, `synthetic-fixture`) that are pure HTTP proxies: they receive a job, POST to a Python internal API endpoint, and return the result. There is zero business logic in TypeScript — it exists only to bridge BullMQ to Python.

2. **Python worker** (`apps/api/app/workers/`) — handles all ingestion pipeline stages (parse → chunk → embed → index → validate) plus memory jobs, but uses manual `HSET`/`LPUSH` Redis commands instead of proper BullMQ primitives. This means no retry, no backoff, no dead-letter queue, no job lifecycle events, and no interoperability guarantee with the TypeScript side.

This split creates:
- Two separate processes to deploy, monitor, and scale
- Internal HTTP round-trips for every tool-execution, calibration, and synthetic-fixture job
- Brittle Redis key manipulation that diverges from BullMQ's Lua-script-managed state machine
- Operational overhead: two Dockerfiles, two dependency trees, two health checks

## Solution

Install `python-bullmq 3.0.4` (official, MIT, pure Python, ~1 MB, depends only on `redis`) as a core dependency in `apps/api/pyproject.toml`. Rewrite `apps/api/app/workers/ingestion_worker.py` as a proper `bullmq.Worker`-based implementation, and add three new Python worker handlers for `tool-execution`, `calibration`, and `synthetic-fixture` that call Python application-layer functions directly instead of making HTTP calls. Remove `apps/worker/` entirely.

## Goals

- Single Python worker process handles all 10 queues
- Proper BullMQ job lifecycle: retry, backoff, dead-letter, progress, cancellation
- No internal HTTP calls between worker and API for job execution
- No manual Redis key manipulation
- Full interoperability with BullMQ TypeScript clients that enqueue jobs (producers remain unchanged)
- Reduced operational surface: one process, one Dockerfile, one deploy unit

## Non-Goals

- Changing any BullMQ producer code (frontend, API routes, etc.)
- Migrating queue names (all existing names are preserved)
- Replacing Redis or BullMQ with a different queue technology
- Adding new business logic beyond what already exists in the Python application layer

## Affected Areas

| Area | Change |
|---|---|
| `apps/api/pyproject.toml` | Add `bullmq==3.0.4` to core dependencies |
| `apps/api/app/workers/ingestion_worker.py` | Rewrite using `bullmq.Worker` |
| `apps/api/app/workers/main.py` | Update entrypoint to start consolidated worker |
| `apps/api/app/workers/` | Add handlers for tool-execution, calibration, synthetic-fixture |
| `apps/api/app/application/confidence_service.py` | Replace manual `LPUSH` with `bullmq.Queue` |
| `apps/worker/` | Delete entirely |
| `docker-compose.yml` | No change (TypeScript worker was not a compose service) |

## Risk

Low. The `python-bullmq` library is the official Python port, shares Lua scripts with the TypeScript implementation, and is fully interoperable at the Redis level. The TypeScript worker is already stateless (no local state, no DB writes). The Python application layer functions being called already exist and are tested. The queue names and job data shapes are unchanged.
