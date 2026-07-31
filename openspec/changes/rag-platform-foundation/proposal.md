## Why

Reliable ingestion and grounded retrieval require durable, secure platform boundaries
before application features are added. The current FastAPI starter has PostgreSQL,
Redis, and a Node BullMQ worker, but it lacks the vector, object-storage, knowledge
catalog, provider-port, and operational contracts that let RAG features be built and
recovered safely.

## What Changes

- Add a portable RAG infrastructure profile for Qdrant and an S3-compatible object
  store alongside the existing shared PostgreSQL and Redis services.
- Establish FastAPI configuration, health/readiness diagnostics, and provider-neutral
  ports for object storage, vector search, embeddings, sparse encoding, reranking,
  and generation without choosing a hosted model provider.
- Add the tenant-scoped PostgreSQL knowledge catalog for knowledge bases, sources,
  documents, versions, model/index profiles, ingestion jobs, index generations, and
  transactional outbox events.
- Define durable derived-index publication, retry-safe job identity, trace context,
  and rebuild/backup operational boundaries.
- Keep Qdrant and graph projections derived and rebuildable; PostgreSQL and object
  storage remain authoritative.
- Exclude upload endpoints, parser/OCR, chunking, embedding execution, document
  indexing, retrieval, answer generation, graph deployment, and frontend RAG UI.

## Capabilities

### New Capabilities

- `rag-infrastructure-runtime`: Provide secure, persistent, portable local runtime
  profiles for vector and object-storage dependencies with health diagnostics.
- `rag-provider-ports`: Define tenant-aware, provider-neutral contracts and validated
  model/index configuration for RAG external services.
- `rag-knowledge-catalog`: Persist the tenant-scoped knowledge lifecycle, document
  lineage, index generations, ingestion job records, and transactional outbox.
- `rag-operational-safety`: Define trace propagation, idempotency, recovery,
  snapshot/backup, and derived-index rebuild requirements for the RAG platform.

### Modified Capabilities

None. No main OpenSpec capability specifications exist yet.

## Impact

- Adds FastAPI domain/application/infrastructure modules, SQLAlchemy mappings,
  Alembic migrations, tests, and generated OpenAPI diagnostics for the RAG platform.
- Extends the shared Docker service through a portable configuration path with Qdrant
  and an S3-compatible object store; existing PostgreSQL, Redis, and Node BullMQ
  worker behavior remains unchanged.
- Adds configuration and operational documentation for provider profiles, persistent
  volumes, API keys, snapshot/rebuild procedures, and health checks.
- Depends on the tenant-ready single-deployment foundation for tenant identity,
  membership, and mandatory tenant context. It does not implement that foundation
  itself.
