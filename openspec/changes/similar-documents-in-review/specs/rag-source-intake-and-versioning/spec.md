## ADDED Requirements

### Requirement: Review exposes related indexed versions without changing lifecycle
The ingestion API SHALL allow an operator to request related indexed document versions
for a source under review. This read-only operation MUST NOT approve, reject, mutate the
parsed text, create a new version, or alter the source lifecycle state.

#### Scenario: Similarity is requested while a source needs review
- **WHEN** an authorized operator opens the review surface for a document version
- **THEN** the API returns related indexed versions from the same knowledge base while
  leaving the reviewed version in its current lifecycle state

#### Scenario: Similarity lookup has no usable source text
- **WHEN** the reviewed version has no parsed text available
- **THEN** the API returns an empty related-document list and the review actions remain
  available
