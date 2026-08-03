## ADDED Requirements

### Requirement: Ingestion lifecycle is observable and controllable
The system SHALL expose tenant-authorized status for document versions and ingestion
jobs, including lifecycle state, current stage, attempts, progress, quality outcome,
active generation, and safe recovery action. Status APIs MUST use the existing success
and error envelopes.

#### Scenario: Caller checks an asynchronous ingestion
- **WHEN** an authorized caller requests the status of a pending ingestion
- **THEN** the API returns its tenant-scoped lifecycle state and progress without
  exposing internal credentials or another tenant's metadata

### Requirement: Retry and reindex are explicit and bounded
The system SHALL allow an authorized operator to retry a failed recoverable stage or
create a new generation for a changed pipeline profile. Retries MUST be bounded,
idempotent, and recorded; a reindex MUST NOT mutate the prior generation in place.

#### Scenario: Operator retries a recoverable failure
- **WHEN** an operator retries a document version with a recoverable failed stage
- **THEN** the system resumes from the valid checkpoint using the original immutable
  version and records the new attempt and trace identity

### Requirement: Ingestion operations are auditable and measurable
The system SHALL record tenant, actor when available, document/version, stage,
generation, idempotency, trace, outcome, and failure classification for security and
recovery events. It MUST emit bounded operational metrics for queue latency, stage
duration, failure count, bytes, tokens, chunks, and vectors.

#### Scenario: Ingestion stage fails
- **WHEN** a parser, scanner, embedding, or vector stage fails
- **THEN** an audit/recovery record and bounded metric are emitted with tenant and
  trace identity, without raw source content or provider credentials
