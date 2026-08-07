# Spec: parsed-text-persistence

## Overview

Persist extracted text from the parse stage to `rag_document_versions.parsed_text`, gate the pipeline at `NEEDS_REVIEW`, and expose four HTTP endpoints for human review before chunking proceeds.

---

## ADDED Requirements

### Requirement: persist-parsed-text

After the parse stage successfully extracts text from a document, the system SHALL persist the extracted text to the `parsed_text` column of `rag_document_versions` before advancing the lifecycle state. The text MUST be written in the same logical operation as the state transition to `NEEDS_REVIEW` so no partial state can result from a crash between the two.

#### Scenario: text is persisted on successful parse

Given a document version in `PARSING` state  
When `parse_document()` completes extraction successfully  
Then `rag_document_versions.parsed_text` SHALL contain the extracted text  
And `rag_document_versions.lifecycle_state` SHALL be `NEEDS_REVIEW`  
And the pipeline SHALL NOT advance to `NORMALIZING` or `CHUNKING` automatically

#### Scenario: parse failure leaves text null

Given a document version in `PARSING` state  
When extraction raises an exception  
Then `rag_document_versions.parsed_text` SHALL remain `NULL`  
And `rag_document_versions.lifecycle_state` SHALL be set to `FAILED`

#### Scenario: parsed text survives worker restart

Given a document version with `lifecycle_state = NEEDS_REVIEW` and a non-null `parsed_text`  
When the worker process restarts  
Then `GET /rag/ingestion/{version_id}/parsed-text` SHALL still return the same text  
And the lifecycle state SHALL still be `NEEDS_REVIEW`

---

### Requirement: pipeline-gate-at-needs-review

The pipeline SHALL stop at `NEEDS_REVIEW` after parse completes. Chunking MUST NOT be enqueued or started until an explicit `POST .../approve` call is received. No automatic timer or retry mechanism SHALL bypass this gate.

#### Scenario: pipeline halts at NEEDS_REVIEW

Given a document version that has just been parsed successfully  
When the parse stage function returns  
Then the lifecycle state SHALL be `NEEDS_REVIEW`  
And no chunking job SHALL be enqueued  
And no further pipeline stage SHALL execute

#### Scenario: approve transitions to chunking

Given a document version with `lifecycle_state = NEEDS_REVIEW`  
When `POST /rag/ingestion/{version_id}/approve` is called by an authenticated tenant user  
Then the lifecycle state SHALL transition to `NORMALIZING`  
And the chunking pipeline SHALL be enqueued  
And the response SHALL include `lifecycleState: "NORMALIZING"`

#### Scenario: reject terminates the pipeline

Given a document version with `lifecycle_state = NEEDS_REVIEW`  
When `POST /rag/ingestion/{version_id}/reject` is called  
Then the lifecycle state SHALL be set to `FAILED`  
And no further pipeline stage SHALL execute  
And the response SHALL include `lifecycleState: "FAILED"`

---

### Requirement: get-parsed-text-endpoint

The system SHALL expose `GET /rag/ingestion/{version_id}/parsed-text` that returns the persisted parsed text for a document version scoped to the authenticated tenant.

#### Scenario: returns parsed text for NEEDS_REVIEW version

Given a document version with `lifecycle_state = NEEDS_REVIEW` and non-null `parsed_text`  
When `GET /rag/ingestion/{version_id}/parsed-text` is called by a user in the same tenant  
Then the response SHALL have HTTP 200  
And `data.parsedText` SHALL equal the persisted text  
And `data.lifecycleState` SHALL be `"NEEDS_REVIEW"`

#### Scenario: returns parsed text for any lifecycle state

Given a document version with non-null `parsed_text` in any lifecycle state  
When `GET /rag/ingestion/{version_id}/parsed-text` is called  
Then the response SHALL return the stored text regardless of current state

#### Scenario: 404 for unknown version

Given a version_id that does not exist in the tenant  
When `GET /rag/ingestion/{version_id}/parsed-text` is called  
Then the response SHALL have HTTP 404

#### Scenario: 404 for cross-tenant version

Given a version_id that belongs to a different tenant  
When `GET /rag/ingestion/{version_id}/parsed-text` is called  
Then the response SHALL have HTTP 404  
And no text or state information SHALL be disclosed

#### Scenario: null parsed text returns empty string

Given a document version where `parsed_text IS NULL`  
When `GET /rag/ingestion/{version_id}/parsed-text` is called  
Then `data.parsedText` SHALL be `null`

---

### Requirement: patch-parsed-text-endpoint

The system SHALL expose `PATCH /rag/ingestion/{version_id}/parsed-text` that allows an operator to replace the stored parsed text with a corrected version. This endpoint SHALL only succeed when the version is in `NEEDS_REVIEW` state. The corrected text MUST be what is used for chunking if the version is subsequently approved.

#### Scenario: operator submits corrected text

Given a document version with `lifecycle_state = NEEDS_REVIEW`  
When `PATCH /rag/ingestion/{version_id}/parsed-text` is called with `{"text": "<corrected>"}`  
Then `rag_document_versions.parsed_text` SHALL be updated to the corrected text  
And `lifecycle_state` SHALL remain `NEEDS_REVIEW`  
And the response SHALL have HTTP 200 with `data.parsedText` equal to the corrected text

#### Scenario: corrected text is used on approval

Given a document version in `NEEDS_REVIEW` whose `parsed_text` was updated via PATCH  
When `POST /rag/ingestion/{version_id}/approve` is called  
Then the chunking pipeline SHALL use the corrected text, not the original extraction

#### Scenario: PATCH rejected for non-NEEDS_REVIEW state

Given a document version with `lifecycle_state != NEEDS_REVIEW` (e.g. `READY`, `FAILED`)  
When `PATCH /rag/ingestion/{version_id}/parsed-text` is called  
Then the response SHALL have HTTP 409  
And `parsed_text` SHALL remain unchanged

#### Scenario: PATCH with empty text is rejected

Given a document version with `lifecycle_state = NEEDS_REVIEW`  
When `PATCH /rag/ingestion/{version_id}/parsed-text` is called with an empty string  
Then the response SHALL have HTTP 422

#### Scenario: 404 for unknown or cross-tenant version

Given a version_id that does not exist or belongs to a different tenant  
When `PATCH /rag/ingestion/{version_id}/parsed-text` is called  
Then the response SHALL have HTTP 404

---

### Requirement: approve-endpoint

The system SHALL expose `POST /rag/ingestion/{version_id}/approve` that transitions a `NEEDS_REVIEW` document version to `NORMALIZING` and enqueues the chunking pipeline.

#### Scenario: approve succeeds for NEEDS_REVIEW

Given a document version with `lifecycle_state = NEEDS_REVIEW`  
When `POST /rag/ingestion/{version_id}/approve` is called  
Then `lifecycle_state` SHALL transition to `NORMALIZING`  
And the chunking job SHALL be enqueued  
And the response SHALL have HTTP 200 with `data.lifecycleState = "NORMALIZING"` and `data.enqueued = true`

#### Scenario: approve is idempotent-safe for non-NEEDS_REVIEW

Given a document version with `lifecycle_state != NEEDS_REVIEW`  
When `POST /rag/ingestion/{version_id}/approve` is called  
Then the response SHALL have HTTP 409  
And no chunking job SHALL be enqueued

#### Scenario: 404 for unknown or cross-tenant version on approve

Given a version_id that does not exist or belongs to another tenant  
When `POST /rag/ingestion/{version_id}/approve` is called  
Then the response SHALL have HTTP 404

---

### Requirement: reject-endpoint

The system SHALL expose `POST /rag/ingestion/{version_id}/reject` that transitions a `NEEDS_REVIEW` document version to `FAILED` and halts the pipeline permanently.

#### Scenario: reject succeeds for NEEDS_REVIEW

Given a document version with `lifecycle_state = NEEDS_REVIEW`  
When `POST /rag/ingestion/{version_id}/reject` is called  
Then `lifecycle_state` SHALL be set to `FAILED`  
And no further pipeline stage SHALL be enqueued  
And the response SHALL have HTTP 200 with `data.lifecycleState = "FAILED"`

#### Scenario: reject fails for non-NEEDS_REVIEW state

Given a document version with `lifecycle_state != NEEDS_REVIEW`  
When `POST /rag/ingestion/{version_id}/reject` is called  
Then the response SHALL have HTTP 409  
And `lifecycle_state` SHALL remain unchanged

#### Scenario: 404 for unknown or cross-tenant version on reject

Given a version_id that does not exist or belongs to another tenant  
When `POST /rag/ingestion/{version_id}/reject` is called  
Then the response SHALL have HTTP 404

---

### Requirement: domain-entity-update

The `DocumentVersion` domain entity SHALL carry a `parsed_text: str | None` field so application and infrastructure layers can pass parsed text without accessing the ORM record directly.

#### Scenario: entity includes parsed_text

Given a `DocumentVersionRecord` row with a non-null `parsed_text`  
When the record is mapped to a `DocumentVersion` domain entity  
Then `entity.parsed_text` SHALL equal the stored text

#### Scenario: entity parsed_text is None when column is NULL

Given a `DocumentVersionRecord` row where `parsed_text IS NULL`  
When the record is mapped to a `DocumentVersion` domain entity  
Then `entity.parsed_text` SHALL be `None`

---

### Requirement: alembic-migration

An Alembic migration SHALL add the `parsed_text TEXT` column as nullable to `rag_document_versions`. The migration MUST be reversible (downgrade removes the column).

#### Scenario: migration adds column

Given the current schema without `parsed_text`  
When the migration is applied  
Then `rag_document_versions` SHALL have a nullable `TEXT` column named `parsed_text`  
And all existing rows SHALL have `parsed_text = NULL`

#### Scenario: migration is reversible

Given the schema with `parsed_text` applied  
When the migration downgrade is run  
Then the `parsed_text` column SHALL be removed from `rag_document_versions`
