## Context

`tenant-ready-single-deployment` provides the tenant boundary and
`rag-platform-foundation` provides the catalog, object store, Qdrant, provider ports,
outbox, and generation model. This change makes the first corpus usable: PDF,
Markdown, and TXT files enter through a durable, versioned, tenant-scoped pipeline and
become validated dense/sparse Qdrant projections.

The API remains FastAPI. The existing Node BullMQ worker remains the queue orchestrator
and calls internal, authenticated FastAPI ingestion commands for authoritative state
transitions; it must not update catalog tables directly. Parser, scanner, embedding,
and vector implementations remain behind the RAG provider ports. This avoids
duplicating Python domain rules in Node while retaining the existing worker runtime.

## Goals / Non-Goals

**Goals:**

- Safely accept PDF, Markdown, and TXT through two-phase, presigned uploads.
- Preserve document identity, immutable source versions, artifacts, policy metadata,
  deterministic chunks, active generation, and audit lineage.
- Run parsing, normalization, chunking, embedding, indexing, and validation
  asynchronously with checkpointed retry and idempotency.
- Produce dense and sparse Qdrant representations under mandatory tenant, knowledge
  base, ACL, version, generation, and active-state filters.
- Permit reindex, retry, soft delete, hard purge, and rebuild without retrieval gaps.

**Non-Goals:**

- DOCX/PPTX/XLSX, images, scanned OCR, tables, web/API/database connectors, email,
  code repositories, audio/video, or CDC.
- Cross-tenant shared SaaS, graph projection, multi-vector retrieval, semantic/late
  chunking, hybrid query, reranking, citations, or answer generation.
- A browser ingestion interface, quota/billing UI, or an unrestricted file manager.
- Migrating the Node BullMQ worker to Python or adding direct database access to it.

## Decisions

### Intake is a two-phase object-store protocol

An authorized caller first creates an ingestion request with knowledge-base context and
source metadata. FastAPI creates a pending document version and returns a short-lived
presigned upload target. The client uploads directly to an object-store key scoped as
`tenants/{tenant_id}/knowledge-bases/{knowledge_base_id}/documents/{document_id}/...`.
Completion calls FastAPI, which HEADs the object and verifies size, checksum, MIME,
magic bytes, and declared source metadata before enqueueing work.

The API never holds the source file in process memory. Only PDF, Markdown, and TXT are
accepted in v1, with configured size limits and explicit tenant/knowledge-base
authorization. Production requires a configured malware-scan adapter; a scan failure
or unavailable scanner quarantines the version rather than allowing it to become
ready. Development may use an explicitly labelled no-scan adapter.

Alternatives considered:

- Multipart upload through FastAPI exhausts worker/API memory and complicates retry.
- Trusting extensions or client MIME allows mismatched content.
- Accepting all formats now creates an untestable parser/OCR surface before the core
  lifecycle is reliable.

### Identity, source revision, and pipeline revision are separate

`document_id` is a stable logical identity. `document_version_id` represents immutable
source bytes. `source_revision` captures an upload revision; `content_checksum` is the
SHA-256 of raw bytes. `pipeline_fingerprint` identifies the parser, normalizer,
chunker, embedding, sparse encoder, and configuration versions used for a generation.

Within a tenant and knowledge base, an equal checksum plus equal pipeline fingerprint
is a no-op. Changed bytes create a new document version. Changed pipeline configuration
creates a new index generation for the same source version. Stage idempotency keys are
derived from tenant, document version, generation, stage, and fingerprint. Chunk IDs
are deterministic hashes of version, hierarchy path, offsets, chunker version, and
content type.

### Parser output is canonical, persisted, and quality-gated

The parser adapter emits ordered `DocumentElement` records, not a flattened string:

```text
id, type, text, page, hierarchy_path, source_offsets,
structured_payload, extraction_confidence
```

PDF elements retain page and reading order; Markdown preserves headings and code
blocks; TXT becomes narrative elements. Normalization repairs Unicode, whitespace,
hyphenation, source metadata, and obvious boilerplate while preserving source offsets.
The raw source, parser output, normalized artifact, and quality report are stored in
the tenant object namespace so a later chunker/profile change does not require parsing
again.

The quality gate measures extraction coverage, invalid-character ratio, empty-element
ratio, page coverage for PDF, and parser confidence where available. A failed gate
goes to `NEEDS_REVIEW` or a bounded parser fallback; empty or low-quality content can
never be silently promoted to `READY`.

### Chunking is structure-aware parent-child by default

Parents preserve section/page-level context at roughly 1,000–2,000 embedding tokens.
Children are retrieval units targeting 300–500 tokens with a 700-token hard maximum.
Overlap is allowed only when a single oversized element is split; ordinary section
boundaries have no global overlap. Children retain parent ID, hierarchy path, page,
offsets, content type, and policy metadata.

Markdown headings, PDF titles/layout elements, paragraphs, lists, and code blocks are
hard boundaries. Initial v1 does not claim table, OCR, or code-AST strategies; those
become later parser/content-profile changes. Token counting uses the active embedding
profile tokenizer, not character count.

### Node BullMQ orchestrates; FastAPI owns lifecycle changes

The pipeline stages are `RECEIVED → STORED → QUEUED → PARSING → NORMALIZING →
CLASSIFYING → CHUNKING → EMBEDDING → INDEXING → VALIDATING → READY`, with explicit
`REJECTED`, `QUARANTINED`, `NEEDS_REVIEW`, `FAILED`, `SUPERSEDED`, `DELETING`, and
`DELETED` states. BullMQ jobs contain only tenant-scoped identifiers, generation,
stage, idempotency key, and trace context. The worker gets a short-lived internal
capability to claim/checkpoint a job and invokes internal FastAPI commands to record
state, artifacts, manifests, and failures.

Each stage is retryable from its checkpoint with bounded attempts and exponential
backoff. Partial provider failures are handled per batch. The worker never accepts an
unscoped job or modifies PostgreSQL catalog records directly. Future worker migration
is possible because the commands and provider ports, not BullMQ implementation, own
the pipeline contract.

### Index promotion is a saga with zero retrieval gap

Embedding batches are cached by content checksum plus embedding profile, validated for
dimension/NaN, and coupled with sparse representation from the active sparse profile.
Qdrant points use deterministic IDs and carry indexed payload fields for tenant,
knowledge base, document/version, parent/child, classification, ACL, generation, and
`is_active`.

A new generation is written as pending through the existing outbox boundary. The
worker upserts vectors with the generation ID, then validates manifest count, vector
count, payload filters, and sample reads. Only then does FastAPI promote the generation
and mark the new version ready. The previous active version/generation remains
retrievable until promotion and a grace-period cleanup complete. Failed vectors are
removed by compensating cleanup or a later reconciliation run.

### Delete and recovery are stateful

Source deletion first prevents new retrieval by marking the active version deleted or
superseded and removing it from active filters. Asynchronous purge removes Qdrant
points, artifacts, and catalog data according to retention policy. Reindex creates a
new generation; it does not mutate existing vectors. Operators can retry a failed stage
only with the original immutable version and a recorded reason.

## Risks / Trade-offs

- [Parser behavior varies by PDF quality] → Restrict v1 formats, persist artifacts,
  expose quality state, and add a bounded fallback/review path.
- [Node worker and Python API add an internal protocol] → Keep the protocol narrow,
  authenticated, idempotent, traceable, and covered by contract tests.
- [Large files or embeddings exhaust resources] → Use presigned upload, configured
  quotas/limits, bounded batches, token-aware scheduling, and backpressure.
- [Retries create duplicate vectors or jobs] → Use stable stage keys, deterministic
  point IDs, idempotent upserts, and generation-aware cleanup.
- [New versions could create stale or missing answers] → Keep prior active generation
  until validated promotion; queries later filter `is_active` and active generation.
- [Malware scanning may not be available locally] → Require production scanning and
  mark the development bypass explicitly in diagnostics/audit.

## Migration Plan

1. Complete tenant and RAG platform foundation changes, including runtime profiles and
   catalog/outbox contracts.
2. Add additive source/version, element/artifact, chunk-manifest, stage checkpoint,
   and quality-report schema without altering existing catalog records.
3. Introduce intake routes and object-store completion validation behind feature flags.
4. Register Node BullMQ stages and internal FastAPI commands; run only with supported
   test providers in a disposable environment.
5. Validate a PDF, Markdown, and TXT corpus through retries, replacement, reindex,
   soft delete, hard purge, and Qdrant rebuild drills.
6. Enable the feature for operators after metrics, audit, limits, and recovery runbooks
   are verified.

Rollback disables new intake and queue registration. Existing raw files, catalog
records, parser artifacts, and pending generations are retained for recovery; Qdrant
projections are cleaned or rebuilt through the catalog rather than treated as rollback
authority.

## Open Questions

- Which parser adapter is officially supported first for digital PDFs, and what
  production malware scanner is acceptable for the open-source profile?
- What maximum source size, pages, tokens, batch size, and concurrent jobs match the
  target hardware profile?
- Which dense and sparse model profiles become the first supported local defaults?
- Should `NEEDS_REVIEW` be operator-only in v1 or exposed through a future UI/API?
