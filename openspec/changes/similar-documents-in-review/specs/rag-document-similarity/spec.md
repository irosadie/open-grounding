## Purpose

Provides a safe, read-only semantic comparison for documents under review so operators
can identify related indexed sources in the same knowledge base before approving them.

## ADDED Requirements

### Requirement: Similarity lookup is tenant and knowledge-base scoped
The system SHALL provide an authenticated similarity lookup for a document version that
searches only authorized, actively indexed content from the same knowledge base. The
current document version MUST be excluded from the results, and the lookup MUST NOT
return content from another tenant, knowledge base, inactive generation, or unauthorized
classification/ACL scope.

#### Scenario: Review document has related indexed sources
- **WHEN** an authorized operator requests similar documents for a document version with
  parsed text and an active index in its knowledge base
- **THEN** the system returns a bounded list of different document versions from that
  knowledge base, ordered by semantic similarity and scoped by the normal retrieval policy

#### Scenario: No indexed sources are available
- **WHEN** the document has no parsed text or its knowledge base has no active indexed
  generations
- **THEN** the system returns an empty result list without creating an index, persisting
  a similarity record, or failing the document review page

### Requirement: Similarity results expose safe source context
Each result SHALL include stable document and version identifiers, a display title, the
indexed document lifecycle state, a bounded text preview, and a similarity score suitable
for sorting and display. The API MUST cap the requested result count and MUST return a
tenant-safe not-found error when the source version is not accessible.

#### Scenario: Operator opens similarity results
- **WHEN** the lookup returns matching indexed sources
- **THEN** each result contains enough metadata for the console to display the match and
  link to the authorized document version without exposing raw vectors or hidden prompts

#### Scenario: Unknown or cross-tenant version is requested
- **WHEN** an operator requests similarity for a version that does not belong to the
  active tenant
- **THEN** the API returns the existing not-found error envelope and no similarity search
  is executed
