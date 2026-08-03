# rag-knowledge-catalog Specification

## Purpose
TBD - created by archiving change rag-platform-foundation. Update Purpose after archive.
## Requirements
### Requirement: Knowledge lifecycle has an authoritative tenant-scoped catalog
The system SHALL persist tenant-scoped knowledge bases, knowledge sources, documents,
document versions, model profiles, index profiles, index generations, ingestion job
records, and outbox events in PostgreSQL. The catalog MUST remain authoritative for
identity, lifecycle, and audit even when Qdrant or object storage is unavailable.

#### Scenario: Platform initializes a knowledge base
- **WHEN** an authorized tenant-owned knowledge base is created
- **THEN** PostgreSQL records its tenant ownership, lifecycle metadata, and policy
  boundary without requiring a vector or object-store write

### Requirement: Document and index lineage is immutable and versioned
The system SHALL distinguish stable document identity from immutable document versions
and derived index generations. A new profile or reindex attempt MUST create a new
generation and MUST NOT overwrite an active generation in place.

#### Scenario: Reindex is requested for a future document version
- **WHEN** an authorized reindex operation creates a new index generation
- **THEN** the prior active generation remains identifiable until the new generation
  is validated and promoted

### Requirement: Catalog relationships cannot cross tenant boundaries
The system SHALL use required tenant ownership, tenant-local uniqueness, and
tenant-consistent parent-child relationships for catalog records. Repository operations
MUST apply tenant context in the database query or mutation.

#### Scenario: Cross-tenant catalog association is attempted
- **WHEN** a caller attempts to associate an index generation, profile, or document
  version with a record from another tenant
- **THEN** the operation is rejected and no cross-tenant relationship is persisted

