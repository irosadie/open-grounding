# Design: parsed-text-persistence

## Architecture Overview

This change touches four layers of the Clean Architecture stack. The flow is strictly top-down: HTTP interface → application service → domain entity → infrastructure repository → database. No layer skips another.

```
PATCH/POST (routes.py)
  → IngestionService (application)
      → SqlAlchemyDocumentVersionRepository (infrastructure)
          → DocumentVersionRecord.parsed_text (ORM column)
              → rag_document_versions.parsed_text (Postgres)

parse_document() (worker)
  → SqlAlchemyDocumentVersionRepository.update_parsed_text()
      → sets parsed_text + lifecycle_state = NEEDS_REVIEW atomically
```

---

## Database

### Migration

New Alembic migration file: `apps/api/alembic/versions/<revision>_add_parsed_text_to_document_versions.py`

```python
def upgrade() -> None:
    op.add_column(
        "rag_document_versions",
        sa.Column("parsed_text", sa.Text(), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("rag_document_versions", "parsed_text")
```

The column is `TEXT` (unbounded), nullable. No index — it is never filtered on, only read by primary key. Existing rows get `NULL` automatically.

---

## Domain Layer

### `DocumentVersion` entity (`apps/api/app/domain/rag/catalog.py`)

Add one field to the frozen dataclass:

```python
@dataclass(frozen=True)
class DocumentVersion:
    ...
    parsed_text: str | None  # added after pipeline_fingerprint
```

Placement: after `pipeline_fingerprint`, before `object_key_raw`. This keeps parse-related fields grouped.

No business logic lives here — the entity is a pure value object.

---

## Infrastructure Layer

### `DocumentVersionRecord` ORM model (`apps/api/app/infrastructure/rag_catalog.py`)

Add one mapped column to `DocumentVersionRecord`:

```python
parsed_text: Mapped[str | None] = mapped_column(
    String, nullable=True, default=None
)
```

Place it after `pipeline_fingerprint` to mirror domain entity field order.

### `_to_document_version()` mapper

Add `parsed_text=row.parsed_text` to the `DocumentVersion(...)` constructor call.

### `SqlAlchemyDocumentVersionRepository` — new methods

#### `update_parsed_text()`

Writes `parsed_text` and sets `lifecycle_state = NEEDS_REVIEW` in a single `commit()`. This is the only place the state transitions to `NEEDS_REVIEW`.

```python
async def update_parsed_text(
    self,
    *,
    tenant_id: str,
    version_id: str,
    parsed_text: str,
) -> DocumentVersion | None:
    row = await self._get_row(tenant_id=tenant_id, version_id=version_id)
    if row is None:
        return None
    row.parsed_text = parsed_text
    row.lifecycle_state = DocumentVersionLifecycleState.NEEDS_REVIEW
    await self._session.commit()
    await self._session.refresh(row)
    return _to_document_version(row)
```

#### `find_parsed_text()`

Read-only fetch returning the current `parsed_text` value. Returns `None` if the version does not exist.

```python
async def find_parsed_text(
    self,
    *,
    tenant_id: str,
    version_id: str,
) -> str | None:
    row = await self._get_row(tenant_id=tenant_id, version_id=version_id)
    return row.parsed_text if row else None
```

#### `patch_parsed_text()`

Updates only `parsed_text` without changing lifecycle state. Used by the PATCH endpoint when the operator submits a correction.

```python
async def patch_parsed_text(
    self,
    *,
    tenant_id: str,
    version_id: str,
    text: str,
) -> DocumentVersion | None:
    row = await self._get_row(tenant_id=tenant_id, version_id=version_id)
    if row is None:
        return None
    row.parsed_text = text
    await self._session.commit()
    await self._session.refresh(row)
    return _to_document_version(row)
```

A private `_get_row()` helper is extracted to avoid repeating the `select(...).where(tenant_id, id)` pattern across the three new methods:

```python
async def _get_row(
    self, *, tenant_id: str, version_id: str
) -> DocumentVersionRecord | None:
    result = await self._session.execute(
        select(DocumentVersionRecord).where(
            DocumentVersionRecord.tenant_id == tenant_id,
            DocumentVersionRecord.id == version_id,
        )
    )
    return result.scalar_one_or_none()
```

The existing `find_by_id()` already does the same select but returns a domain entity — keeping `_get_row()` internal prevents ORM record leakage out of the repository.

---

## Worker Layer

### `parse_document()` (`apps/api/app/workers/stages/parse.py`)

Two changes only:

1. After extracting `text`, call `repo.update_parsed_text(...)` instead of writing to `_parsed_cache`.
2. Remove the subsequent `repo.update_lifecycle_state(..., "NORMALIZING")` call — state is now `NEEDS_REVIEW` and the function returns.

```python
async def parse_document(...) -> str:
    ...
    text = _extract_text(raw_content, mime_type, version.object_key_raw)

    version = await repo.update_parsed_text(
        tenant_id=tenant_id,
        version_id=document_version_id,
        parsed_text=text,
    )
    # Pipeline halts here — approval required before NORMALIZING

    logger.info("[parse] persisted %d chars for %s", len(text), document_version_id)
    return text
```

The `_parsed_cache` dict remains in the file (it is still used by other stages for chunking data) but the parse stage no longer writes to it. Do not delete the other caches.

---

## HTTP Interface Layer

### New Pydantic schemas (`apps/api/app/interfaces/http/schemas.py`)

```python
class ParsedTextResponse(BaseModel):
    version_id: str
    parsed_text: str | None
    lifecycle_state: str

class UpdateParsedTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000_000)

    model_config = {"extra": "forbid"}
```

`max_length=10_000_000` (10 MB of text) is a safety guard against pathologically large payloads while accommodating real-world long documents.

### New route handlers (`apps/api/app/interfaces/http/routes.py`)

All four endpoints are added to the existing `rag_router` (prefix `/rag`). They reuse `TenantContextDependency` and `IngestionServiceDependency` already present in the file.

#### `GET /rag/ingestion/{version_id}/parsed-text`

```python
@rag_router.get("/ingestion/{version_id}/parsed-text")
async def get_parsed_text(
    version_id: str,
    tenant: TenantContextDependency,
    service: IngestionServiceDependency,
) -> dict[str, object]:
    version = await service._version_repo.find_by_id(
        tenant_id=tenant.tenant_id, version_id=version_id
    )
    if version is None:
        raise DomainError("NOT_FOUND", "Document version not found", 404)
    return success(
        "Parsed text loaded",
        {
            "versionId": version.id,
            "parsedText": version.parsed_text,
            "lifecycleState": version.lifecycle_state.value,
        },
    )
```

#### `PATCH /rag/ingestion/{version_id}/parsed-text`

```python
@rag_router.patch("/ingestion/{version_id}/parsed-text")
async def update_parsed_text(
    version_id: str,
    payload: UpdateParsedTextRequest,
    tenant: TenantContextDependency,
    service: IngestionServiceDependency,
) -> dict[str, object]:
    version = await service._version_repo.find_by_id(
        tenant_id=tenant.tenant_id, version_id=version_id
    )
    if version is None:
        raise DomainError("NOT_FOUND", "Document version not found", 404)
    if version.lifecycle_state != DocumentVersionLifecycleState.NEEDS_REVIEW:
        raise DomainError("CONFLICT", "Version is not in NEEDS_REVIEW state", 409)
    updated = await service._version_repo.patch_parsed_text(
        tenant_id=tenant.tenant_id, version_id=version_id, text=payload.text
    )
    return success(
        "Parsed text updated",
        {
            "versionId": updated.id,
            "parsedText": updated.parsed_text,
            "lifecycleState": updated.lifecycle_state.value,
        },
    )
```

#### `POST /rag/ingestion/{version_id}/approve`

```python
@rag_router.post("/ingestion/{version_id}/approve")
async def approve_parsed_text(
    version_id: str,
    tenant: TenantContextDependency,
    service: IngestionServiceDependency,
) -> dict[str, object]:
    version = await service._version_repo.find_by_id(
        tenant_id=tenant.tenant_id, version_id=version_id
    )
    if version is None:
        raise DomainError("NOT_FOUND", "Document version not found", 404)
    if version.lifecycle_state != DocumentVersionLifecycleState.NEEDS_REVIEW:
        raise DomainError("CONFLICT", "Version is not in NEEDS_REVIEW state", 409)
    updated = await service._version_repo.update_lifecycle_state(
        tenant_id=tenant.tenant_id,
        version_id=version_id,
        lifecycle_state="NORMALIZING",
    )
    enqueued = await service._enqueue_chunking(tenant=tenant, version=updated)
    return success(
        "Document version approved",
        {
            "versionId": updated.id,
            "lifecycleState": updated.lifecycle_state.value,
            "enqueued": enqueued,
        },
    )
```

#### `POST /rag/ingestion/{version_id}/reject`

```python
@rag_router.post("/ingestion/{version_id}/reject")
async def reject_parsed_text(
    version_id: str,
    tenant: TenantContextDependency,
    service: IngestionServiceDependency,
) -> dict[str, object]:
    version = await service._version_repo.find_by_id(
        tenant_id=tenant.tenant_id, version_id=version_id
    )
    if version is None:
        raise DomainError("NOT_FOUND", "Document version not found", 404)
    if version.lifecycle_state != DocumentVersionLifecycleState.NEEDS_REVIEW:
        raise DomainError("CONFLICT", "Version is not in NEEDS_REVIEW state", 409)
    updated = await service._version_repo.update_lifecycle_state(
        tenant_id=tenant.tenant_id,
        version_id=version_id,
        lifecycle_state="FAILED",
    )
    return success(
        "Document version rejected",
        {"versionId": updated.id, "lifecycleState": updated.lifecycle_state.value},
    )
```

---

## Error Handling

All four endpoints follow the existing `DomainError` → middleware pattern already in place:

| Condition | Error code | HTTP status |
|-----------|-----------|-------------|
| Version not found or cross-tenant | `NOT_FOUND` | 404 |
| State is not `NEEDS_REVIEW` (for PATCH/approve/reject) | `CONFLICT` | 409 |
| Empty text in PATCH body | Pydantic `min_length` | 422 |

No new error codes are introduced.

---

## Sequence Diagram

```
Worker                    DB                      Operator (API)
  |                        |                           |
  |-- parse extract ------>|                           |
  |-- update_parsed_text ->| parsed_text = <text>      |
  |                        | lifecycle = NEEDS_REVIEW  |
  |<-- return version -----|                           |
  | (pipeline halts)       |                           |
  |                        |<-- GET parsed-text -------|
  |                        |--- return text ---------->|
  |                        |<-- PATCH parsed-text -----|
  |                        |--- updated text --------->|
  |                        |<-- POST approve ----------|
  |                        | lifecycle = NORMALIZING   |
  |<-- enqueue chunking ---|                           |
  |                        |--- 200 OK --------------->|
```

---

## Decisions

**Why store text in the DB column instead of object store?**
Simplicity. The text is already extracted (small compared to raw bytes), needs to be readable via SQL for debugging, and the existing repository pattern handles it with one new column. An object store approach would require a new key scheme, async streaming, and a separate read path — over-engineering for what is essentially an intermediate text buffer.

**Why `NEEDS_REVIEW` instead of a new state?**
The state already exists in `DocumentVersionLifecycleState` and its semantics match exactly. Using it avoids an enum change and a migration for the enum type.

**Why not add a dedicated use-case class for approve/reject?**
The operations are thin: one state check + one `update_lifecycle_state` call. A dedicated use case class would add a file with two methods that each delegate to the repo. Following the project's simplicity-first principle, the logic sits directly in the route handlers, consistent with how `soft_delete` and status endpoints are handled in the same file.

**Why `_get_row()` private helper in the repository?**
The three new repo methods (`update_parsed_text`, `patch_parsed_text`, `find_parsed_text`) all run the same `select().where(tenant_id, id)` query. Extracting it to a private helper avoids repeating four lines three times and keeps the tenant-scope guard in one place.
