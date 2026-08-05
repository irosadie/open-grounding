## Context

Pipeline ingestion butuh tiga komponen yang saat ini belum ada:

1. **Model profiles** — konfigurasi provider + model untuk embedding dense, sparse encoder, reranker, dan generation LLM
2. **Index profiles** — kombinasi model profiles + Qdrant collection config yang menjadi "blueprint" indexing
3. **Worker queue processors** — BullMQ workers yang mengeksekusi tiap stage pipeline menggunakan profile aktif

Saat ini semua tabel profile kosong dan worker hanya scaffold tanpa queue. Dokumen yang diupload stuck di `PARSING` selamanya.

## Goals / Non-Goals

**Goals:**
- CRUD model profiles (dense embedding, sparse encoder, reranker, generation)
- CRUD index profiles (set active per tenant)
- Provider adapters: OpenAI, Ollama, FastEmbed — dengan fallback chain
- Worker queue processors: parse → chunk → embed → index
- UI di Settings untuk manage profiles
- Multimodal support: text + image embedding (via provider yang mendukung)

**Non-Goals:**
- Fine-tuning atau training model
- Custom model hosting (hanya consume existing endpoints)
- Graph projection (Phase E)
- Evaluation pipeline (Phase D future)

## Decisions

### 1. Provider abstraction via adapter pattern

Setiap provider (OpenAI, Ollama, FastEmbed) mengimplementasi interface yang sama:

```python
class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str], model: str) -> list[list[float]]: ...
    async def health(self) -> bool: ...
```

Fallback chain dikonfigurasi di `IndexProfile.fallback_provider_ids` — jika provider utama gagal, sistem mencoba provider berikutnya. Fallback hanya berlaku untuk embedding, bukan generation.

### 2. Provider registry — singleton per app startup

Provider instances dibuat satu kali saat startup dan di-cache. Konfigurasi dibaca dari env + database. Tidak ada hot-reload provider — restart diperlukan jika env berubah.

### 3. Model profile kinds

```
DENSE_EMBEDDING   — text embedding (OpenAI, Ollama, FastEmbed)
SPARSE_EMBEDDING  — lexical sparse (SPLADE via FastEmbed, BM25)
RERANKER          — cross-encoder reranking (Cohere, local cross-encoder)
GENERATION        — LLM untuk answer generation (OpenAI, Ollama)
```

### 4. Index profile = kombinasi profiles + collection config

```
IndexProfile:
  embedding_profile_id   → ModelProfile (DENSE_EMBEDDING)
  sparse_profile_id      → ModelProfile (SPARSE_EMBEDDING) — nullable
  reranker_profile_id    → ModelProfile (RERANKER) — nullable
  collection             → Qdrant collection name
  dimensions             → harus match model output
  distance_metric        → COSINE | DOT | EUCLID
  version                → bump when config changes → triggers reindex
```

Satu tenant punya satu `active` index profile. Ganti active profile → trigger reindex semua dokumen.

### 5. Chunking strategy — per index profile

```
IndexProfile:
  chunking_strategy      → RECURSIVE | SENTENCE | FIXED | PARAGRAPH
  chunk_size_tokens      → default 400
  chunk_overlap_tokens   → default 50
  parent_chunk_size      → default 1500 (untuk parent-child)
```

Chunking strategy disimpan di index profile, bukan di env. Ganti strategy → reindex.

### 6. Worker stage architecture

```
ingestion.parse    → extract text dari file (PDF: pdfminer, MD: markdown-it, TXT: plain)
ingestion.chunk    → split text sesuai strategy dari active IndexProfile
ingestion.embed    → embed chunks menggunakan active IndexProfile.embedding_profile
ingestion.index    → upsert vectors ke Qdrant collection
ingestion.validate → verify count match, update lifecycle ke READY atau FAILED
```

Setiap stage membaca active IndexProfile saat job dieksekusi — bukan saat enqueue.

### 7. Multimodal — text-first, image as extension

V1 hanya text embedding. Image embedding (via OpenAI vision atau CLIP) ditambah sebagai optional field di ModelProfile (`modality: TEXT | IMAGE | MULTIMODAL`). Worker melewati image chunks jika provider tidak mendukung multimodal.

### 8. FastEmbed sebagai default local provider

FastEmbed (by Qdrant) jalan di CPU tanpa API key, mendukung dense + sparse (SPLADE). Ini default untuk development. OpenAI untuk production. Ollama untuk self-hosted LLM generation.

Default model:
- Dense: `BAAI/bge-small-en-v1.5` (FastEmbed, 384 dims)
- Sparse: `prithivida/Splade_PP_COO_1` (FastEmbed)
- Generation: `gpt-4o-mini` (OpenAI) atau `llama3.2` (Ollama)

## Risks / Trade-offs

- **Reindex on profile change** → expensive untuk large knowledge bases → mitigasi: soft switch dengan grace period
- **FastEmbed download on first run** → model ~100MB, butuh internet atau pre-cache → dokumentasikan di README
- **Ollama cold start** → first request slow → health check + warn user
- **Dimension mismatch** → jika model diganti tanpa reindex → Qdrant reject → handled di validate stage

## Migration Plan

1. Alembic migration: tambah `rag_model_profiles` dan `rag_index_profiles` columns baru
2. Seed default FastEmbed profiles via bootstrap script
3. Implement provider adapters (FastEmbed → OpenAI → Ollama)
4. Implement worker queue processors (parse → chunk → embed → index → validate)
5. Implement API CRUD endpoints
6. Implement UI di Settings
7. Update .env.example dengan provider env vars
8. Test end-to-end: upload PDF → pipeline selesai → status READY

## Open Questions

1. Apakah FastEmbed model harus di-download saat bootstrap atau lazy load saat pertama dipakai? → **Lazy load + warm-up job saat worker startup**
2. Apakah perlu UI untuk trigger manual reindex? → **Ya, tambah di Phase D**
3. Berapa max file size yang didukung V1? → **Ikut setting `RAG_INGESTION_MAX_FILE_SIZE` yang sudah ada**
