## ADDED Requirements

### Requirement: Full cascade delete on document version deletion
When a document version is deleted, the system SHALL remove all associated data in the correct order: answer evidence nullification, Qdrant vector deletion, S3 raw file deletion, parsed text nullification, index generation status update, document version hard-delete, and document soft-delete if all versions are gone.

#### Scenario: Cascade delete completes fully
- **WHEN** a delete job is processed for a `DELETING` document version
- **THEN** Qdrant vectors filtered by `document_version_id` are deleted, the raw S3 object at `object_key_raw` is deleted, `parsed_text` is set to null, `rag_index_generations` for the version transition to `DELETED`, the `rag_document_versions` row transitions to `DELETED`, and if no other versions exist for the parent document the `rag_documents` row is soft-deleted

#### Scenario: Answer evidence RESTRICT FK handled before hard-delete
- **WHEN** `rag_answer_evidence` rows reference the version being deleted
- **THEN** those rows are soft-deleted (or `document_version_id` nulled) before the version row is hard-deleted, preventing FK constraint violation

#### Scenario: Qdrant vectors removed
- **WHEN** the delete stage runs for a version with indexed vectors
- **THEN** `VectorStoreAdapter.delete_points` is called with `tenant_id` and `document_version_id` filter, and all matching points are removed from the collection

#### Scenario: S3 raw file removed
- **WHEN** the delete stage runs and `object_key_raw` is set on the version
- **THEN** `ObjectStoreAdapter.delete_object` is called with the object key, removing the file from MinIO/S3

#### Scenario: S3 file not found — non-fatal
- **WHEN** `delete_object` raises a not-found error (e.g. file already removed)
- **THEN** the delete stage logs a warning and continues — it SHALL NOT fail the job

#### Scenario: Delete job for non-DELETING version is a no-op
- **WHEN** a delete job is received for a version not in `DELETING` state
- **THEN** the job completes without performing any deletions and logs a warning

### Requirement: ObjectStoreAdapter concrete delete_object implementation
The `S3ObjectStoreAdapter` (or equivalent concrete class) SHALL implement `delete_object(object_key: str)` using `aioboto3` `delete_object` API, consistent with the existing `put_object` and `get_object` patterns.

#### Scenario: Object deleted from MinIO
- **WHEN** `delete_object` is called with a valid key
- **THEN** the object is removed from the configured bucket via `s3.delete_object(Bucket=bucket, Key=key)`

#### Scenario: Object not found is non-fatal
- **WHEN** `delete_object` is called with a key that does not exist
- **THEN** the adapter logs a warning and returns without raising
