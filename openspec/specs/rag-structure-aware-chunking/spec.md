# rag-structure-aware-chunking Specification

## Purpose
TBD - created by archiving change rag-ingestion-foundation. Update Purpose after archive.
## Requirements
### Requirement: Default chunks are structure-aware parent-child units
The system SHALL create parent context units and embedded child retrieval units from
canonical elements. Children MUST retain tenant, knowledge base, document version,
parent identity, hierarchy path, page, source offsets, content type, classification,
and ACL metadata.

#### Scenario: Section is chunked for retrieval
- **WHEN** a normalized section is within configured parent and child token budgets
- **THEN** the system creates lineage-preserving parent and child units at section
boundaries without arbitrary global overlap

### Requirement: Chunk identity and token limits are deterministic
The system SHALL calculate chunk sizes using the active embedding tokenizer and assign
deterministic IDs from version, hierarchy, offsets, content type, and chunker version.
The initial preferred child range is 300–500 tokens with a 700-token hard maximum;
overlap is allowed only to split one oversized element.

#### Scenario: Pipeline retries chunking
- **WHEN** the same document version and chunker fingerprint are processed again
- **THEN** the system produces the same chunk identities and does not create duplicate
  child manifests or vector targets

### Requirement: Content boundaries are protected
The system SHALL treat Markdown headings, PDF title/layout elements, paragraphs, lists,
and code blocks as structural boundaries. The initial release MUST not apply narrative
splitting rules to unsupported table, OCR, or code-AST content profiles.

#### Scenario: Markdown contains a heading and code block
- **WHEN** a Markdown source is chunked
- **THEN** the heading hierarchy and code-block boundary are retained in the resulting
  parent-child manifest

