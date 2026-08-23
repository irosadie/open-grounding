## ADDED Requirements

### Requirement: Parse stage processes supported MIME types
The system SHALL extract text content from PDF, Markdown, and plain-text files in the parse stage.

#### Scenario: PDF parsed successfully
- **WHEN** ingestion job reaches parse stage with a PDF file
- **THEN** text is extracted page by page and stored as normalized document elements

#### Scenario: Markdown parsed successfully
- **WHEN** ingestion job reaches parse stage with a Markdown file
- **THEN** text is extracted preserving heading structure

#### Scenario: Unsupported MIME type fails
- **WHEN** ingestion job reaches parse stage with unsupported MIME type
- **THEN** document version moves to FAILED with code UNSUPPORTED_MIME_TYPE

### Requirement: Chunk stage applies active index profile strategy
The system SHALL split parsed text into chunks using the chunking strategy defined in the active IndexProfile.

#### Scenario: Chunks respect token size limits
- **WHEN** text is chunked with chunk_size_tokens=400
- **THEN** no chunk exceeds 400 tokens (measured by the profile's tokenizer)

#### Scenario: Parent-child chunks created
- **WHEN** chunking_strategy is RECURSIVE
- **THEN** each child chunk has a parent_chunk_id reference to its parent chunk

### Requirement: Embed stage uses active index profile
The system SHALL embed chunks using the dense embedding model from the active IndexProfile, with fallback if configured.

#### Scenario: Vectors match declared dimensions
- **WHEN** embedding completes successfully
- **THEN** all vectors have dimension equal to IndexProfile.dimensions

### Requirement: Index stage upserts to Qdrant
The system SHALL upsert chunk vectors with payload to the Qdrant collection defined in the active IndexProfile.

#### Scenario: Vectors upserted with required payload
- **WHEN** index stage completes
- **THEN** each vector in Qdrant has payload fields: tenant_id, knowledge_base_id, document_version_id, chunk_id, is_active=true

### Requirement: Validate stage promotes document to READY
The system SHALL verify vector count matches chunk manifest count before promoting document version to READY.

#### Scenario: Count matches — document becomes READY
- **WHEN** Qdrant vector count equals chunk manifest count
- **THEN** document version lifecycle_state becomes READY

#### Scenario: Count mismatch — document FAILED
- **WHEN** Qdrant vector count does not match chunk manifest count
- **THEN** document version lifecycle_state becomes FAILED with code INDEX_VALIDATION_FAILED
