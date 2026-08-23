## 1. Tenant foundation and migration

- [x] 1.1 Add validated `DEPLOYMENT_TENANT_ID` and single-deployment mode settings, startup verification, and operator diagnostics without accepting client tenant selection.
- [x] 1.2 Add tenant and tenant-membership domain models, SQLAlchemy mappings, repository protocols, and an additive Alembic migration with required indexes and constraints.
- [x] 1.3 Backfill active membership for existing users in the sole deployment tenant without changing user or auth-session identifiers.
- [x] 1.4 Add database integration tests for valid bootstrap, membership backfill, immutable tenant mismatch, and cross-tenant relational integrity.

## 2. FastAPI tenant context and authorization

- [x] 2.1 Implement immutable `TenantContext` and FastAPI dependencies that resolve the configured deployment tenant plus authenticated active membership.
- [x] 2.2 Require tenant context in tenant-owned application-service and repository contracts; reject missing or inactive membership before resource access.
- [x] 2.3 Add tenant-aware audit fields and trace correlation for mutations and security-relevant access denials.
- [x] 2.4 Add HTTP contract and unit tests proving that client-supplied tenant values cannot override deployment scope.

## 3. Tenant-aware RAG adapter boundaries

- [x] 3.1 Add provider-neutral tenant namespace and filter primitives for object keys, BullMQ payload/idempotency keys, cache keys, Qdrant payload filters, and optional graph predicates.
- [x] 3.2 Require tenant context in future RAG adapter ports and reject missing or mismatched tenant scope before adapter operations execute.
- [x] 3.3 Add disposable two-tenant integration tests proving derived-store key/filter construction prevents cross-tenant read, mutation, and deletion.

## 4. Operations, documentation, and verification

- [x] 4.1 Document single-deployment bootstrap, configuration validation, backup/restore expectations, and the unsupported in-place tenant-ID change.
- [x] 4.2 Document the shared-SaaS and dedicated-enterprise migration paths, including the deferred PostgreSQL RLS and containerization decisions.
- [x] 4.3 Run FastAPI unit, HTTP-contract, migration, repository integration, and generated OpenAPI checks.
- [x] 4.4 Run frontend auth/proxy compatibility checks and the documented full repository quality gate.
