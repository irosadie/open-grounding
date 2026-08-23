## Why

Pipeline ingestion saat ini stuck di stage `PARSING` karena tidak ada embedding model, chunking strategy, atau index profile yang dikonfigurasi. Semua tabel `rag_model_profiles` dan `rag_index_profiles` kosong.

Operator perlu bisa mengkonfigurasi model embedding, sparse encoder, reranker, dan generation model langsung dari UI — tanpa harus edit database atau env file. Sistem harus mendukung multi-provider (OpenAI, Ollama, FastEmbed/local), multimodal (text + image), dan fallback jika provider utama tidak tersedia.

## What Changes

- **API**: CRUD endpoints untuk `ModelProfile` (embedding dense, sparse, reranker, generation)
- **API**: CRUD endpoints untuk `IndexProfile` (kombinasi embedding + sparse + collection config)
- **API**: Set active profile per tenant
- **API**: Provider adapter layer — OpenAI, Ollama, FastEmbed — dengan fallback chain
- **UI**: Halaman `/console/settings/models` untuk manage model profiles
- **UI**: Halaman `/console/settings/index-profiles` untuk manage index profiles
- **Worker**: Queue processor `ingestion.embed` menggunakan active index profile
- **Worker**: Queue processor `ingestion.parse` menggunakan parser sesuai MIME type
- **Worker**: Queue processor `ingestion.chunk` dengan configurable chunking strategy
- **Worker**: Queue processor `ingestion.index` menulis ke Qdrant menggunakan active index profile

## Capabilities

### New Capabilities
- `model-profile-crud`: API + UI untuk create, list, update, delete model profiles (embedding dense, sparse, reranker, generation)
- `index-profile-crud`: API + UI untuk create, list, set-active index profiles
- `provider-adapter`: Abstraction layer untuk OpenAI, Ollama, FastEmbed dengan fallback chain
- `ingestion-pipeline-worker`: Full worker queue processors: parse → chunk → embed → index

### Modified Capabilities
- `rag-ingestion-ui`: Tambah indicator provider aktif di halaman Ingestion
- `rag-settings-ui`: Extend Settings page dengan model + index profile management

## Impact

- `apps/api/app/` — domain models, use cases, repository, routes untuk model/index profiles
- `apps/api/app/application/` — provider adapters (OpenAI, Ollama, FastEmbed)
- `apps/worker/src/` — queue processors untuk parse, chunk, embed, index stages
- `apps/web/app/console/settings/` — UI untuk model dan index profile management
- `apps/api/.env.example` — tambah provider env vars (OPENAI_API_KEY, OLLAMA_BASE_URL, dll)
- `packages/schemas/` + `packages/types/` — schema dan types untuk model/index profiles
- `docs/openapi.json` — regenerate
