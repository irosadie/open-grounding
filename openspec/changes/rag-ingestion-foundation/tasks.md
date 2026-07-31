## 1. Prerequisites, schema, and safe configuration

- [ ] 1.1 Verify `tenant-ready-single-deployment` and `rag-platform-foundation` are implemented, including tenant context, catalog/outbox, object storage, Qdrant, and provider ports.
- [ ] 1.2 Add validated ingestion settings for supported MIME types, limits, quotas, malware-scan mode, parser/model profiles, retry budgets, and feature flags.
- [ ] 1.3 Add additive tenant-scoped schema and Alembic migrations for source/version lifecycle, source objects, parser/normalized/quality artifacts, element manifests, chunk manifests, stage checkpoints, and recovery metadata.
- [ ] 1.4 Add repository protocols and SQLAlchemy implementations with tenant-scoped lineage, idempotency, active-version, retention, and audit constraints.

## 2. Source intake and document lifecycle

- [ ] 2.1 Add Pydantic models and FastAPI routes to create upload intake, issue presigned targets, complete validated uploads, fetch ingestion status, and request deletion using existing response envelopes.
- [ ] 2.2 Implement tenant/knowledge-base authorization, direct object key construction, object HEAD validation, MIME/magic-byte/size/checksum checks, and production scan/quarantine behavior.
- [ ] 2.3 Implement document identity, immutable source versioning, duplicate no-op detection, source/pipeline fingerprints, active/superseded/deleting lifecycle transitions, and audit events.
- [ ] 2.4 Add HTTP-contract, unit, and PostgreSQL/object-store integration tests for supported uploads, rejection/quarantine, duplicate uploads, replacement versions, and tenant isolation.

## 3. Content extraction, quality, and chunk manifests

- [ ] 3.1 Implement provider-neutral parser adapters and test fixtures for digital PDF, Markdown, and TXT that produce ordered canonical document elements.
- [ ] 3.2 Persist raw, parser, normalized, and quality-report artifacts under the tenant object namespace; implement normalization while preserving page, hierarchy, and source offsets.
- [ ] 3.3 Implement configured quality gates, bounded fallback/review states, and tests proving empty or insufficient extraction cannot become ready.
- [ ] 3.4 Implement tokenizer-aware, structure-aware parent-child chunking with deterministic IDs, lineage metadata, section/code boundaries, and manifest persistence.
- [ ] 3.5 Add parser/normalizer/chunker regression fixtures and tests for deterministic reruns, token limits, PDF page lineage, Markdown hierarchy, and content boundary preservation.

## 4. BullMQ orchestration and Qdrant publication

- [ ] 4.1 Add tenant-scoped BullMQ stage job contracts, idempotency keys, trace context, checkpoint claiming, bounded retries/backoff, and dead-letter/recovery handling.
- [ ] 4.2 Add authenticated internal FastAPI ingestion commands for worker claim, progress, artifact/manifest recording, failure reporting, retry, and promotion without direct worker database writes.
- [ ] 4.3 Implement worker stage adapters for parse, normalize, classify, chunk, dense/sparse representation, index, and validation using the configured provider ports.
- [ ] 4.4 Implement bounded embedding batches, content-addressed cache, dimension/finite-vector validation, provider usage/latency capture, and partial-failure recovery.
- [ ] 4.5 Implement deterministic Qdrant upsert, mandatory tenant/ACL/version/generation payload indexes and filters, manifest/vector validation, promotion, grace cleanup, and compensating reconciliation.
- [ ] 4.6 Add disposable end-to-end tests for PDF, Markdown, and TXT through retry, version replacement, pipeline reindex, partial index failure, active-generation promotion, and Qdrant rebuild.

## 5. Operations, documentation, and verification

- [ ] 5.1 Add operator-authorized lifecycle endpoints and use cases for status, safe retry, reindex, soft delete, hard purge, quarantine/review resolution, and bounded recovery actions.
- [ ] 5.2 Add ingestion audit records, trace correlation, and bounded metrics for queue delay, stage duration, failures, bytes, tokens, chunks, vectors, and quality outcomes.
- [ ] 5.3 Document supported formats, upload limits, scanner modes, worker configuration, retention/deletion behavior, retry/reindex, and recovery/rebuild runbooks.
- [ ] 5.4 Regenerate FastAPI OpenAPI and run unit, HTTP-contract, PostgreSQL, object-store, Qdrant, and worker integration suites plus the documented full repository quality gate.
- [ ] 5.5 Record the handoff to `rag-grounded-query` and the deferred connector/OCR/table/code/graph capabilities.
