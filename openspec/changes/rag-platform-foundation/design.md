## Context

The completed FastAPI migration provides PostgreSQL, Redis, a Node BullMQ worker, and
Clean Architecture boundaries. The RAG architecture requires additional durable
platform contracts before ingestion or retrieval can safely exist: an object store for
binary sources, Qdrant for derived retrieval indexes, a knowledge catalog, model/index
profiles, provider ports, and recovery semantics.

This change is planned after `tenant-ready-single-deployment`. It consumes the future
`TenantContext` and does not duplicate tenant or membership ownership. The runtime
must remain practical for a local-first open-source deployment and must not require a
hosted LLM, graph database, or migrated Python worker.

## Goals / Non-Goals

**Goals:**

- Add secure, persistent, portable Qdrant and S3-compatible object-store runtime
  profiles without changing PostgreSQL, Redis, or Node worker behavior.
- Establish tenant-aware RAG ports and validated provider/index configuration.
- Create the authoritative PostgreSQL catalog and outbox needed by future ingestion
  and index publication.
- Establish health, readiness, trace, backup, snapshot, and rebuild boundaries.
- Make it impossible for a future derived index to become the only record of content.

**Non-Goals:**

- File upload, connectors, parsing, OCR, normalization, chunking, embedding calls,
  or vector upsert execution.
- Hybrid retrieval, reranking, answer generation, streaming, citations, or frontend
  RAG screens.
- Graph database deployment, graph projection, or local/hosted model installation.
- Multi-tenant SaaS mode, tenant lifecycle implementation, billing, or user-facing
  tenant administration.
- Migrating BullMQ workers from Node to Python.

## Decisions

### Use Qdrant and an S3-compatible object store as derived and binary stores

PostgreSQL is authoritative for knowledge identity, tenant ownership, lifecycle,
versioning, index generation, and audit. The object store is authoritative for raw
sources and large parser artifacts. Qdrant stores dense/sparse vectors plus minimal
retrieval payload and is rebuildable from the catalog and object store.

Qdrant runs in a pinned Docker image with persistent storage and snapshot volumes,
an API key, strict mode, internal-only network exposure, and payload indexes for
mandatory fields. The object-store port uses S3 semantics. `LocalFileObjectStore` is
permitted only for simple development; SeaweedFS is the default self-hosted
S3-compatible production profile. No business layer imports a Qdrant or S3 SDK.

Alternatives considered:

- PostgreSQL `pgvector` does not meet the planned dense+sparse hybrid and operational
  separation goals as cleanly as Qdrant.
- Elasticsearch introduces a second search runtime before retrieval evaluation proves
  it is necessary.
- Storing raw files in Qdrant or PostgreSQL damages recovery, retention, and storage
  characteristics.

### Model/index profiles make external providers replaceable

The catalog stores immutable, versioned `model_profiles` and `index_profiles` that
describe the embedding model, vector dimensions, distance metric, sparse profile,
collection name, and provider configuration reference. Active profile changes create
a new index generation rather than rewriting an active index in place.

Application ports cover object storage, vector index, embedding, sparse encoder,
reranker, and generation. Implementations may be local or hosted, but secrets stay in
environment/secret configuration and are never stored in a profile or returned by
diagnostics. The foundation validates profile compatibility without making a model
inference call.

Alternatives considered:

- Binding domain code directly to one provider makes local/self-hosted support and
  future changes expensive.
- A mutable active collection risks mixing incompatible vector dimensions or models.

### Build a catalog before RAG content exists

The tenant-scoped catalog has the following core records:

| Record | Purpose |
| --- | --- |
| `knowledge_bases` | Tenant-owned logical corpus and policy boundary. |
| `knowledge_sources` | Future upload/connector origin and source configuration reference. |
| `documents` | Stable logical document identity. |
| `document_versions` | Immutable source version, lifecycle state, checksums, and object references. |
| `model_profiles` | Embedding/reranker/generation profile metadata without secrets. |
| `index_profiles` | Compatible vector/sparse collection and profile configuration. |
| `index_generations` | Pending/active/failed derived index publication generation. |
| `ingestion_jobs` | Durable future job identity, stage, retry count, and trace context. |
| `outbox_events` | Transactional events to dispatch post-commit. |

All future catalog records include non-null tenant ownership supplied by the prerequisite
tenant foundation. The foundation may create tables and repositories but does not
create documents, enqueue ingestion, or write vectors.

### Publish derived indexes through generation state and a transactional outbox

Future ingestion creates a pending index generation and outbox event in the same
PostgreSQL transaction. A worker dispatches only committed events, performs derived
store work idempotently, and reports completion. The generation becomes active only
after validation; failed generations never replace the active one. Reindex/delete
operations use the same generation and outbox boundary.

This is a saga, not a distributed transaction. Qdrant and S3 side effects can be
reconciled from the catalog. Event payloads include tenant ID, resource/version ID,
generation ID, idempotency key, and trace context.

### Diagnostics distinguish liveness, readiness, and recovery

Existing `/health` remains a lightweight liveness contract. A protected or
operator-oriented readiness diagnostic reports PostgreSQL, Redis, Qdrant, object
storage, active deployment tenant, and active index profile status without exposing
credentials, internal URLs, or raw provider errors. It is not a retrieval endpoint.

Operator runbooks define:

- PostgreSQL backup and Alembic restore;
- object-store version/backup and restore;
- Qdrant snapshots and restore;
- derived-index rebuild from catalog plus object store;
- recovery of stuck outbox events and job records.

## Risks / Trade-offs

- [More services increase self-hosted setup complexity] → Ship version-pinned profiles,
  health checks, persistent volumes, and an explicit local-file development adapter.
- [Index and catalog can drift after partial failure] → Use generation state, outbox,
  idempotency keys, reconciliation, and rebuild procedures.
- [Embedding profile changes can make vectors incompatible] → Create a new immutable
  profile and generation; never mutate an active collection in place.
- [External service secrets could leak through diagnostics] → Store only references in
  the catalog and redact readiness/error output.
- [Foundation tables may be unused until ingestion lands] → Keep the catalog minimal
  and omit content/chunk tables until the ingestion change owns them.
- [Tenant prerequisite may not be applied first] → Block platform migrations and
  repository use until `TenantContext` and tenant ownership exist.

## Migration Plan

1. Apply the tenant-ready single-deployment change and verify its database baseline.
2. Add portable shared-service profiles and verify Qdrant/object-store health with
   persistent volumes and non-default credentials.
3. Add RAG settings, ports, provider configuration validation, and safe diagnostics.
4. Apply additive catalog, profile, generation, job, and outbox Alembic migrations.
5. Add repository/adapter contract tests, including tenant scope and profile
   compatibility tests, without processing a document.
6. Document backup, snapshot, restore, and rebuild drills; run a disposable recovery
   test before ingestion is enabled.

Rollback removes application use of the new platform before any RAG data is written.
Once catalog metadata or object data exists, rollback preserves the PostgreSQL catalog
and object-store data; Qdrant remains disposable and is rebuilt rather than treated as
a rollback source.

## Open Questions

- Is SeaweedFS accepted as the production default or should the project ship only an
  S3 interface plus documented compatible providers?
- Should Qdrant and object storage be placed in one shared compose profile or distinct
  `rag` and `object-store` profiles for resource-constrained development?
- Which local embedding profile is officially supported first, and what dimension and
  sparse encoder does it require?
- Should operator readiness be a protected HTTP route, CLI-only command, or both?
