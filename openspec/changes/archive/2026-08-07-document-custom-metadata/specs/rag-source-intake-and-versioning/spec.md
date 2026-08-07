## MODIFIED Requirements

### Requirement: Supported sources use authorized direct upload
The system SHALL accept only PDF, Markdown, and plain-text source files in the initial
ingestion release. An authorized caller MUST create an intake request before receiving
a short-lived presigned object-store upload target scoped to the active tenant and
knowledge base. The API MUST NOT buffer the source file in application memory.
The intake request MAY include an optional flat `metadata` field (string key-value pairs,
max 20 keys, max 256 chars per key and value) which MUST be persisted on the document version.

#### Scenario: Caller uploads a supported source
- **WHEN** an authorized caller creates and completes an intake request for a supported
  file within configured limits without a `metadata` field
- **THEN** the raw object is stored under the active tenant namespace and the API
  returns an asynchronous ingestion identity

#### Scenario: Caller uploads a supported source with metadata
- **WHEN** an authorized caller creates and completes an intake request for a supported file with a valid `metadata` field
- **THEN** the raw object is stored under the active tenant namespace, metadata is persisted on the document version, and the API returns an asynchronous ingestion identity

#### Scenario: Caller uploads an unsupported source
- **WHEN** a caller requests intake for an unsupported MIME type or file extension
- **THEN** the API rejects the request before issuing an upload target
