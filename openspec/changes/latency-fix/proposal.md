# Proposal

## Why

Query RAG dan console ingestion terasa lambat bukan karena satu query berat, tapi karena penjumlahan latensi serial: 6 tahap independen di `rag_query_service.py` dijalankan berurutan, provider embedding/Qdrant dibuka-tutup per panggilan, N+1 query DB, trace write 5-8x commit memblokir respons, dan frontend melakukan fan-out polling (N kartu x 3 detik) lewat BFF yang buffering penuh plus typewriter gate buatan. Perlu perbaikan latency yang tidak mengorbankan korektness, isolasi tenant, auditability, atau UX.

## What Changes

- Paralelisasi terbatas (bounded) tahap independen query path dengan timeout + fail-soft, tanpa mengubah urutan semantik dan tenant scope.
- Singleton/pooling untuk `AsyncSession` factory, `httpx.AsyncClient`, dan provider client; timeout pendek untuk read path + 1x retry idempotent dengan jitter.
- Hilangkan N+1 (`memory_retriever`, otorisasi KB, similar-documents) via `WHERE IN` + batasi `LIMIT`/pagination di `rag_catalog` dan `use-documents`.
- Pindahkan trace/audit write ke background (after-response) dengan logging gagal yang aman; respons user tidak menunggu commit trace.
- CPU-bound embedding (`FastEmbed`) ke `asyncio.to_thread` + cache model; `Ollama` embed batch paralel terbatas dengan satu client.
- Frontend: agregasi polling ingestion (satu poller di parent, bukan per kartu), visibility-aware + backoff, dedup refresh token (singleflight), perbaiki interceptor 401 agar reject bukan gantung, dan typewriter adaptif yang langsung flush saat `completed`.
- Tambah SLO latency + guardrail regresi (anggaran p50/p95, larangan N+1 baru, batas fan-out polling).

## Capabilities

### New Capabilities
- `rag-latency-slo`: anggaran latency query/ingestion/console dan guardrail anti-regresi (bounded concurrency, timeout budget, no-N+1, polling budget). Ini perilaku sistem yang durable, bukan tugas implementasi.

### Modified Capabilities
- Tidak ada perubahan requirement fungsional. Semua capability eksisting (`rag-grounded-answer-generation`, `rag-hybrid-retrieval-and-ranking`, `rag-retrieval-conversation-ui`, `ingestion-review-ui`, `fastapi-api-runtime`) tetap berlaku; change ini hanya memenuhi SLO tanpa mengubah kontrak API, klaim token, isolasi tenant, atau bentuk respons.

## Impact

- `apps/api/app/application/rag_query_service.py`, `memory_retriever.py`, `similar_documents_service.py`, `provider_resolver.py`, `mcp_runtime_service.py`
- `apps/api/app/infrastructure/database.py`, `qdrant.py`, `embedding_adapter.py`, `generation_adapter.py`, `providers/*`, `rag_catalog.py`, `rag/parsers/docling_serve_adapter.py`
- `apps/web/app/api/proxy/[...path]/route.ts`, `app/api/stream/[...path]/route.ts`, `services/axios/interceptor*.ts`, `hooks/transactions/use-rag-ingestion/*`, `hooks/transactions/use-rag-query/use-rag-query-stream.ts`, `app/console/document/*`
- `docs/latency-fix.md` sebagai panduan win-win agar optimasi tidak mengorbankan hal lain.
- Tidak ada perubahan skema API publik, tidak ada migrasi destruktif; indeks DB baru bersifat aditif dan backward-compatible.
