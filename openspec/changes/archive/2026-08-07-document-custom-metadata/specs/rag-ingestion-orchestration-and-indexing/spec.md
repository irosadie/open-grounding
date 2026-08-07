## MODIFIED Requirements

### Requirement: Qdrant publication is generation-safe
The system SHALL upsert deterministic vector points with mandatory indexed payload for
tenant, knowledge base, document/version, chunk/parent, classification, ACL,
generation, and active state. If the source document version carries a non-null
`metadata` field, the system MUST include it in the Qdrant point payload under the
key `metadata` as a flat string key-value object. A pending generation MUST be
validated against its manifest before FastAPI promotes it active.

#### Scenario: Replacement version indexes successfully
- **WHEN** a new document version completes vector upsert and manifest validation
- **THEN** the new generation becomes active and the prior active version remains available until promotion has completed and cleanup grace conditions are met

#### Scenario: Indexing fails after partial upsert
- **WHEN** an indexing stage fails after some points are written
- **THEN** the active generation is unchanged and compensating cleanup or reconciliation can remove only the failed pending generation points

#### Scenario: Version with metadata is indexed
- **WHEN** a document version with a non-null `metadata` field completes the index stage
- **THEN** every Qdrant point for that version includes a `metadata` key in its payload containing the persisted key-value pairs

#### Scenario: Version without metadata is indexed
- **WHEN** a document version with null `metadata` completes the index stage
- **THEN** every Qdrant point for that version is upserted without a `metadata` key in its payload
