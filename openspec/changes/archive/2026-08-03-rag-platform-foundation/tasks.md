## 1. Prerequisites and RAG runtime profile

- [x] 1.1 Verify `tenant-ready-single-deployment` is implemented and expose its tenant context to the RAG platform modules.
- [x] 1.2 Add portable shared-service configuration for pinned Qdrant and S3-compatible object storage with persistent volumes, internal networking, and no `latest` image tags.
- [x] 1.3 Add Qdrant API-key, strict-mode, payload-index, snapshot, and production exposure validation; keep existing PostgreSQL, Redis, and Node worker behavior unchanged.
- [x] 1.4 Add runtime integration checks for service health, persistence across restart, and Node BullMQ worker compatibility with the RAG profile enabled.

## 2. Configuration, diagnostics, and provider ports

- [x] 2.1 Add validated FastAPI RAG settings for runtime mode, provider references, Qdrant, object storage, and active deployment/index profile identifiers without storing secrets in PostgreSQL.
- [x] 2.2 Add tenant-aware application ports and domain value objects for object storage, vector index, embedding, sparse encoding, reranking, and generation.
- [x] 2.3 Implement infrastructure health adapters and liveness/readiness diagnostics that redact credentials, internal URLs, and raw provider errors.
- [x] 2.4 Add unit and HTTP-contract tests for settings validation, provider-profile compatibility, diagnostics, and tenant-required adapter contracts.

## 3. Knowledge catalog and durable publication foundation

- [x] 3.1 Add tenant-scoped domain models and SQLAlchemy mappings for knowledge bases, sources, documents, document versions, model/index profiles, index generations, ingestion jobs, and outbox events.
- [x] 3.2 Create additive Alembic migrations with tenant-local constraints, indexes, immutable version/generation lineage, and no document-content or chunk table yet.
- [x] 3.3 Implement tenant-scoped repository protocols and SQLAlchemy repositories for catalog, profiles, generations, jobs, and outbox records.
- [x] 3.4 Add pending-generation and transactional-outbox application services with stable idempotency and trace context, without dispatching parser, embedding, or retrieval work.
- [x] 3.5 Add PostgreSQL integration tests for tenant isolation, catalog lineage, incompatible-profile rejection, atomic outbox creation, and failed-generation recovery state.

## 4. Operations, documentation, and verification

- [x] 4.1 Document profile configuration, shared-service startup, secret handling, health/readiness interpretation, and the development local-file object-store adapter.
- [x] 4.2 Document PostgreSQL backup/restore, object-store backup/restore, Qdrant snapshot/restore, derived-index rebuild, and stuck-outbox reconciliation procedures.
- [x] 4.3 Export generated FastAPI OpenAPI diagnostics and run FastAPI lint, type, unit, HTTP-contract, migration, and repository integration checks.
- [x] 4.4 Run Node worker, frontend compatibility, and full repository quality checks; record the explicit handoff to `rag-ingestion-foundation`.
