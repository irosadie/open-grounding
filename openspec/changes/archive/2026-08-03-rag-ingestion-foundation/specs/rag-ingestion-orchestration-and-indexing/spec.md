## ADDED Requirements

### Requirement: Ingestion runs as checkpointed tenant-scoped stages
The system SHALL execute ingestion through explicit lifecycle stages from receipt to
validation. Every BullMQ job MUST carry tenant, document version, generation, stage,
idempotency, and trace identities. The Node worker MUST use authenticated internal
FastAPI commands for authoritative state changes and MUST NOT write catalog tables
directly.

#### Scenario: Worker claims a parsing stage
- **WHEN** a tenant-scoped BullMQ worker receives a queued parsing job
- **THEN** it validates the job scope, claims the checkpoint through FastAPI, and
  records stage progress and failure state through internal commands

#### Scenario: Worker receives an invalid job scope
- **WHEN** a worker receives a job with missing or mismatched tenant context
- **THEN** it rejects the job without parsing, indexing, or mutating catalog state

### Requirement: Embedding and sparse indexing validate representations
The system SHALL batch dense and sparse representation work within configured token and
item limits. It MUST validate vector dimensions and finite values, use content-addressed
cache where configured, and persist provider usage/latency without storing secrets.

#### Scenario: Provider returns an invalid vector
- **WHEN** an embedding batch contains a dimension mismatch or non-finite value
- **THEN** the affected stage fails without publishing the generation and records a
  recoverable diagnostic

### Requirement: Qdrant publication is generation-safe
The system SHALL upsert deterministic vector points with mandatory indexed payload for
tenant, knowledge base, document/version, chunk/parent, classification, ACL,
generation, and active state. A pending generation MUST be validated against its
manifest before FastAPI promotes it active.

#### Scenario: Replacement version indexes successfully
- **WHEN** a new document version completes vector upsert and manifest validation
- **THEN** the new generation becomes active and the prior active version remains
  available until promotion has completed and cleanup grace conditions are met

#### Scenario: Indexing fails after partial upsert
- **WHEN** an indexing stage fails after some points are written
- **THEN** the active generation is unchanged and compensating cleanup or reconciliation
  can remove only the failed pending generation points
