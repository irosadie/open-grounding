# Design: kb-docling-api-key

## Context

See `proposal.md` — Why for motivation.

Current state:
- `crypto.py` already provides `encrypt()`, `decrypt()`, `get_encryption_key()` using
  AES-256-GCM. Same pattern used for provider credentials.
- `IngestionConfig` already has `docling_serve_url` per KB.
- `DoclingServeAdapter` uses `httpx.AsyncClient` — headers can be injected per-request
  or via default headers on the client.
- Parse stage calls `_run_serve_adapter()` which constructs the adapter.

## Goals / Non-Goals

**Goals:**
- API key stored encrypted at rest, never returned plain-text via API.
- `X-Api-Key` injected on every HTTP request to docling-serve when key is set.
- Per-KB key, consistent with per-KB URL.
- `docling_serve_api_key_set: bool` in response so UI can show "Key saved" indicator.

**Non-Goals:**
- Global fallback API key in env var (key follows URL, both per-KB).
- Key rotation or versioning.
- Audit log for key changes.

## Decisions

### 1. `X-Api-Key` injected via per-request headers, not client default headers

The shared `httpx.AsyncClient` is reused across all jobs and all KBs. If we set
`X-Api-Key` as a default header on the client, it leaks across KBs. Instead, the
adapter injects the header per-request by passing `headers={"X-Api-Key": api_key}`
to each `client.post()` / `client.get()` call when `api_key` is set.

### 2. Column type is `TEXT NULL`, not `VARCHAR`

Encrypted values are base64-encoded AES-256-GCM output — variable length, can be
long. `TEXT` avoids length constraints.

### 3. `get_api_key_decrypted()` is a service method, not called from HTTP layer

Follows the same pattern as `provider_credential_service.get_decrypted()`. Parse
stage calls it directly. HTTP routes never touch the decrypted value.

### 4. Write-only field in API — `docling_serve_api_key_set: bool` in response

Standard pattern for credential fields (same as how provider credentials are handled).
Client sends plain-text key on write, gets back a boolean indicator. UI shows a
password input + "Key saved" badge.

### 5. `upsert_config()` signature: `docling_serve_api_key` is optional, default `...` (sentinel)

To distinguish "not provided" (keep existing key) from "explicitly set to None"
(clear key), use a sentinel default. If caller passes the field, update it. If not
passed, keep existing encrypted value. This avoids accidentally clearing keys on
partial updates.

Use `_UNSET = object()` sentinel pattern — same approach used elsewhere in the project.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Losing `SECRET_KEY` makes keys unrecoverable | Same risk as provider credentials — documented, operator responsibility |
| Per-request header injection overhead | Negligible — dict creation per HTTP call |
| Sentinel pattern adds service complexity | Small, well-contained — one sentinel constant |

## Migration Plan

1. Add Alembic migration `20260823_02_kb_docling_api_key.py` — add `docling_serve_api_key_enc TEXT NULL`.
2. Domain → ORM → service → API → adapter → parse stage → frontend.
3. No queue changes, no other table changes.

**Rollback:** Alembic downgrade drops column. Existing behaviour unchanged (adapter
falls back to no auth header when key is absent).

## Open Questions

None.
