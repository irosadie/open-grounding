## ADDED Requirements

### Requirement: Derived publication is committed, idempotent, and recoverable
The system SHALL create pending index-generation state and its outbox event in one
PostgreSQL transaction. Event payloads MUST include tenant, resource/version,
generation, idempotency, and trace identities. A derived generation MUST become active
only after validation succeeds.

#### Scenario: Transaction commits a pending generation
- **WHEN** a future ingestion workflow commits a document version and pending index
  generation
- **THEN** a dispatcher can process only the committed outbox event with its stable
  idempotency and trace context

#### Scenario: Derived publication fails
- **WHEN** a vector or object-store side effect fails after the catalog transaction
- **THEN** the active generation is unchanged and the failed generation can be retried
  or reconciled from the catalog

### Requirement: RAG recovery does not depend on derived indexes as authority
The system SHALL document and support PostgreSQL backup/restore, object-store
backup/restore, Qdrant snapshot/restore, and Qdrant rebuild from the PostgreSQL catalog
plus object-store artifacts. Qdrant MUST NOT be the only record of tenant content.

#### Scenario: Qdrant data is lost
- **WHEN** Qdrant storage is restored from an incomplete snapshot or is recreated
- **THEN** operators can reconstruct derived indexes from authoritative catalog and
  object-store data without losing document identity or version lineage

### Requirement: Platform operations propagate trace context
The system SHALL propagate a request or trace ID from FastAPI through catalog records,
outbox events, and future BullMQ jobs. Security-relevant failures and recovery actions
MUST record the associated tenant and trace identity.

#### Scenario: A future platform job fails
- **WHEN** a dispatcher or worker records a platform failure
- **THEN** the failure record includes tenant, job or generation identity, and the
  originating trace ID for operator investigation
