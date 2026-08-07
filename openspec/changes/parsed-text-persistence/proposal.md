# Proposal: parsed-text-persistence

## Summary

After the parse stage completes, extracted text is only held in `_parsed_cache` — an in-process dict in `workers/stages/parse.py`. This memory is lost on restart, never inspectable, and the pipeline blindly advances to chunking with no human gate. The states `NEEDS_REVIEW` and `QUARANTINED` exist in `DocumentVersionLifecycleState` but are never set.

This change closes the gap: persist parsed text to the database, pause the pipeline for human review, and add four API endpoints that let operators read, correct, approve, or reject a parsed document before chunking begins.

## Problem

1. **Data loss** — parsed text only survives as long as the process is alive. A worker crash drops it silently.
2. **No review gate** — the pipeline skips `NEEDS_REVIEW` and goes straight from `PARSING` → `NORMALIZING` → `CHUNKING`. Operators have no opportunity to inspect or correct OCR/extraction errors before embeddings are produced.
3. **Dead states** — `NEEDS_REVIEW` and `QUARANTINED` are defined but never used, misleading consumers of the lifecycle enum.
4. **Untraceable corrections** — there is no record of what text was actually chunked vs what was originally extracted.

## Proposed Solution

### 1. Database persistence
Add a nullable `parsed_text TEXT` column to `rag_document_versions` via Alembic migration. After extraction, the parse stage writes the text to this column atomically with the state transition to `NEEDS_REVIEW`.

### 2. Pipeline gate
Change `parse.py` so the function exits at `NEEDS_REVIEW` instead of advancing to `NORMALIZING`. Chunking only starts after an explicit approval API call.

### 3. Review API (4 endpoints under `rag_router`)
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/rag/ingestion/{version_id}/parsed-text` | Return persisted parsed text |
| `PATCH` | `/rag/ingestion/{version_id}/parsed-text` | Submit corrected text |
| `POST` | `/rag/ingestion/{version_id}/approve` | Approve and enqueue chunking |
| `POST` | `/rag/ingestion/{version_id}/reject` | Reject and set `FAILED` |

### 4. Repository methods
Add `update_parsed_text()` and `find_parsed_text()` to `SqlAlchemyDocumentVersionRepository`.

### 5. Domain entity
Add `parsed_text: str | None` field to the `DocumentVersion` frozen dataclass.

## Affected Files

| File | Change |
|------|--------|
| `apps/api/app/domain/rag/catalog.py` | Add `parsed_text: str | None` to `DocumentVersion` |
| `apps/api/app/infrastructure/rag_catalog.py` | Add `parsed_text` column to `DocumentVersionRecord`; add `update_parsed_text()` and `find_parsed_text()` to repo |
| `apps/api/app/workers/stages/parse.py` | Persist text to DB; transition to `NEEDS_REVIEW` instead of `NORMALIZING` |
| `apps/api/app/interfaces/http/routes.py` | Add 4 new endpoints to `rag_router` |
| `apps/api/app/interfaces/http/schemas.py` | Add `ParsedTextResponse`, `UpdateParsedTextRequest` |
| New Alembic migration | `parsed_text TEXT` column on `rag_document_versions` |

## Out of Scope

- Frontend review UI (tracked separately in `ingestion-review-ui`)
- Automatic re-parse on rejection
- Notification/webhook on state change
- `QUARANTINED` state activation (separate concern)

## Success Criteria

- Parsed text survives a worker restart
- A version in `NEEDS_REVIEW` does not advance until `POST .../approve` is called
- Corrected text submitted via `PATCH` is what gets chunked, not the original
- `POST .../reject` terminates the pipeline at `FAILED`
- All four endpoints are tenant-scoped and return 404 for unknown or cross-tenant versions
