## Why

Operator tidak bisa mengkonfigurasi API key untuk embedding/generation providers (OpenAI, dll) tanpa harus edit `.env` file dan restart server. Ini membuat platform tidak bisa dioperasikan secara mandiri dari UI — setiap ganti provider harus akses server.

API keys adalah credentials sensitif yang tidak boleh disimpan plain text atau ditampilkan kembali. Platform perlu menyediakan UI write-only yang aman untuk set/update/revoke credentials per provider.

## What Changes

- **API**: Endpoint untuk set, check status, dan revoke provider credentials
- **API**: Encrypted storage di DB (AES-256-GCM) atau env-file write — tidak pernah return plaintext
- **UI**: Halaman `/console/settings/providers` — form set API key per provider, indicator configured/not configured
- **UI**: Integrasi dengan Model Profile form — warning jika provider belum dikonfigurasi
- **Worker**: Read credentials dari DB saat build provider, bukan hanya dari env

## Capabilities

### New Capabilities
- `provider-credentials-management`: API + UI untuk set/check/revoke provider credentials (OpenAI API key, Ollama base URL, HuggingFace token, dll) dengan encrypted storage

### Modified Capabilities
- `provider-adapter`: Provider registry membaca credentials dari DB (encrypted) sebagai fallback dari env vars
- `rag-settings-ui`: Tambah halaman Providers di Settings nav

## Impact

- `apps/api/app/` — domain entity ProviderCredential, repository, use case, routes
- `apps/api/alembic/` — migration untuk tabel `rag_provider_credentials`
- `apps/api/app/infrastructure/providers/registry.py` — baca credentials dari DB
- `apps/web/app/console/settings/providers/` — UI halaman providers
- `apps/web/hooks/transactions/use-provider-credentials/` — hooks
- `packages/schemas/` + `packages/types/` — schema dan types
- `docs/openapi.json` — regenerate
