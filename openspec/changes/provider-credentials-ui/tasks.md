## 1. Database

- [ ] 1.1 Alembic migration: buat tabel `rag_provider_credentials` (id, tenant_id, provider, key_name, value_enc, is_active, created_at, updated_at)
- [ ] 1.2 ORM: tambah `ProviderCredentialRecord` ke `rag_catalog.py`
- [ ] 1.3 Tambah `SECRET_KEY` ke `apps/api/app/core/settings.py` dan `.env.example`

## 2. Encryption Utils

- [ ] 2.1 Buat `apps/api/app/infrastructure/crypto.py` — `encrypt(value, key)` dan `decrypt(encrypted, key)` menggunakan AES-256-GCM

## 3. API — Repository & Service

- [ ] 3.1 Buat `ProviderCredentialRepository` dengan methods: `set_credential`, `find_credential`, `list_status`, `revoke`
- [ ] 3.2 Buat `ProviderCredentialService` use case (set, list_status, revoke)
- [ ] 3.3 Tambah DTOs ke `schemas.py`: `SetProviderCredentialRequest`, `ProviderCredentialStatusResponse`
- [ ] 3.4 Buat routes: `POST /rag/provider-credentials`, `GET /rag/provider-credentials`, `DELETE /rag/provider-credentials/{provider}/{key_name}`
- [ ] 3.5 Tambah DI ke `dependencies.py`

## 4. Provider Registry Update

- [ ] 4.1 Update `ProviderRegistry` untuk inject DB session dan tenant_id
- [ ] 4.2 Update `build_embedding_provider` untuk async DB lookup sebelum env fallback
- [ ] 4.3 Update worker `embed.py` untuk pass session + tenant_id ke registry

## 5. Shared Contracts

- [ ] 5.1 Tambah Zod schema `providerCredentialSetSchema` di `packages/schemas/`
- [ ] 5.2 Tambah response type `ProviderCredentialStatusResponse` di `packages/types/`

## 6. Frontend

- [ ] 6.1 Tambah API route constants + query keys untuk provider credentials
- [ ] 6.2 Buat hooks: `useProviderCredentials`, `useSetProviderCredential`, `useRevokeProviderCredential`
- [ ] 6.3 Buat halaman `/console/settings/providers` dengan form set key per provider
- [ ] 6.4 Tambah nav item `Providers` di console config (indent di bawah Settings)

## 7. Verification

- [ ] 7.1 Run `bun run typecheck` (web) — no errors
- [ ] 7.2 Run `bun run lint` (web) — no errors
- [ ] 7.3 Run `bun run test` (api) — all pass
- [ ] 7.4 Test end-to-end: set OpenAI key dari UI → create model profile OpenAI → upload dokumen → pipeline READY dengan OpenAI embedding
