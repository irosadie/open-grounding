## 1. Database — Model & Index Profile Schema

- [x] 1.1 Alembic migration: tambah kolom baru ke `rag_model_profiles` (name, provider, model, modality, dimensions, config_json, is_active)
- [x] 1.2 Alembic migration: tambah kolom baru ke `rag_index_profiles` (name, embedding_profile_id, sparse_profile_id, reranker_profile_id, collection, dimensions, distance_metric, chunking_strategy, chunk_size_tokens, chunk_overlap_tokens, parent_chunk_size, version, is_active)
- [x] 1.3 Seed script: insert default FastEmbed dense + sparse profiles dan default index profile — `infrastructure/profile_seed.py`

## 2. API — Model Profile CRUD

- [x] 2.1 Tambah `list_by_tenant`, `archive`, `find_by_id` ke `ModelProfileRepository` interface + SQLAlchemy implementation
- [x] 2.2 Buat `ModelProfileService` use case (create, list, archive)
- [x] 2.3 Tambah DTOs ke `schemas.py`: `CreateModelProfileRequest`, `ModelProfileResponse`
- [x] 2.4 Buat routes: `POST /rag/model-profiles`, `GET /rag/model-profiles`, `DELETE /rag/model-profiles/{id}`
- [x] 2.5 Tambah DI ke `dependencies.py`

## 3. API — Index Profile CRUD

- [x] 3.1 Tambah `list_by_tenant`, `set_active`, `find_active` ke `IndexProfileRepository` + SQLAlchemy
- [x] 3.2 Buat `IndexProfileService` use case (create, list, set_active)
- [x] 3.3 Tambah DTOs: `CreateIndexProfileRequest`, `IndexProfileResponse`
- [x] 3.4 Buat routes: `POST /rag/index-profiles`, `GET /rag/index-profiles`, `POST /rag/index-profiles/{id}/activate`
- [x] 3.5 Tambah DI ke `dependencies.py`

## 4. Provider Adapters

- [x] 4.1 Buat interface `EmbeddingProvider` di `apps/api/app/domain/`
- [x] 4.2 Implement `FastEmbedProvider` di `apps/api/app/infrastructure/providers/fastembed_provider.py`
- [x] 4.3 Implement `OpenAIEmbeddingProvider` di `apps/api/app/infrastructure/providers/openai_provider.py`
- [x] 4.4 Implement `OllamaEmbeddingProvider` di `apps/api/app/infrastructure/providers/ollama_provider.py`
- [x] 4.5 Buat `ProviderRegistry` — `infrastructure/providers/registry.py`
- [x] 4.6 Buat fallback chain logic di `ProviderRegistry` — `infrastructure/providers/registry.py`

## 5. Worker — Queue Processors

- [x] 5.1 Buat `apps/worker/.env` dengan `REDIS_URL`
- [x] 5.2 Buat queue processor `ingestion.parse` — `apps/api/app/workers/stages/parse.py`
- [x] 5.3 Buat queue processor `ingestion.chunk` — `apps/api/app/workers/stages/chunk.py`
- [x] 5.4 Buat queue processor `ingestion.embed` — `apps/api/app/workers/stages/embed.py`
- [x] 5.5 Buat queue processor `ingestion.index` — `apps/api/app/workers/stages/index.py`
- [x] 5.6 Buat queue processor `ingestion.validate` — `apps/api/app/workers/stages/validate.py`
- [x] 5.7 Register semua processors di worker `main.py`
- [x] 5.8 Tambah `pdfminer.six`, `fastembed`, `qdrant-client` ke dependencies

## 6. Shared Contracts

- [x] 6.1 Tambah Zod schema `modelProfileCreateSchema` di `packages/schemas/profiles.ts`
- [x] 6.2 Tambah Zod schema `indexProfileCreateSchema` di `packages/schemas/profiles.ts`
- [x] 6.3 Tambah response types `ModelProfileResponse`, `IndexProfileResponse` di `packages/types/profiles-response.ts`

## 7. Frontend — Model & Index Profile UI

- [x] 7.1 Tambah hooks: `useModelProfiles`, `useCreateModelProfile`, `useDeleteModelProfile`
- [x] 7.2 Tambah hooks: `useIndexProfiles`, `useCreateIndexProfile`, `useActivateIndexProfile`
- [x] 7.3 Buat halaman `/console/settings/models` — list + create + delete model profiles
- [x] 7.4 Buat halaman `/console/settings/index-profiles` — list + create + set active
- [x] 7.5 Update Settings nav dengan submenu Models dan Index Profiles

## 8. Environment & Config

- [x] 8.1 Tambah env vars ke `.env.example`: `OPENAI_API_KEY`, `OLLAMA_BASE_URL`, `FASTEMBED_CACHE_DIR`
- [x] 8.2 Tambah env vars ke `apps/api/app/core/settings.py`
- [x] 8.3 Update `apps/api/.env` dengan default FastEmbed config untuk dev

## 9. OpenAPI & Verification

- [x] 9.1 Regenerate `docs/openapi.json`
- [x] 9.2 Run `bun run typecheck` (web) — no errors
- [x] 9.3 Run `bun run lint` (web) — no errors
- [x] 9.4 Run `bun run test` (api) — all pass
- [x] 9.5 Test end-to-end: create model profile → create index profile → set active → upload PDF → pipeline READY
