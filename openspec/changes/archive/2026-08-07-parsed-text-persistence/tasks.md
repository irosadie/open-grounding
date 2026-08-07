# Tasks: parsed-text-persistence

## 1. Database Migration

- [x] 1.1 Create Alembic migration `add_parsed_text_to_document_versions` with `op.add_column("rag_document_versions", sa.Column("parsed_text", sa.Text(), nullable=True))`
- [x] 1.2 Add `downgrade()` that calls `op.drop_column("rag_document_versions", "parsed_text")`
- [x] 1.3 Run `alembic upgrade head` locally and confirm column exists with `\d rag_document_versions`

## 2. Domain Entity

- [x] 2.1 Add `parsed_text: str | None` field to `DocumentVersion` dataclass in `apps/api/app/domain/rag/catalog.py` (after `pipeline_fingerprint`)

## 3. Infrastructure — ORM & Repository

- [x] 3.1 Add `parsed_text: Mapped[str | None] = mapped_column(String, nullable=True, default=None)` to `DocumentVersionRecord` in `apps/api/app/infrastructure/rag_catalog.py`
- [x] 3.2 Add `parsed_text=row.parsed_text` to `_to_document_version()` mapper
- [x] 3.3 Add private `_get_row()` helper to `SqlAlchemyDocumentVersionRepository`
- [x] 3.4 Add `update_parsed_text()` method — writes `parsed_text` and sets `lifecycle_state = NEEDS_REVIEW` in one commit
- [x] 3.5 Add `patch_parsed_text()` method — updates only `parsed_text`, leaves `lifecycle_state` unchanged
- [x] 3.6 Add `find_parsed_text()` method — returns `row.parsed_text` or `None` if version not found

## 4. Worker — Parse Stage

- [x] 4.1 Replace `_parsed_cache[document_version_id] = text` with `await repo.update_parsed_text(tenant_id=tenant_id, version_id=document_version_id, parsed_text=text)` in `apps/api/app/workers/stages/parse.py`
- [x] 4.2 Remove the `await repo.update_lifecycle_state(..., "NORMALIZING")` call that immediately follows the cache write
- [x] 4.3 Update the log message to reflect persistence: `"[parse] persisted %d chars for %s"`

## 5. HTTP Schemas

- [x] 5.1 Add `ParsedTextResponse` Pydantic model to `apps/api/app/interfaces/http/schemas.py` with fields `version_id: str`, `parsed_text: str | None`, `lifecycle_state: str`
- [x] 5.2 Add `UpdateParsedTextRequest` Pydantic model with `text: str = Field(min_length=1, max_length=10_000_000)` and `model_config = {"extra": "forbid"}`
- [x] 5.3 Add both new schemas to the import block in `apps/api/app/interfaces/http/routes.py`

## 6. HTTP Routes

- [x] 6.1 Add `GET /rag/ingestion/{version_id}/parsed-text` — fetch version, return 404 if missing, return `parsedText` + `lifecycleState`
- [x] 6.2 Add `PATCH /rag/ingestion/{version_id}/parsed-text` — fetch version, 404 if missing, 409 if not `NEEDS_REVIEW`, call `patch_parsed_text()`, return updated text
- [x] 6.3 Add `POST /rag/ingestion/{version_id}/approve` — fetch version, 404 if missing, 409 if not `NEEDS_REVIEW`, call `update_lifecycle_state("NORMALIZING")`, enqueue chunking, return `enqueued`
- [x] 6.4 Add `POST /rag/ingestion/{version_id}/reject` — fetch version, 404 if missing, 409 if not `NEEDS_REVIEW`, call `update_lifecycle_state("FAILED")`, return updated state
- [x] 6.5 Add `from app.domain.rag.catalog import DocumentVersionLifecycleState` import to `routes.py` (needed for state comparison in PATCH/approve/reject handlers)

## 7. Verification

- [x] 7.1 Run `alembic upgrade head` in a clean DB and confirm no errors
- [x] 7.2 Manually trigger the parse stage for a test document and confirm `rag_document_versions.parsed_text` is non-null and `lifecycle_state = NEEDS_REVIEW`
- [x] 7.3 Call `GET /rag/ingestion/{version_id}/parsed-text` and confirm text matches what was extracted
- [x] 7.4 Call `PATCH /rag/ingestion/{version_id}/parsed-text` with corrected text and confirm DB is updated
- [x] 7.5 Call `POST /rag/ingestion/{version_id}/approve` and confirm state transitions to `NORMALIZING` and chunking is enqueued
- [x] 7.6 On a fresh `NEEDS_REVIEW` version, call `POST /rag/ingestion/{version_id}/reject` and confirm state is `FAILED`
- [x] 7.7 Confirm that `PATCH`, `approve`, and `reject` all return 409 when version is not in `NEEDS_REVIEW`
- [x] 7.8 Confirm that all four endpoints return 404 for a non-existent or cross-tenant `version_id`
- [x] 7.9 Run `cd apps/api && uv run pytest` and confirm all existing tests pass
