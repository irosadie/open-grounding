## Why

The RAG platform cannot provide trustworthy retrieval until source material is
accepted, versioned, transformed, indexed, and recoverable through one durable
pipeline. The platform foundation supplies the catalog and storage boundaries; this
change turns them into the first usable knowledge corpus without prematurely adding
connectors, advanced OCR, graph projection, or answer generation.

## What Changes

- Add tenant-scoped upload intake for PDF, Markdown, and plain-text files using
  presigned object-store uploads, server-side completion validation, and knowledge
  base authorization.
- Add idempotent document/version lifecycle records with checksum, source revision,
  pipeline fingerprint, quarantine/rejection, and soft/hard deletion semantics.
- Add parser routing, canonical ordered document elements, normalization, quality
  gates, and persisted parser artifacts that allow re-chunking without re-parsing.
- Add content-aware parent-child chunking with deterministic chunk identity and
  preserved section/page/source lineage.
- Add a staged Node BullMQ ingestion workflow that invokes provider adapters, records
  checkpointed progress in FastAPI/PostgreSQL, creates dense and sparse representations,
  and publishes validated Qdrant index generations.
- Add retries, reindexing, status APIs, operational metrics, and safe cleanup while
  retaining the previous active document version until replacement validation passes.
- Exclude remote connectors, office formats, images/scanned OCR, table extraction,
  code repositories, live data tools, graph projection, retrieval/query endpoints,
  reranking, and answer generation.

## Capabilities

### New Capabilities

- `rag-source-intake-and-versioning`: Accept, validate, authorize, version, and delete
  the first tenant-owned file sources safely.
- `rag-content-extraction-and-quality`: Convert supported files into canonical,
  persisted elements and enforce extraction quality before indexing.
- `rag-structure-aware-chunking`: Produce deterministic parent-child chunks with
  source lineage and content-aware boundaries.
- `rag-ingestion-orchestration-and-indexing`: Run idempotent staged jobs, create
  dense/sparse vectors, and atomically publish validated Qdrant generations.
- `rag-ingestion-operations`: Expose lifecycle status, retry/reindex/delete controls,
  audits, metrics, and failure recovery for ingestion.

### Modified Capabilities

None. No main OpenSpec capability specifications exist yet.

## Impact

- Adds FastAPI RAG source/intake/status routes, Pydantic models, use cases,
  repositories, Alembic migrations, and generated OpenAPI operations.
- Adds Node BullMQ ingestion job registration and worker adapters while preserving the
  Node worker runtime and Redis broker.
- Uses the tenant foundation and RAG platform catalog, object store, provider ports,
  Qdrant generation/outbox, and operational diagnostics as prerequisites.
- Adds parser and model-provider configuration plus RAG integration/evaluation fixtures
  for supported document formats; it does not add a frontend ingestion UI yet.
