## Why

The backend starter currently runs on Hono, Prisma, and TypeScript while the desired
backend standard is Python with FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic,
and Pytest. Migrating before domain features are added keeps the platform consistent
with the target Python stack without requiring the Next.js frontend or Node-based
BullMQ worker to change.

## What Changes

- **BREAKING** Replace the `apps/api` Hono/TypeScript runtime with a FastAPI/Python
  service while preserving the API's externally observable HTTP contract.
- Replace Prisma data access with SQLAlchemy 2 asynchronous models, sessions, and
  repositories backed by the existing PostgreSQL database.
- Introduce Alembic as the schema migration mechanism for the existing `User` and
  `AuthSession` persistence model.
- Replace Zod HTTP validation with Pydantic v2 request and response models in the
  API while retaining Zod schemas in `packages/schemas` for frontend validation.
- Preserve JWT authentication semantics, response/error envelopes, CORS behavior,
  system endpoints, and the API base URL consumed by the Next.js proxy.
- Generate the runtime OpenAPI document from FastAPI and retain a documented
  workflow for the repository's OpenAPI artifact.
- Replace backend Vitest coverage with Pytest coverage for unit and HTTP contract
  tests.
- Keep PostgreSQL, Redis, Docker Compose, the Next.js frontend, shared TypeScript
  packages, and the BullMQ worker in Node.js unchanged.

## Capabilities

### New Capabilities

- `fastapi-api-runtime`: Run system and authentication API functionality through a
  FastAPI application using the repository's Clean Architecture boundaries.
- `async-postgres-persistence`: Persist the existing user and auth-session model
  through SQLAlchemy 2 async with Alembic-managed PostgreSQL schema changes.
- `api-contract-compatibility`: Preserve the API contract used by the frontend,
  including envelopes, authentication behavior, and generated OpenAPI.

### Modified Capabilities

None. There are no existing OpenSpec capability specifications in this repository.

## Impact

- Replaces the contents and runtime tooling of `apps/api`.
- Updates root orchestration, bootstrap, Docker, CI, and developer documentation
  where they invoke the API runtime or database migration tooling.
- Leaves `apps/web`, `apps/worker`, `packages/schemas`, `packages/types`, and
  `packages/utils` functionally compatible; only their API integration assumptions
  are verified.
- Adds Python dependencies and lock/tooling configuration for the API service.
