# Tasks: kb-docling-api-key

## 1. Domain Entity

- [ ] 1.1 Add `docling_serve_api_key_enc: str | None` (default `None`) to `IngestionConfig` dataclass in `apps/api/app/domain/rag/catalog.py`
- [ ] 1.2 Update `INGESTION_CONFIG_DEFAULTS` with `docling_serve_api_key_enc=None`
- [ ] 1.3 Update `IngestionConfigRepository.upsert()` protocol to accept `docling_serve_api_key_enc: str | None`

## 2. Database Migration

- [ ] 2.1 Create `apps/api/alembic/versions/20260823_02_kb_docling_api_key.py` — add `docling_serve_api_key_enc TEXT NULL` to `rag_kb_ingestion_configs`
- [ ] 2.2 Implement `downgrade()` to drop the column
- [ ] 2.3 Run `uv run python -m alembic upgrade head` and verify

## 3. Infrastructure (ORM + Repository)

- [ ] 3.1 Add `docling_serve_api_key_enc: Mapped[str | None]` column to `IngestionConfigRecord`
- [ ] 3.2 Update `_to_ingestion_config()` to map new column
- [ ] 3.3 Update `SqlAlchemyIngestionConfigRepository.upsert()` to accept and persist `docling_serve_api_key_enc`

## 4. Application Service

- [ ] 4.1 Add `_UNSET = object()` sentinel at module level in `ingestion_config_service.py`
- [ ] 4.2 Add `docling_serve_api_key: str | None | object = _UNSET` to `upsert_config()` signature
- [ ] 4.3 In `upsert_config()`: if key is `_UNSET`, keep existing `docling_serve_api_key_enc`; if `None`, set to `None`; if str, encrypt via `crypto.encrypt()` and persist
- [ ] 4.4 Update `IngestionConfigResult` to include `docling_serve_api_key_set: bool`
- [ ] 4.5 Update `_to_result()` to set `docling_serve_api_key_set = config.docling_serve_api_key_enc is not None`
- [ ] 4.6 Add `get_api_key_decrypted(*, tenant, knowledge_base_id, settings) -> str | None` method — decrypt and return key, return `None` if not set; MUST NOT be called from HTTP routes
- [ ] 4.7 Update `upsert_config()` to accept `settings: Settings` (needed for `get_encryption_key()`)

## 5. API Layer

- [ ] 5.1 Add `docling_serve_api_key: str | None = None` to `IngestionConfigWriteRequest` in `schemas.py` (write-only, not in response)
- [ ] 5.2 Add `docling_serve_api_key_set: bool` to `IngestionConfigResponse` in `schemas.py`
- [ ] 5.3 Update route handler to pass `docling_serve_api_key` and `settings` to service
- [ ] 5.4 Add `"doclingServeApiKeySet": result.docling_serve_api_key_set` to both GET and PUT response dicts

## 6. DoclingServeAdapter

- [ ] 6.1 Add `api_key: str | None = None` parameter to `DoclingServeAdapter.__init__()`
- [ ] 6.2 In `_submit()`: add `headers={"X-Api-Key": self._api_key}` to `client.post()` when `self._api_key` is set
- [ ] 6.3 In `_poll()`: add `headers={"X-Api-Key": self._api_key}` to `client.get()` when `self._api_key` is set
- [ ] 6.4 In `_fetch_result()`: add `headers={"X-Api-Key": self._api_key}` to `client.get()` when `self._api_key` is set

## 7. Parse Stage

- [ ] 7.1 Update `_run_serve_adapter()` signature to accept `api_key: str | None`
- [ ] 7.2 Pass `api_key=api_key` to `DoclingServeAdapter.__init__()`
- [ ] 7.3 In `_parse_with_docling_or_fallback()`: call `svc.get_api_key_decrypted()` to get key before calling `_run_serve_adapter()` — requires passing `session` and `settings` or pre-decrypting in `parse_document()`
- [ ] 7.4 Decrypt key in `parse_document()` using a simple helper that calls `crypto.decrypt()` on `cfg.docling_serve_api_key_enc` if set, else `None`; pass decrypted key down to `_parse_with_docling_or_fallback()`
- [ ] 7.5 Ensure decrypted key is NOT logged anywhere

## 8. Frontend — Shared Packages

- [ ] 8.1 Add `doclingServeApiKey: z.string().nullable().default(null)` to `ingestionConfigSchema` in `packages/schemas/ingestion-config.ts` (write-only field)
- [ ] 8.2 Add `doclingServeApiKeySet: boolean` to `IngestionConfigResponse` in `packages/types/ingestion-config-response.ts`

## 9. Frontend — Hook

- [ ] 9.1 Add `docling_serve_api_key: data.doclingServeApiKey` to the `mutationFn` data mapping in `use-ingestion-config/index.ts`

## 10. Frontend — UI

- [ ] 10.1 Add password input for `doclingServeApiKey` below the URL field — only visible when `parser === "docling_serve"`
- [ ] 10.2 Show "Key saved" badge (green indicator) next to the password input when `config.doclingServeApiKeySet === true` and input is empty
- [ ] 10.3 Placeholder text: "Enter new key to replace" when key is already set, "Enter API key" when not set
- [ ] 10.4 On load, initialize `doclingServeApiKey` to `null` (never pre-fill from server — write-only)

## 11. Tests

- [ ] 11.1 Unit test: `upsert_config()` with key → `docling_serve_api_key_enc` is encrypted (not plain text)
- [ ] 11.2 Unit test: `upsert_config()` with `key=None` → clears `docling_serve_api_key_enc`
- [ ] 11.3 Unit test: `upsert_config()` with `key=_UNSET` → keeps existing encrypted value unchanged
- [ ] 11.4 Unit test: `get_api_key_decrypted()` → returns original plain-text key
- [ ] 11.5 Unit test: `DoclingServeAdapter` with `api_key` → `X-Api-Key` header on all requests
- [ ] 11.6 Unit test: `DoclingServeAdapter` with `api_key=None` → no `X-Api-Key` header
- [ ] 11.7 Unit test: `IngestionConfigResult.docling_serve_api_key_set` is `True` when enc key is set
- [ ] 11.8 Unit test: parse stage passes decrypted key to `_run_serve_adapter`

## 12. Verification

- [ ] 12.1 Run `uv run python -m alembic upgrade head` — migration applies cleanly
- [ ] 12.2 Run `cd apps/api && uv run python -m pytest tests/ -x -q` — all tests pass
- [ ] 12.3 Manual: set `parser="docling_serve"` + URL + API key on a KB, trigger ingestion, confirm `X-Api-Key` header sent (check docling-serve logs)
