## 1. Backend — Delete Worker Stage

- [ ] 1.1 Find the concrete object store adapter file and implement `delete_object(object_key: str) -> None` using `aioboto3` `delete_object` — non-fatal on not-found (log warning, return)
- [ ] 1.2 Create `apps/api/app/workers/stages/delete.py` — `delete_document_version()` async function with full cascade: null `rag_answer_evidence.document_version_id`, delete Qdrant vectors, delete S3 raw file, null `parsed_text`, transition `rag_index_generations` to `DELETED`, hard-delete `rag_document_versions` row, soft-delete `rag_documents` if no versions remain
- [ ] 1.3 Verify `VectorStoreAdapter.delete_points` in `apps/api/app/infrastructure/qdrant.py` — confirm it accepts `document_version_id` filter and works correctly; use it in the delete stage
- [ ] 1.4 In `apps/api/app/application/ingestion_intake_service.py` `soft_delete` — after setting state to `DELETING`, enqueue a job to `ingestion.delete` BullMQ queue with `{"documentVersionId": ..., "tenantId": ...}`
- [ ] 1.5 In `apps/api/app/workers/ingestion_worker.py` — register `handle_delete` handler and `ingestion.delete` BullMQ Worker with concurrency 2 and standard retry opts; add `QUEUE_DELETE = "ingestion.delete"` constant

## 2. Backend — Answer Evidence FK Handling

- [ ] 2.1 In the delete stage, before hard-deleting the version row, execute `UPDATE rag_answer_evidence SET document_version_id = NULL WHERE document_version_id = $version_id` to unblock the RESTRICT FK constraint
- [ ] 2.2 Verify `rag_answer_evidence` table name and column name by checking the migration file — confirm the FK column is `document_version_id`

## 3. Frontend — Document List Delete

- [ ] 3.1 In `apps/web/app/console/document/ingestion-content.tsx` — add per-row delete button visible only for terminal states (`READY`, `FAILED`, `NEEDS_REVIEW`); add confirm dialog state per row
- [ ] 3.2 Wire delete button to existing `useRagIngestionDelete` hook (already exists in `use-delete-version.ts`) — on success invalidate document list query
- [ ] 3.3 Update lifecycle badge map in `ingestion-content.tsx` — add `DELETING` ("Deleting", gray), `DELETED` ("Deleted", muted gray + row dimmed), `NEEDS_REVIEW` ("Needs Review", amber), `SUPERSEDED` ("Superseded", gray), `FAILED` ("Failed", red)

## 4. Verification

- [ ] 4.1 Upload a test document, let it reach `READY`, then call `DELETE /rag/ingestion/{version_id}` — confirm state transitions to `DELETING` and `ingestion.delete` job is enqueued
- [ ] 4.2 After worker processes the job — confirm Qdrant collection has no points with `document_version_id` filter, S3 object is gone, DB version row is `DELETED` or absent
- [ ] 4.3 Confirm `rag_answer_evidence` rows referencing the version have `document_version_id = NULL` after delete
- [ ] 4.4 Delete button visible in UI for `READY` document, triggers confirm dialog, calls API on confirm
- [ ] 4.5 Delete a version that has no S3 object (simulate by removing the key) — confirm worker completes without error
