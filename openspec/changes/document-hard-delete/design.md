## Context

Delete document is currently broken end-to-end. The API endpoint exists (`DELETE /rag/ingestion/{id}`) and transitions state to `DELETING`, but stops there. Vectors remain in Qdrant, raw files remain in MinIO, and DB rows are never hard-deleted. The `DELETED` state exists in the enum but nothing ever reaches it. The object store adapter has a `delete_object` protocol declared but no implementation. The `rag_answer_evidence` table has a RESTRICT FK on `document_version_id` which would block any hard-delete attempt without prior cleanup.

## Goals / Non-Goals

**Goals:**
- Full cascade delete: Qdrant vectors → S3 raw file → DB answer evidence nullification → DB version hard-delete → DB document soft-delete
- Async execution via BullMQ `ingestion.delete` worker — delete is non-blocking from the API perspective
- `ObjectStoreAdapter.delete_object` concrete implementation
- Frontend delete button on document list with confirmation
- Non-fatal handling for missing Qdrant points or S3 objects (idempotent)

**Non-Goals:**
- Deleting conversation history or answer run records referencing the document
- Bulk delete (delete all documents in a KB) — out of scope
- Undo/restore after deletion
- Frontend delete from the review page

## Decisions

### D1: Async BullMQ worker for cascade delete

**Chosen:** `soft_delete` sets state to `DELETING` and enqueues `ingestion.delete` job. Worker executes cascade asynchronously.

**Alternatives considered:**
- _Synchronous delete in the API handler_: Cascade involves Qdrant HTTP call + S3 HTTP call + multiple DB writes. Too slow for a synchronous endpoint. Also risky — partial failures leave inconsistent state with no retry mechanism.
- _Scheduled background job_: Cron-style cleanup of `DELETING` rows. Adds latency and complexity. BullMQ is already the job infrastructure.

**Rationale:** Async worker with retry is the right pattern for multi-system cleanup. Consistent with how ingestion stages are handled.

### D2: Answer evidence — null document_version_id before hard-delete

**Chosen:** Before hard-deleting the `rag_document_versions` row, set `document_version_id = NULL` on all `rag_answer_evidence` rows referencing it. This satisfies the RESTRICT FK without losing the answer run history.

**Alternatives considered:**
- _Hard-delete evidence rows_: Destroys answer audit history, unacceptable.
- _Defer FK to DEFERRABLE INITIALLY DEFERRED_: Requires migration, adds DB complexity.

**Rationale:** Nulling the FK preserves answer history while unblocking the version delete. Evidence rows become orphaned but traceable via `answer_run_id`.

### D3: Delete worker cascade order

```
1. Null rag_answer_evidence.document_version_id (unblock FK)
2. Delete Qdrant vectors (tenant_id + document_version_id filter)
3. Delete S3 raw file (object_key_raw)
4. Null parsed_text on document_version (free DB storage)
5. Transition rag_index_generations → DELETED
6. Hard-delete rag_document_versions row
7. If no versions remain → soft-delete rag_documents row
```

Steps 2 and 3 are non-fatal on not-found. Steps 1 and 5 happen in DB before step 6.

### D4: Frontend delete — only terminal states

**Chosen:** Delete button shown only for `READY`, `FAILED`, `NEEDS_REVIEW`. In-progress states (`PARSING`, `CHUNKING`, etc.) do not show the button.

**Rationale:** Deleting a document mid-pipeline would leave orphaned BullMQ jobs that would try to write to a `DELETING` version. Simpler to block it at the UI level. The worker stages already check lifecycle state; they will skip/fail gracefully if the version is gone, but preventing it in UI is cleaner.

## Implementation Map

```
apps/api/app/workers/stages/delete.py              ← NEW: delete_document_version()
apps/api/app/application/ingestion_intake_service.py ← MODIFY: soft_delete enqueues job
apps/api/app/workers/ingestion_worker.py           ← MODIFY: register ingestion.delete worker
apps/api/app/infrastructure/object_store.py        ← MODIFY: implement delete_object
apps/web/app/console/document/ingestion-content.tsx ← MODIFY: delete button + confirm + badges
```

## Risks / Trade-offs

- **[Risk] Qdrant delete with stale collection name** — If the index profile collection has changed since indexing, the delete filter may target the wrong collection. Mitigation: resolve active collection from `rag_index_generations` for that version, not from current active profile.
- **[Risk] S3 key mismatch** — `object_key_raw` may have been stored with a different prefix in dev vs prod. Mitigation: non-fatal, log warning, continue.
- **[Risk] Partial cascade failure** — If Qdrant delete succeeds but S3 delete fails, the job retries. Qdrant delete is idempotent (no-op if points already gone). S3 delete is also idempotent. Safe to retry the full cascade.
- **[Trade-off] Hard-delete vs soft-delete** — We hard-delete `rag_document_versions` rather than leaving the row. This means the version ID is gone from DB. Any external reference (e.g. a bookmark to the review URL) will 404. Acceptable — the version is intentionally destroyed.

## Open Questions

- Should the delete button in the UI also be available from the review page for `FAILED`/`NEEDS_REVIEW` documents? (Recommendation: out of scope for this change, add later)
- Should deleting the last version of a document also delete the `rag_knowledge_source` row? (Recommendation: no — keep source record for audit; only delete document + versions)
