## 1. Database — Model & Index Profile Schema

- [ ] 1.1 Alembic migration: tambah kolom baru ke `rag_model_profiles` (name, provider, model, modality, dimensions, config_json, is_active)
- [ ] 1.2 Alembic migration: tambah kolom baru ke `rag_index_profiles` (name, embedding_profile_id, sparse_profile_id, reranker_profile_id, collection, dimensions, distance_metric, chunking_strategy, chunk_size_tokens, chunk_overlap_tokens, parent_chunk_size, version, is_active)
- [ ] 1.3 Seed script: insert default FastEmbed dense + sparse profiles dan default index profile

## 2. API — Model Profile CRUD

- [ ] 2.1 Tambah `list_by_tenant`, `archive`, `find_by_id` ke `ModelProfileRepository` interface + SQLAlchemy implementation
- [ ] 2.2 Buat `ModelProfileService` use case (create, list, archive)
- [ ] 2.3 Tambah DTOs ke `schemas.py`: `CreateModelProfileRequest`, `ModelProfileResponse`
- [ ] 2.4 Buat routes: `POST /rag/model-profiles`, `GET /rag/model-profiles`, `DELETE /rag/model-profiles/{id}`
- [ ] 2.5 Tambah DI ke `dependencies.py`

## 3. API — Index Profile CRUD

- [ ] 3.1 Tambah `list_by_tenant`, `set_active`, `find_active` ke `IndexProfileRepository` + SQLAlchemy
- [ ] 3.2 Buat `IndexProfileService` use case (create, list, set_active)
- [ ] 3.3 Tambah DTOs: `CreateIndexProfileRequest`, `IndexProfileResponse`
- [ ] 3.4 Buat routes: `POST /rag/index-profiles`, `GET /rag/index-profiles`, `POST /rag/index-profiles/{id}/activate`
- [ ] 3.5 Tambah DI ke `dependencies.py`

## 4. Provider Adapters

- [ ] 4.1 Buat interface `EmbeddingProvider` di `apps/api/app/domain/`
- [ ] 4.2 Implement `FastEmbedProvider` di `apps/api/app/infrastructure/`
- [ ] 4.3 Implement `OpenAIEmbeddingProvider` di `apps/api/app/infrastructure/`
- [ ] 4.4 Implement `OllamaEmbeddingProvider` di `apps/api/app/infrastructure/`
- [ ] 4.5 Buat `ProviderRegistry` — singleton yang di-init dari env + active profiles
- [ ] 4.6 Buat fallback chain logic di `ProviderRegistry`

## 5. Worker — Queue Processors

- [ ] 5.1 Buat `apps/worker/.env` dengan `REDIS_URL` + `API_URL`
- [ ] 5.2 Buat queue processor `ingestion.parse` — extract text dari PDF/MD/TXT
- [ ] 5.3 Buat queue processor `ingestion.chunk` — split text sesuai IndexProfile strategy
- [ ] 5.4 Buat queue processor `ingestion.embed` — embed chunks via active IndexProfile provider
- [ ] 5.5 Buat queue processor `ingestion.index` — upsert ke Qdrant
- [ ] 5.6 Buat queue processor `ingestion.validate` — verify count, set READY/FAILED
- [ ] 5.7 Register semua processors di `create-workers.ts`
- [ ] 5.8 Tambah `pdfminer.six`, `fastembed`, `qdrant-client` ke `apps/api/app/` dependencies

## 6. Shared Contracts

- [ ] 6.1 Tambah Zod schema `modelProfileCreateSchema` di `packages/schemas/`
- [ ] 6.2 Tambah Zod schema `indexProfileCreateSchema` di `packages/schemas/`
- [ ] 6.3 Tambah response types `ModelProfileResponse`, `IndexProfileResponse` di `packages/types/`

## 7. Frontend — Model & Index Profile UI

- [ ] 7.1 Tambah hooks: `useModelProfiles`, `useCreateModelProfile`, `useDeleteModelProfile`
- [ ] 7.2 Tambah hooks: `useIndexProfiles`, `useCreateIndexProfile`, `useActivateIndexProfile`
- [ ] 7.3 Buat halaman `/console/settings/models` — list + create + delete model profiles
- [ ] 7.4 Buat halaman `/console/settings/index-profiles` — list + create + set active
- [ ] 7.5 Update Settings nav dengan submenu Models dan Index Profiles

## 8. Environment & Config

- [ ] 8.1 Tambah env vars ke `.env.example`: `OPENAI_API_KEY`, `OLLAMA_BASE_URL`, `FASTEMBED_CACHE_DIR`
- [ ] 8.2 Tambah env vars ke `apps/api/app/core/settings.py`
- [ ] 8.3 Update `apps/api/.env` dengan default FastEmbed config untuk dev

## 9. OpenAPI & Verification

- [ ] 9.1 Regenerate `docs/openapi.json`
- [ ] 9.2 Run `bun run typecheck` (web) — no errors
- [ ] 9.3 Run `bun run lint` (web) — no errors
- [ ] 9.4 Run `bun run test` (api) — all pass
- [ ] 9.5 Test end-to-end: create model profile → create index profile → set active → upload PDF → pipeline READY
