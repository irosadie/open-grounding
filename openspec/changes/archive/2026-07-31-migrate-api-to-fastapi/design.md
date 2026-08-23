## Context

`apps/api` is a TypeScript/Hono starter with domain entities, use cases, repository interfaces, JWT authentication, Prisma persistence, Vitest tests, and a manually merged OpenAPI artifact. The frontend calls the API only through its internal proxy at `http://localhost:3001` and retains TypeScript/Zod packages. PostgreSQL and Redis are provided by Docker Compose; the Redis-backed BullMQ worker remains a separate Node.js process.

The migration replaces the API implementation before domain features are added. The existing `User` and `AuthSession` tables, response/error envelopes, HTTP paths, and JWT claims are compatibility boundaries. The current auth router is not mounted in the Hono app; the FastAPI service will make the documented auth surface explicit.

## Goals / Non-Goals

**Goals:**

- Provide a Python FastAPI API with Clean Architecture boundaries equivalent to the current backend layering.
- Use Pydantic v2, SQLAlchemy 2 async, Alembic, and Pytest.
- Keep the PostgreSQL schema and frontend API contract compatible.
- Generate a consumable OpenAPI document from the FastAPI application.
- Keep the web app, shared TypeScript packages, Redis infrastructure, and BullMQ worker operational without migration.

**Non-Goals:**

- Migrating the worker to Python or replacing BullMQ/Redis.
- Rebuilding the frontend or removing its Zod validation.
- Introducing new product/domain features, multi-tenancy, or a new authorization model.
- Changing the public API version, base URL, or response-envelope convention.

## Decisions

### Python packaging and service layout

`apps/api` will become a standalone Python service managed with `uv`, using `pyproject.toml` and a committed lock file. Source will be arranged into `domain`, `application`, `infrastructure`, and `interfaces/http` packages. This preserves the current architectural intent while using Python-native imports and dependency injection.

Alternatives considered: keeping a TypeScript API alongside FastAPI adds two runtimes and creates ambiguity; using a requirements.txt-only workflow does not provide reproducible modern dependency resolution. Both are rejected.

### Database access and migrations

Use SQLAlchemy 2's asynchronous engine/session factory with an async PostgreSQL driver. Repository implementations translate SQLAlchemy ORM rows into domain entities. Alembic owns database schema migration, with an initial revision matching the existing `users`, `auth_sessions`, `UserRole`, and `UserStatus` schema rather than applying destructive changes.

Alternatives considered: SQLModel provides a thinner API but couples persistence models and API schemas; synchronous SQLAlchemy does not meet the requested async standard. Both are rejected.

### HTTP contract and validation

APIRouters, request models, and dependencies replace Hono routes, Zod validators, and middleware. A shared response factory and exception handlers will preserve the current success envelope (`success`, `message`, optional `data`/`meta`) and error envelope (`success: false`, `errors`). Authentication will be a FastAPI dependency that validates Bearer JWTs, suspended accounts, role membership, and token revocation before invoking the application service.

The API will expose `/`, `/health`, `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me`, and `/auth/refresh`. The refresh endpoint is included because the frontend proxy already depends on it, even though it is missing from the active Hono router.

Alternatives considered: returning FastAPI's default validation errors would break the existing error contract; moving validation solely to the frontend would weaken server-side safeguards. Both are rejected.

### Security implementation

Use a maintained Python password-hashing library with a self-describing, salted password format and PyJWT-compatible JWT signing/verification. New passwords are created in that format. The implementation must also verify the legacy `salt:hex-scrypt` values created by the existing Node service, so existing users can log in without a forced reset. Access and refresh tokens retain their current issuer, audience, claim names, one-hour access expiry, and seven-day refresh expiry.

The in-memory token blacklist remains a starter limitation; it is deliberately not promoted to Redis in this migration.

### OpenAPI and tooling

FastAPI's generated OpenAPI schema becomes the runtime source. A repository script will export it to `docs/openapi.json` so Scalar and existing documentation paths continue to work. Root scripts, CI, bootstrap documentation, and API developer commands will call `uv`/Alembic/Pytest for API work while Bun/Turbo continue to operate the web, worker, and TypeScript packages.

## Risks / Trade-offs

- [Legacy password verification differs by library] → Preserve a tested verifier for the existing scrypt format and rehash only through an explicit later policy.
- [PostgreSQL schema drift or data loss] → Inspect the current schema, use Alembic revision review, and do not run destructive DDL in the initial migration.
- [Frontend proxy incompatibility] → Add HTTP contract tests for all system and auth paths, envelopes, status codes, and refresh behavior.
- [Dual Node/Python tooling increases contributor setup] → Document `uv` commands and make root scripts delegate to the API service consistently.
- [In-memory revocation is not shared across API instances] → Retain the current behavior and document Redis-backed revocation as future work.

## Migration Plan

1. Add Python packaging, environment settings, FastAPI factory, and Pytest setup.
2. Port domain/application logic, database mappings, repositories, authentication, HTTP routers, error handlers, and OpenAPI export.
3. Add Alembic configuration and an initial schema-safe revision; validate it against a disposable PostgreSQL database before applying to shared environments.
4. Update root scripts, CI, compose/bootstrap references, and documentation.
5. Run Python tests, frontend tests, OpenAPI generation, and an end-to-end proxy smoke check; then remove Hono/Prisma runtime files and dependencies.

Rollback before destructive cleanup is restoring the prior `apps/api` runtime and the existing database schema. After cleanup, rollback requires a release tag or deployment artifact; no database rollback is needed for a schema-equivalent initial migration.

## Open Questions

- Should the initial Alembic revision be stamped against an already-bootstrapped PostgreSQL database, or should local environments be recreated during migration?
- Does deployment infrastructure require a Python API container image in this change, or is local/CI runtime support sufficient?
