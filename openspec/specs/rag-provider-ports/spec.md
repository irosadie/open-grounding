# rag-provider-ports Specification

## Purpose
TBD - created by archiving change rag-platform-foundation. Update Purpose after archive.
## Requirements
### Requirement: RAG providers are accessed through tenant-aware ports
The system SHALL define application-owned ports for object storage, vector indexing,
embedding, sparse encoding, reranking, and generation. Tenant-owned adapter operations
MUST require tenant context and MUST NOT expose provider SDK types beyond
infrastructure adapters.

#### Scenario: Application service requests a vector operation
- **WHEN** an application service invokes a vector-index port for tenant-owned data
- **THEN** it supplies tenant context and domain-level parameters without importing a
  Qdrant SDK type

### Requirement: Model and index profiles are immutable and compatible
The system SHALL persist versioned model and index profiles containing provider
references, vector dimensions, distance metric, sparse profile, and collection
identity without storing secrets. An active index generation MUST reference compatible
immutable profiles.

#### Scenario: Operator activates an incompatible profile
- **WHEN** an operator attempts to activate an index profile incompatible with its
  embedding or sparse profile
- **THEN** validation rejects the activation before any derived index is published

### Requirement: Provider secrets remain outside the catalog
The system SHALL load provider credentials only from runtime configuration or a secret
provider. Catalog records, audit events, generated OpenAPI, and diagnostics MUST NOT
contain provider credential values.

#### Scenario: Provider configuration is inspected
- **WHEN** an operator requests diagnostic or profile information
- **THEN** the system returns provider identity and non-secret compatibility metadata
  without returning credential material

