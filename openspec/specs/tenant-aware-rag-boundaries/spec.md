# tenant-aware-rag-boundaries Specification

## Purpose
TBD - created by archiving change tenant-ready-single-deployment. Update Purpose after archive.
## Requirements
### Requirement: RAG object storage is tenant-namespaced
The system SHALL store tenant-owned raw files and derived parser artifacts beneath an
object-store key prefix containing the tenant ID. Object access adapters MUST require
tenant context and MUST NOT construct tenant-neutral keys for tenant-owned content.

#### Scenario: Ingestion stores an uploaded document
- **WHEN** a tenant-owned document is accepted for ingestion
- **THEN** its raw object and derived artifacts are stored beneath the active tenant
  namespace

### Requirement: Asynchronous RAG work carries verified tenant context
The system SHALL include tenant ID in each tenant-owned BullMQ job, idempotency key,
and relevant cache key. A worker MUST reject a job whose tenant ID is missing or does
not match the deployment tenant.

#### Scenario: Worker receives a mismatched ingestion job
- **WHEN** a worker receives an ingestion job for a tenant other than the configured
  deployment tenant
- **THEN** the worker does not process the job and records a security-relevant failure

### Requirement: Vector and graph retrieval use mandatory tenant filters
The system SHALL persist tenant ID as indexed Qdrant payload for each tenant-owned
point and MUST apply an identical mandatory tenant filter to vector reads, writes,
scrolls, and deletes. Optional graph projections MUST enforce equivalent tenant
predicates for traversal and results.

#### Scenario: Query retrieves candidate chunks
- **WHEN** a tenant-scoped RAG query is executed
- **THEN** every retrieval adapter returns only candidates with the active tenant ID
  before fusion, reranking, or context construction

#### Scenario: Vector point deletion is requested
- **WHEN** a tenant-owned document version is deleted or reindexed
- **THEN** the vector adapter deletes only points matching both the active tenant ID
  and the document-version identity

### Requirement: Derived-store isolation is testable
The system SHALL provide integration tests that seed at least two tenant identifiers
in a disposable environment and prove that object-key construction, queue processing,
cache lookups, and retrieval filters never return or mutate data from the other
tenant.

#### Scenario: Isolation regression test runs
- **WHEN** the tenant-boundary integration suite runs with two test tenants
- **THEN** each tenant can access only its own seeded derived-store data and all
  attempted cross-tenant operations are rejected or return no data

