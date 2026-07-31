## 1. Python API foundation

- [x] 1.1 Add `uv`-managed Python packaging, locked dependencies, environment settings, and documented API commands under `apps/api`.
- [x] 1.2 Create the FastAPI application factory, lifespan/configuration wiring, CORS setup, and development entrypoint on the existing API port.
- [x] 1.3 Establish Python Clean Architecture packages for domain, application, infrastructure, and HTTP interfaces.
- [x] 1.4 Add Pytest, async test fixtures, HTTP test client, and baseline lint/type-check commands for the API service.

## 2. Domain and asynchronous persistence

- [x] 2.1 Port the User and AuthSession domain entities, repository protocol, domain errors, and system/authentication use cases to Python.
- [x] 2.2 Add SQLAlchemy 2 async engine, session dependency, ORM mappings, and repository implementations for users and auth sessions.
- [x] 2.3 Add Alembic configuration and initial schema-equivalent migration for user/auth-session tables, enums, constraints, and indexes.
- [x] 2.4 Document and test the safe procedure to stamp or migrate an existing Prisma-created PostgreSQL database without destructive data changes.
- [x] 2.5 Add repository integration tests against disposable PostgreSQL covering user lookup, session lifecycle, and existing-row compatibility.

## 3. HTTP API and authentication

- [x] 3.1 Add Pydantic v2 request/response models and shared success/error envelope helpers compatible with the existing API contract.
- [x] 3.2 Add exception handlers for domain, authentication, request-validation, and unexpected errors with compatible status codes and error shapes.
- [x] 3.3 Implement FastAPI system routers for `GET /` and `GET /health` with contract tests.
- [x] 3.4 Implement password hashing and verification, including compatibility with legacy Node `salt:hex-scrypt` hashes.
- [x] 3.5 Implement JWT token creation and verification with existing claims, issuer, audience, access expiry, refresh expiry, and token-revocation behavior.
- [x] 3.6 Implement FastAPI authentication dependencies for Bearer tokens, suspended accounts, session access, and role checks.
- [x] 3.7 Implement `/auth/register`, `/auth/login`, `/auth/logout`, and `/auth/me` with HTTP contract tests.
- [x] 3.8 Implement `/auth/refresh` in the format expected by the Next.js proxy and add refresh/retry compatibility tests.

## 4. Documentation and repository integration

- [x] 4.1 Export FastAPI-generated OpenAPI to `docs/openapi.json` and update Scalar/OpenAPI commands and documentation.
- [x] 4.2 Update root scripts, bootstrap helpers, API environment examples, and README instructions for `uv`, Alembic, and Pytest.
- [x] 4.3 Update CI to install Python/uv and execute API format, type, test, and OpenAPI checks alongside existing Bun checks.
- [x] 4.4 Keep Docker Compose PostgreSQL/Redis configuration and the Node BullMQ worker unchanged; validate the worker still starts with Redis.

## 5. Migration verification and cleanup

- [x] 5.1 Run FastAPI unit, HTTP-contract, repository, migration, and OpenAPI-generation checks.
- [x] 5.2 Run frontend auth/proxy and smoke tests against the FastAPI service to verify response and token compatibility.
- [x] 5.3 Remove Hono, Prisma, TypeScript API runtime files, obsolete scripts, and dependencies after FastAPI checks pass.
- [x] 5.4 Run the documented full repository quality checks and record any intentionally deferred deployment/container follow-up.
