# rag-source-intake-and-versioning Specification

## Purpose
TBD - created by archiving change rag-ingestion-foundation. Update Purpose after archive.
## Requirements
### Requirement: Supported sources use authorized direct upload
The system SHALL accept only PDF, Markdown, and plain-text source files in the initial
ingestion release. An authorized caller MUST create an intake request before receiving
a short-lived presigned object-store upload target scoped to the active tenant and
knowledge base. The API MUST NOT buffer the source file in application memory.

#### Scenario: Caller uploads a supported source
- **WHEN** an authorized caller creates and completes an intake request for a supported
  file within configured limits
- **THEN** the raw object is stored under the active tenant namespace and the API
  returns an asynchronous ingestion identity

#### Scenario: Caller uploads an unsupported source
- **WHEN** a caller requests intake for an unsupported MIME type or file extension
- **THEN** the API rejects the request before issuing an upload target

### Requirement: Source completion is validated and quarantined safely
The system SHALL validate object existence, size, checksum, MIME type, magic bytes,
knowledge-base authorization, and malware-scan status after upload completion. The
system MUST quarantine or reject a failed validation and MUST NOT enqueue it for
indexing.

#### Scenario: Uploaded object fails validation
- **WHEN** the completed object checksum, MIME, magic bytes, size, or malware scan is
  invalid or unavailable for a production profile
- **THEN** the version enters a rejected or quarantined state with an audit record and
  no parser or embedding job is created

### Requirement: Source versions and idempotency preserve lineage
The system SHALL keep stable document identity separate from immutable source versions.
Equal content checksum and pipeline fingerprint within the same tenant and knowledge
base MUST result in a no-op; changed bytes MUST create a new document version.

#### Scenario: Caller repeats an identical upload
- **WHEN** a supported source has the same checksum and active pipeline fingerprint as
  an existing version in the same knowledge base
- **THEN** the system returns the existing ingestion result and does not create duplicate
  document versions, jobs, or vectors

### Requirement: Source deletion is safe and asynchronous
The system SHALL support soft deletion that immediately removes a source version from
future active retrieval, followed by retention-aware asynchronous purge of derived
indexes and artifacts.

#### Scenario: Caller deletes an active document
- **WHEN** an authorized caller requests deletion of an active document
- **THEN** the version is removed from active retrieval before asynchronous projection
  cleanup and the deletion lifecycle is auditable

