# Open Grounding Platform Operations

This document explains how to configure, run, verify, and recover the RAG
platform runtime added by the `rag-platform-foundation` change. It covers
profile configuration, shared-service startup, secret handling, health and
readiness interpretation, the development local-file object-store adapter,
and backup/restore procedures.

## Scope

- Qdrant (derived vector store) and an S3-compatible object store (binary and
  parser artifacts) alongside the existing PostgreSQL and Redis.
- FastAPI RAG settings, provider-neutral ports, and readiness diagnostics.
- The tenant-scoped PostgreSQL knowledge catalog (no ingestion or retrieval
  execution yet).
- Recovery: PostgreSQL, object-store, Qdrant snapshot/restore, and
  derived-index rebuild.

Qdrant and object storage are **derived** stores — they can be rebuilt from
PostgreSQL plus the object store. PostgreSQL is authoritative for identity,
lifecycle, and audit.

## 1. Runtime profile configuration

### Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `RAG_ENABLED` | `false` | Feature flag; disabled by default so existing behavior is unchanged |
| `RAG_RUNTIME_MODE` | `development` | `development` or `production` |
| `QDRANT_URL` | `http://127.0.0.1:6334` | Qdrant endpoint |
| `QDRANT_API_KEY` | (none) | Required when `RAG_ENABLED=true` in production |
| `QDRANT_STRICT_MODE` | `true` | Rejects writes without a valid API key |
| `OBJECT_STORE_ENDPOINT` | `http://127.0.0.1:9100` | S3-compatible endpoint (MinIO default) |
| `OBJECT_STORE_ACCESS_KEY` | (none) | Required in production |
| `OBJECT_STORE_SECRET_KEY` | (none) | Required in production |
| `OBJECT_STORE_BUCKET` | `rag-artifacts` | Bucket for raw sources and parser artifacts |
| `OBJECT_STORE_LOCAL_PATH` | (none) | When set, a local filesystem path replaces the S3 endpoint for development |

### Production validation

When `RAG_ENABLED=true` and `RAG_RUNTIME_MODE=production`, the settings
validator rejects startup unless `QDRANT_API_KEY`,
`OBJECT_STORE_ACCESS_KEY`, and `OBJECT_STORE_SECRET_KEY` are set. A separate
config-time check (`validate_qdrant_runtime_config`) enforces that Qdrant
strict mode is enabled. Neither check contacts external services.

### Secrets

Provider credentials are loaded only from runtime configuration (environment
or a secret provider). They are never stored in PostgreSQL, model profiles,
or catalog records, and are never returned by diagnostics or readiness.

## 2. Shared-service startup

The `docker-compose.yml` at the repo root defines the full stack:

```bash
docker compose up -d            # postgres, redis, qdrant, minio
docker compose ps               # verify all healthy
```

| Service | Image (pinned) | Port | Volume |
| --- | --- | --- | --- |
| PostgreSQL | `postgres:16-alpine` | 5433 | `postgres-data` |
| Redis | `redis:7-alpine` | 6380 | `redis-data` |
| Qdrant | `qdrant/qdrant:v1.12.0` | 6334 | `qdrant-data`, `qdrant-snapshots` |
| MinIO | `minio/minio:RELEASE.2024-10-13T13-34-11Z` | 9100 / 9101 | `minio-data` |

No `latest` tags are used. Persistent volumes survive container restarts.
Qdrant ships with an API key (`QDRANT_API_KEY`), strict mode, and snapshot
storage.

## 3. Health and readiness

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Liveness — lightweight, always returns `ok` if the process is up |
| `GET /ready` | Readiness — probes PostgreSQL, Redis, Qdrant, object storage, and reports deployment tenant + active index profile |

Readiness never exposes credentials, internal URLs, or raw provider errors.
A dependency that cannot be reached is reported `unavailable`; liveness stays
`ok` so process supervision does not restart the API for an external outage.

When `RAG_ENABLED=false`, readiness only probes PostgreSQL and reports
`ragEnabled: false`.

### Local-file object-store adapter (development)

For simple local development without MinIO, set `OBJECT_STORE_LOCAL_PATH` to
a filesystem directory. The object-store health check verifies the path
exists. Production must use a real S3-compatible store.

## 4. Catalog and migration

The catalog migration is additive and tenant-scoped:

```bash
cd apps/api
uv run alembic upgrade head
```

Nine tables are created: `rag_knowledge_bases`, `rag_knowledge_sources`,
`rag_documents`, `rag_document_versions`, `rag_model_profiles`,
`rag_index_profiles`, `rag_index_generations`, `rag_ingestion_jobs`, and
`rag_outbox_events`. Every table carries a non-null `tenant_id` foreign key
to `tenants.id`. No document-content or chunk tables are added by the
foundation.

## 5. Recovery and rebuild

### PostgreSQL backup / restore

```bash
docker exec open-grounding-postgres pg_dump -U postgres open_grounding > backup.sql
# restore
docker exec -i open-grounding-postgres psql -U postgres open_grounding < backup.sql
```

PostgreSQL is the source of truth; catalog records survive a Qdrant loss.

### Object-store backup / restore

```bash
# MinIO: mirror the bucket to a local directory
mc alias set local http://127.0.0.1:9100 minioadmin minioadmin
mc mirror local/rag-artifacts ./rag-artifacts-backup
# restore
mc mirror ./rag-artifacts-backup local/rag-artifacts
```

### Qdrant snapshot / restore

```bash
# create a snapshot
curl -X POST http://127.0.0.1:6334/collections/rag/cluster -H "api-key: $QDRANT_API_KEY"
# snapshots are stored in the qdrant-snapshots volume
```

### Derived-index rebuild

Qdrant is a derived projection. If it is lost or corrupted, rebuild from the
authoritative PostgreSQL catalog plus object-store artifacts:

1. Drop the affected Qdrant collection.
2. Replay ingestion jobs from the catalog (future ingestion pipeline reads
   parser artifacts from the object store and re-embeds).
3. Validate manifest and vector counts, then promote the new generation.

Qdrant must never be the only record of tenant content.

### Stuck outbox reconciliation

Outbox events that remain `PENDING` after repeated dispatch failures can be
re-processed:

1. Query `rag_outbox_events` for `status = 'PENDING'` events older than a
   threshold.
2. Re-dispatch each event idempotently using its `idempotency_key`.
3. Mark dispatched events `DISPATCHED` with a timestamp.

Failed generations remain `FAILED` and never replace the active generation.


## 6. Document parser (docling)

The `rag-docling-parser-adapter` change adds the provider-neutral
`DocumentParser` port and the docling-backed adapter as the first officially
supported parser.

### Supported and deferred formats

| Format | v1 support | Notes |
| --- | --- | --- |
| Digital PDF | ✅ | Page, bounding box, reading order, table grids |
| Markdown | ✅ | Headings and code blocks as structural boundaries |
| Plain text (.txt) | ✅ | Ordered narrative elements |
| Scanned PDF / image OCR | deferred | Docling supports OCR; deferred to match MVP scope |
| DOCX / PPTX / XLSX | deferred | Docling supports; deferred to a format-extension change |
| HTML / email / EPUB | deferred | Docling supports; deferred |
| Code-AST | deferred | Not a docling concern; future language-parser adapter |

Unsupported MIME types are rejected without attempting conversion.

### Parser profile

The adapter is configured through an immutable, versioned `ParserProfile`:

| Field | Purpose |
| --- | --- |
| `id` | Stable profile identity |
| `pipeline` | Docling pipeline option (e.g. `standard`) |
| `model` | Layout model identifier |
| `ocr_enabled` | OCR toggle (always `false` in v1) |
| `version` | Profile version; a change creates a new generation |
| `is_active` | Whether this profile is the active one |

A profile change creates a new generation rather than mutating parsed
artifacts in place. Element IDs are deterministic (SHA-256 of version, index,
page, and text) so retries never create duplicate elements.

### Worker runtime requirements

Docling is a heavy ML dependency (PyTorch + layout models, ~GBs). It is
declared as an **optional** dependency:

```bash
cd apps/api
uv sync --extra parsing   # installs docling + PyTorch + models
```

The `DoclingParserAdapter` imports docling lazily inside `_convert`, so the
API runs without it installed. The `DocumentParser` port MUST be invoked
only by the ingestion worker parse stage — never in a FastAPI request path.

If docling is not installed and `parse` is called, the adapter raises a
`PARSER_NOT_INSTALLED` domain error with install instructions.

### Handoff to `rag-ingestion-foundation` task 3.1

The `DocumentParser` port and `DoclingParserAdapter` satisfy
`rag-ingestion-foundation` task 3.1 ("Implement provider-neutral parser
adapters"). The ingestion pipeline's parsing stage invokes the
`DocumentParser` port; docling is the concrete adapter selected through
parser-profile configuration.


## 7. Ingestion pipeline

The `rag-ingestion-foundation` change adds the source intake and processing
pipeline. Files enter through a two-phase object-store upload, become
immutable document versions, and flow through a staged pipeline:
`RECEIVED → STORED → QUEUED → PARSING → NORMALIZING → CLASSIFYING →
CHUNKING → EMBEDDING → INDEXING → VALIDATING → READY`.

### Supported formats and limits

| Format | v1 | Max size | Max pages |
| --- | --- | --- | --- |
| Digital PDF | ✅ | 50 MB (configurable) | 500 |
| Markdown | ✅ | 50 MB | n/a |
| Plain text | ✅ | 50 MB | n/a |

Unsupported MIME types are rejected before an upload target is issued.

### Intake flow

1. `POST /rag/ingestion/intake` — creates a pending document version, returns
   an object-store upload key scoped to `tenants/{tenant_id}/...`.
2. Client uploads directly to the object store (presigned or direct).
3. `POST /rag/ingestion/complete` — validates checksum, MIME, size; transitions
   to `STORED`; creates a pending index generation + outbox event.
4. `GET /rag/ingestion/status/{id}` — returns lifecycle state and progress.
5. `DELETE /rag/ingestion/{id}` — soft-deletes (removes from active retrieval).

### Chunking

Structure-aware parent-child chunking creates parent context units
(~1,000-2,000 tokens) and child retrieval units (~300-500 tokens, hard max
700). Structural boundaries (titles, code, lists, tables) are respected.
Chunk IDs are deterministic (SHA-256) so retries never create duplicates.

### Orchestration (deferred)

The Node BullMQ worker orchestrates staged jobs and calls internal
authenticated FastAPI commands for state transitions. The worker does not
write to catalog tables directly. Stage adapters (parse, normalize, chunk,
embed, index, validate) invoke the provider ports. Qdrant publication uses
deterministic point IDs and mandatory tenant/ACL/version/generation payload.

### Handoff to `rag-grounded-query`

The ingestion pipeline produces validated dense/sparse Qdrant projections
with canonical chunks, parser quality, provider profiles, and operational
traces. `rag-grounded-query` turns that corpus into grounded answers with
evidence, citations, and safe abstention.

## Grounded Query Operations

### Query Profile And Security Boundary

`POST /rag/query` accepts `message`, one or more `knowledge_base_ids`, an
optional server-owned `conversation_id`, and `stream`. `mode` is fixed to
`grounded`. The request rejects extra fields, including tenant IDs, ACL
principals, clearance, active generation IDs, and raw vector filters.

Tenant context is derived from the authenticated membership and deployment
configuration. The service validates the selected knowledge bases for that
tenant, applies rate, payload, and concurrency limits, and constructs the
mandatory policy scope server-side. The same scope is required for dense,
sparse, canonical-context, and parent-expansion access. Clients must never
treat a response as authorization to fetch a chunk, Qdrant point, source
object, or another tenant's trace directly.

The initial query profile is controlled through `RAG_QUERY_*`,
`RAG_RETRIEVAL_*`, `RAG_CONTEXT_*`, and `RAG_GENERATION_*` settings. Candidate
budgets, timeouts, conversation window, retention period, and one bounded
retrieval/repair attempt are configuration, not client controls. Numeric
confidence is intentionally not exposed.

### Blocking And SSE Contract

With `stream: false` (the default), the API returns the normal success
envelope with an answer result containing `answer`, `route`, `evidenceLevel`,
`citations`, `limitations`, and `traceId`.

With `stream: true`, the response content type is `text/event-stream` and
events appear in this order:

1. `response.started` with `traceId`
2. `response.route` with `route`
3. `response.retrieval_summary` with `evidenceLevel`
4. `response.delta` with the final answer, only when there is a validated answer
5. `response.citations` with final citations
6. `response.completed` with `traceId`, `evidenceLevel`, and `limitations`

An execution failure produces only `response.failed` with `QUERY_FAILED`.
Events never expose raw vectors, mandatory filters, provider errors, prompts,
hidden reasoning, provider secrets, or cross-tenant metadata. The release
model validates final output before emitting `response.delta`; it does not
stream provisional model tokens.

### Evidence Levels And Abstention

`high`, `medium`, `low`, and `none` describe evidence sufficiency, not a
calibrated probability. A response can route to `grounded`, `clarify`, or
`abstain`. When a permitted active generation or validated evidence is not
available, the service returns a safe `abstain` outcome with a user-safe
limitation and no citations.

The current deployment path records retrieval, reranking, and generation as
`skipped` when it takes this safe-abstention fallback. Operators must not
interpret that trace as a successful model execution. Full retrieval and
generation adapters remain subject to the same server-built policy scope and
validation-before-release rule.

### Trace, Feedback, Retention, And Debugging

Every query receives a trace ID and persists tenant-scoped query forms,
profile snapshot, route, evidence level, limitations, bounded retrieval
summary, and validation outcome. It does not persist raw source duplication,
hidden reasoning, prompts, vectors, or provider credentials.

`GET /rag/query/traces/{trace_id}` is available only to tenant `ADMIN` users.
The endpoint returns 404 for a non-existent, cross-tenant, or expired trace.
Trace retention is set by `RAG_QUERY_TRACE_RETENTION_DAYS` (30 days by
default). Operators should retain the trace ID from query/SSE completion,
inspect the route and bounded stage outcomes, then correlate structured
`rag_query_stage` metrics and tenant audit records by trace ID.

Any tenant member can submit bounded feedback through
`POST /rag/query/traces/{trace_id}/feedback` with an optional 1-5 rating and
optional comment. Feedback is allowed only while the tenant-scoped trace is
within retention.

### Evaluation And Profile Promotion

Evaluate a candidate profile using labeled fixtures containing expected chunk
and citation IDs plus the expected abstention behavior. The evaluation runner
records retrieval recall, citation correctness and coverage, groundedness,
abstention quality, latency, and failure rate in `rag_evaluation_results`.

An advanced index profile must be activated through
`RagProfilePromotionService`. The service rejects promotion unless the tenant
has a passing labeled result for that profile: full recall, citation
correctness/coverage, groundedness, and abstention quality with zero failure
rate. Do not promote by setting `is_active` directly or by using an
unreviewed evaluation result.
