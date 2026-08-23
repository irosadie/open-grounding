## Why

Documents uploaded to a knowledge base have no clean delete path. The existing `DELETE /rag/ingestion/{document_version_id}` only sets lifecycle state to `DELETING` — it never removes vectors from Qdrant, never deletes the raw file from object store, and never hard-deletes the DB row. The `DELETED` state exists in the enum but nothing transitions to it. This means deleted documents accumulate as dead weight in Qdrant and MinIO indefinitely, polluting retrieval and consuming storage.

## What Changes

- **New BullMQ worker stage** `ingestion.delete` — handles the full cascade: delete Qdrant vectors by `document_version_id` filter, delete raw file from object store (`object_key_raw`), null out `parsed_text` in DB, transition `rag_index_generations` to `DELETED`, transition `rag_document_versions` to `DELETED`, soft-delete `rag_documents` if all versions are deleted
- **Existing `soft_delete`** in `IngestionIntakeService` updated to enqueue an `ingestion.delete` job instead of only setting state to `DELETING`
- **New `ObjectStoreAdapter.delete_object`** concrete implementation in `S3ObjectStoreAdapter` (protocol already declared, no implementation exists)
- **`rag_answer_evidence` FK handling** — evidence rows referencing the version are nulled/soft-deleted before hard-delete to avoid RESTRICT constraint
- **Frontend delete button** added to the "Documents in KB" list (`ingestion-content.tsx`) for all terminal-state documents (`READY`, `FAILED`, `NEEDS_REVIEW`), with confirmation dialog
- **Frontend lifecycle badge** in document list updated to handle `DELETING` and `DELETED` states

## Capabilities

### New Capabilities

- `document-hard-delete`: Full cascade delete of a document version — Qdrant vectors, S3 raw file, DB rows — triggered via existing DELETE endpoint, executed asynchronously via BullMQ worker

### Modified Capabilities

- `rag-ingestion-operations`: `soft_delete` now enqueues `ingestion.delete` job; delete endpoint response unchanged
- `rag-source-intake-and-versioning`: `ObjectStoreAdapter` gets concrete `delete_object` implementation
- `rag-ingestion-workbench-ui`: Document list gains delete button with confirm dialog for terminal-state documents

## Impact

- **New file:** `apps/api/app/workers/stages/delete.py` — `delete_document_version()` cascade handler
- **Modified:** `apps/api/app/application/ingestion_intake_service.py` — enqueue delete job in `soft_delete`
- **Modified:** `apps/api/app/workers/ingestion_worker.py` — register `ingestion.delete` worker
- **Modified:** `apps/api/app/infrastructure/object_store.py` (or equivalent) — implement `delete_object`
- **Modified:** `apps/web/app/console/document/ingestion-content.tsx` — add delete button + confirm dialog
- **No new API endpoints** — reuses existing `DELETE /rag/ingestion/{document_version_id}`
- **No DB migration needed** — `DELETED` state already in enum, no new tables
- **Risk:** `rag_answer_evidence` RESTRICT FK — must null/delete evidence rows before version hard-delete
