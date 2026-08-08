# kb-ingestion-config Specification

## Purpose
Per-Knowledge-Base ingestion configuration that controls quality gate thresholds and
auto-review behavior. Allows operators to tune extraction quality requirements and
enforce mandatory human review for every document without modifying source code.

## Requirements

### Requirement: Each knowledge base has exactly one ingestion config
The system SHALL maintain exactly one `IngestionConfig` record per knowledge base.
If no config has been explicitly created, the system MUST return and apply default
values equivalent to the constructor defaults of `QualityGate`.

#### Scenario: KB has no explicit ingestion config
- **WHEN** the ingestion pipeline reads config for a KB that has no `IngestionConfig` record
- **THEN** the system applies default thresholds: `min_text_coverage=0.3`,
  `max_invalid_char_ratio=0.1`, `min_aggregate_confidence=0.5`,
  `min_page_coverage=0.5`, `auto_review=false`

### Requirement: Ingestion config is readable and writable via API
The system SHALL expose GET and PUT endpoints for ingestion config scoped to a
knowledge base. GET MUST return current config or defaults. PUT MUST validate all
threshold values are within bounds and persist atomically (upsert).

#### Scenario: Operator updates quality gate thresholds
- **WHEN** an authorized operator sends a PUT to `/rag/knowledge-bases/{kb_id}/ingestion-config`
  with valid threshold values
- **THEN** the system persists the new config and subsequent ingestion jobs for that KB
  use the updated thresholds

#### Scenario: Operator submits out-of-range threshold
- **WHEN** a PUT request contains a threshold value outside its valid range
  (e.g. `min_text_coverage=1.5`)
- **THEN** the API returns 422 with a validation error and no config is persisted

### Requirement: Quality gate evaluates invalid character ratio
The system SHALL check `max_invalid_char_ratio` in `QualityGate.evaluate()`.
If the ratio of invalid characters across all element text exceeds the configured
maximum, the document version MUST be routed to `NEEDS_REVIEW`.

#### Scenario: OCR output contains high invalid character ratio
- **WHEN** parsed elements contain an invalid character ratio above `max_invalid_char_ratio`
- **THEN** the quality gate returns `NEEDS_REVIEW` regardless of text coverage or confidence

### Requirement: Auto-review flag forces all documents to NEEDS_REVIEW
When `auto_review` is `false` (default), the quality gate decides routing as normal.
When `auto_review` is `true`, the system SHALL route ALL document versions to
`NEEDS_REVIEW` after parse and normalize, regardless of quality gate outcome.
The quality evidence MUST still be computed and persisted.

#### Scenario: Auto-review is enabled and a high-quality document is parsed
- **WHEN** `auto_review=true` on a KB and a document passes all quality thresholds
- **THEN** the document is still routed to `NEEDS_REVIEW` and quality evidence is recorded

#### Scenario: Auto-review is disabled and a document passes quality gate
- **WHEN** `auto_review=false` on a KB and a document passes all quality thresholds
- **THEN** the document continues automatically to chunking without human intervention

### Requirement: Config is scoped to the owning tenant
The system SHALL reject any attempt to read or write ingestion config for a KB that
does not belong to the requesting tenant. Repository operations MUST include tenant
context in all queries.

#### Scenario: Cross-tenant config access is attempted
- **WHEN** a caller attempts to GET or PUT ingestion config for a KB owned by another tenant
- **THEN** the API returns 404 (not found, not forbidden, to avoid enumeration)
