## 1. Database

- [x] 1.1 Alembic migration: buat tabel `rag_provider_credentials` (id, tenant_id, provider, key_name, value_enc, is_active, created_at, updated_at)
- [x] 1.2 ORM: tambah `ProviderCredentialRecord` ke `rag_catalog.py`
- [x] 1.3 Tambah `SECRET_KEY` ke `apps/api/app/core/settings.py` dan `.env.example`

## 2. Encryption Utils

- [x] 2.1 Buat `apps/api/app/infrastructure/crypto.py` — `encrypt(value, key)` dan `decrypt(encrypted, key)` menggunakan AES-256-GCM

## 3. API — Repository & Service

- [x] 3.1 Buat `ProviderCredentialRepository` dengan methods: `set_credential`, `find_credential`, `list_status`, `revoke`
- [x] 3.2 Buat `ProviderCredentialService` use case (set, list_status, revoke)
- [x] 3.3 Tambah DTOs ke `schemas.py`: `SetProviderCredentialRequest`, `ProviderCredentialStatusResponse`
- [x] 3.4 Buat routes: `POST /rag/provider-credentials`, `GET /rag/provider-credentials`, `DELETE /rag/provider-credentials/{provider}/{key_name}`
- [x] 3.5 Tambah DI ke `dependencies.py`

## 4. Provider Registry Update

- [x] 4.1 Update `ProviderRegistry` untuk inject DB session dan tenant_id
- [x] 4.2 Update `build_embedding_provider` untuk async DB lookup sebelum env fallback
- [x] 4.3 Update worker `embed.py` untuk pass session + tenant_id ke registry

## 5. Shared Contracts

- [x] 5.1 Tambah Zod schema `providerCredentialSetSchema` di `packages/schemas/` — tidak diperlukan, frontend tidak menggunakannya
- [x] 5.2 Tambah response type `ProviderCredentialStatusResponse` di `packages/types/provider-credentials-response.ts`

## 6. Frontend

- [x] 6.1 Tambah API route constants + query keys untuk provider credentials
- [x] 6.2 Buat hooks: `useProviderCredentials`, `useSetProviderCredential`, `useRevokeProviderCredential`
- [x] 6.3 Buat halaman `/console/settings/providers` dengan form set key per provider
- [x] 6.4 Tambah nav item `Providers` di console config

## 7. Verification

- [x] 7.1 Run `bun run typecheck` (web) — no errors
- [x] 7.2 Run `bun run lint` (web) — no errors
- [x] 7.3 Run `bun run test` (api) — all pass
- [x] 7.4 Test end-to-end: set OpenAI key dari UI → create model profile OpenAI → upload dokumen → pipeline READY dengan OpenAI embedding
