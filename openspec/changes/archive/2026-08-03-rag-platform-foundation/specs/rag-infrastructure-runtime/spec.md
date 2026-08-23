## ADDED Requirements

### Requirement: RAG runtime dependencies are persistent and secure
The system SHALL provide version-pinned, persistent, self-hostable runtime profiles
for Qdrant and an S3-compatible object store. Qdrant MUST use an API key, internal-only
network exposure for production, strict mode, payload indexes for mandatory fields,
and snapshot-capable persistent storage.

#### Scenario: Operator enables the RAG runtime profile
- **WHEN** an operator starts the documented RAG runtime profile with valid settings
- **THEN** Qdrant and the object store are healthy, persistent, and reachable only by
  authorized application services on the configured service network

#### Scenario: Qdrant starts without required protection
- **WHEN** Qdrant is configured without a required API key, persistent storage, or
  strict mode in a production profile
- **THEN** the runtime validation fails before RAG operations are enabled

### Requirement: Existing shared services remain compatible
The system SHALL retain existing PostgreSQL, Redis, and Node BullMQ worker behavior
while adding the RAG runtime profile. The platform MUST NOT require a Python worker or
expose Qdrant or object storage through a public browser-facing port.

#### Scenario: Existing worker starts with RAG profile enabled
- **WHEN** the Node BullMQ worker starts while the RAG runtime profile is enabled
- **THEN** it retains its Redis connection and no RAG dependency is required until a
  RAG job is registered

### Requirement: Runtime readiness is observable without secret disclosure
The system SHALL provide liveness and readiness diagnostics that distinguish
PostgreSQL, Redis, Qdrant, object storage, deployment tenant, and active index-profile
availability. Diagnostics MUST NOT expose credentials, secret values, internal URLs,
or raw provider error payloads.

#### Scenario: An external dependency is unavailable
- **WHEN** Qdrant or object storage is unreachable
- **THEN** readiness reports the affected dependency as unavailable while liveness
  remains suitable for process supervision and no secret is included in the response
