## Context

Provider credentials (OpenAI API key, Ollama base URL, HuggingFace token) saat ini hanya bisa dikonfigurasi via env vars. Worker dan API membaca langsung dari `settings` object yang di-load dari `.env` saat startup.

Operator perlu bisa set credentials dari UI tanpa restart server, dan tanpa akses SSH ke server.

## Goals / Non-Goals

**Goals:**
- Tabel `rag_provider_credentials` di DB untuk simpan credentials per tenant per provider
- Encryption at rest: AES-256-GCM, key dari `SECRET_KEY` env var (tidak di-rotate otomatis)
- API endpoints: set credential, check status (configured/not), revoke
- UI write-only: input field, submit, tampilkan "Configured ✓" / "Not configured"
- Provider registry membaca dari DB dulu, fallback ke env var
- Credentials tidak pernah dikembalikan ke client (write-only)

**Non-Goals:**
- Secret manager (AWS Secrets Manager, Vault) — bisa ditambah Phase D
- Credential rotation otomatis
- Per-user credentials (semua tenant-scoped)
- Audit log per credential change (Phase D)

## Decisions

### 1. Encryption: AES-256-GCM dengan per-row IV

```
stored_value = base64(iv + ciphertext + tag)
key = sha256(SECRET_KEY env var)
```

IV di-generate random per-write. Tag memastikan integrity. Key tidak disimpan di DB — hanya di env. Jika `SECRET_KEY` tidak di-set, fallback ke `JWT_SECRET` yang sudah ada.

### 2. Schema: satu row per provider per tenant

```
rag_provider_credentials
  id          uuid PK
  tenant_id   uuid FK
  provider    varchar(60)   — openai | ollama | fastembed | huggingface
  key_name    varchar(120)  — api_key | base_url | token
  value_enc   text          — encrypted value
  is_active   boolean
  created_at  timestamp
  updated_at  timestamp
  UNIQUE(tenant_id, provider, key_name)
```

### 3. Provider registry: DB-first, env fallback

```python
async def get_api_key(provider: str) -> str | None:
    # 1. Check DB credentials
    cred = await repo.find(tenant_id, provider, "api_key")
    if cred:
        return decrypt(cred.value_enc)
    # 2. Fallback to env var
    return settings.openai_api_key  # etc
```

### 4. UI: write-only masked input

- Input type="password" — tidak display existing value
- Submit → POST /rag/provider-credentials
- Success → tampilkan "Configured ✓ (updated just now)"
- GET /rag/provider-credentials → return `{provider, keyName, isConfigured, updatedAt}` — TIDAK return value

### 5. Supported providers v1

| Provider | Key Name | Description |
|---|---|---|
| openai | api_key | OpenAI API key (sk-...) |
| ollama | base_url | Ollama server URL |
| huggingface | token | HF token untuk private models |

## Risks / Trade-offs

- **SECRET_KEY loss** → credentials tidak bisa di-decrypt → operator harus re-enter semua keys → dokumentasikan sebagai critical env var
- **JWT_SECRET as fallback key** → acceptable untuk dev, production HARUS set SECRET_KEY terpisah
- **No rotation** → jika key compromise, operator harus revoke + re-enter manual

## Migration Plan

1. Alembic migration: buat tabel `rag_provider_credentials`
2. Tambah `SECRET_KEY` ke settings + `.env.example`
3. Implement encryption utils
4. Implement repository + use case
5. Implement API endpoints
6. Update provider registry untuk baca dari DB
7. Implement frontend UI + hooks
8. Test: set OpenAI key dari UI → worker embed berhasil

## Open Questions

- Apakah perlu audit log siapa yang set credentials? → **Tidak untuk v1, Phase D**
- Apakah `base_url` untuk Ollama perlu diencrypt? → **Ya, konsisten — semua credentials diencrypt**
