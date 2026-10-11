## 1. Backend — Delete Worker Stage

- [x] 1.1 Find the concrete object store adapter file and implement `delete_object(object_key: str) -> None` using `aioboto3` `delete_object` — non-fatal on not-found (log warning, return)
- [x] 1.2 Create `apps/api/app/workers/stages/delete.py` — `delete_document_version()` async function with full cascade: null answer-trace source references, delete Qdrant vectors, delete S3 raw file, null `parsed_text`, transition `rag_index_generations` to `DELETED`, hard-delete `rag_document_versions` row, soft-delete `rag_documents` if no versions remain
- [x] 1.3 Verify `VectorStoreAdapter.delete_points` in `apps/api/app/infrastructure/qdrant.py` — confirm it accepts `document_version_id` filter and works correctly; use it in the delete stage
- [x] 1.4 In `apps/api/app/application/ingestion_intake_service.py` `soft_delete` — after setting state to `DELETING`, enqueue a job to `ingestion.delete` BullMQ queue with `{"documentVersionId": ..., "tenantId": ...}`
- [x] 1.5 In `apps/api/app/workers/ingestion_worker.py` — register `handle_delete` handler and `ingestion.delete` BullMQ Worker with concurrency 2 and standard retry opts; add `QUEUE_DELETE = "ingestion.delete"` constant

## 2. Backend — Answer Evidence FK Handling

- [x] 2.1 In the delete stage, before hard-deleting the version row, null answer citation source references to unblock the RESTRICT FK constraints
- [x] 2.2 Verify the migration: this repository names the table `rag_answer_citations` (not `rag_answer_evidence`) and its FK column is `document_version_id`; selected evidence chunk references are also nulled before chunk cascade

## 3. Frontend — Document List Delete

- [x] 3.1 In `apps/web/app/console/document/ingestion-content.tsx` — add per-row delete button visible only for terminal states (`READY`, `FAILED`, `NEEDS_REVIEW`); add confirm dialog state per row
- [x] 3.2 Wire delete button to existing `useRagIngestionDelete` hook (already exists in `use-delete-version.ts`) — on success invalidate document list query
- [x] 3.3 Update lifecycle badge map in `ingestion-content.tsx` — add `DELETING` ("Deleting", gray), `DELETED` ("Deleted", muted gray + row dimmed), `NEEDS_REVIEW` ("Needs Review", amber), `SUPERSEDED` ("Superseded", gray), `FAILED` ("Failed", red)

## 4. Verification

- [ ] 4.1 Upload a test document, let it reach `READY`, then call `DELETE /rag/ingestion/{version_id}` — confirm state transitions to `DELETING` and `ingestion.delete` job is enqueued
- [ ] 4.2 After worker processes the job — confirm Qdrant collection has no points with `document_version_id` filter, S3 object is gone, DB version row is `DELETED` or absent
- [ ] 4.3 Confirm `rag_answer_evidence` rows referencing the version have `document_version_id = NULL` after delete
- [ ] 4.4 Delete button visible in UI for `READY` document, triggers confirm dialog, calls API on confirm
- [x] 4.5 Delete a version that has no S3 object (simulate by removing the key) — confirm worker completes without error

Live verification notes:
- 4.1–4.4 remain pending because the local Qdrant service is unavailable and no authenticated end-to-end upload/UI session was available. Automated coverage for queue payload, worker registration, cascade ordering, vector filter, and UI type/lint checks passes.
- 4.5 was also smoke-tested against the configured object store with a unique missing key and completed successfully.
