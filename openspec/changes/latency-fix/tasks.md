## 1. Backend query path — bounded parallelism + resource reuse

- [x] 1.1 Paralelkan tahap independen di `rag_query_service.py:261,303,311,320,355-356` dengan TaskGroup/semaphore (4-6) + timeout per cabang + fail-soft opsional; retrieval/generation tetap wajib; verifikasi tenant scope + response shape tidak berubah.
- [x] 1.2 Ganti `create_session_factory` per call (`provider_resolver.py:33`, `rag_query_service.py:902`, `rag_health.py:62`) dengan singleton `_session_factory` dari `database.py:139` / lifespan; tiap request tetap pinjam session dari pool.
- [x] 1.3 Pindahkan trace/audit write (`rag_query_service.py:1124,1144,1160,1305,1318`, `mcp_runtime_service.py:234`) ke background (`BackgroundTasks`/`create_task` + log gagal + trace ID); tambah test: respons tidak menunggu commit trace.
- [x] 1.4 Hilangkan N+1: `memory_retriever.py:153-154` → batch `WHERE IN`; loop otorisasi `rag_query_service.py:1335-1336` → batch/gather terbatas; `similar_documents_service.py:69-90` → gather `generations`+`profile`.
- [x] 1.5 Batasi `rag_catalog.py:886-905` dengan `LIMIT` + pagination; `similar_documents_service.py:100-106` hanya load katalog untuk version_id hasil retrieval; tambah indeks komposit aditif bila belum ada.

## 2. Provider / Qdrant / MCP — timeout, retry, dan anti-hang

- [x] 2.1 `ollama_provider.py:21-29`: satu `AsyncClient` + paralel terbatas (semaphore 4) + error per-teks terisolasi; pertahankan tanpa cache antar tenant.
- [x] 2.2 `fastembed_provider.py:37-56`: bungkus `embed/encode_sparse` dengan `asyncio.to_thread`, cache `SparseTextEmbedding`, jangan load model per call.
- [x] 2.3 `openai_provider.py:28-29` + `embedding_adapter.py:37` + `generation_adapter.py:179`: shared client via lifespan, timeout eksplisit + 1x retry idempotent dengan jitter; tidak ada hang 30s di query path.
- [x] 2.4 `qdrant.py:29-37,94-105` + `dependencies.py:126`: shared `httpx.AsyncClient` dengan pool limit + `aclose`, timeout query 5-8s, retry 1x read; `provision_payload_indexes` ke startup/background.
- [x] 2.5 `mcp_runtime_service.py:159-234` + `connection_manager.py:16-33`: cache `list_tools` per server (TTL + hormati `freshness_seconds`), satu `wait_for` (hapus ganda), budget per-server + circuit-breaker; satu server hang tidak menenggelamkan query.
- [x] 2.6 `docling_serve_adapter.py:69,162-177`: fixed 3s → exponential backoff + jitter + batal saat disconnect; timeout total tetap.

## 3. Frontend console — akhiri fan-out, perbaiki BFF dan sinyal selesai

- [x] 3.1 Agregasi polling: ganti N `useRagIngestionStatus` per `version-card.tsx:28` menjadi satu `useIngestionStatuses(ids)` di `ingestion-content.tsx:437` (1 req/interval, `refetchIntervalInBackground:false`, backoff error, stop saat terminal, stop saat tab hidden).
- [x] 3.2 `use-documents.ts:17-26` + `ingestion-content.tsx:344`: tambah `page/page_size` + `useInfiniteQuery`/windowing; samakan dengan `use-memory`/`use-confidence` yang sudah paginated.
- [x] 3.3 `proxy/[...path]/route.ts:188-254`: dedup refresh (singleflight promise-cache) + retry max 1x; `interceptor.ts:63-75` + `interceptor-wo-version.ts:51-53` wajib reject (jangan `new Promise(()=>{})`) agar react-query masuk error state.
- [x] 3.4 `use-rag-query-stream.ts:52-53,182-199,411-416`: typewriter adaptif (chars/tick ∝ backlog) + flush langsung saat `response.completed`; konten akhir identik, sinyal selesai akurat.
- [x] 3.5 `review-content.tsx:71-80` + `console-guard.tsx:17-24`: hilangkan early-return blocking penuh; biarkan panel independen (similar/meta/editor) progressive render; `page.tsx:12` Suspense tetap.
- [x] 3.6 Terapkan polling budget global: `use-needs-review-count` 30s + `use-readiness` 30s + `useCalibrationStatus` 2s semuanya visibility-aware + `staleTime` eksplisit; tidak ada poller permanen saat tidak dilihat.

## 4. SLO, observability, dan docs

- [x] 4.1 Tambah span/metric: per-cabang paralel ms, `db_pool_wait`, `qdrant_ms`, `embed_ms`, `trace_async_fail`, `poll_req_per_min`; manfaatkan `tracer.emit("query.plan")` yang ada.
- [x] 4.2 Tulis `docs/latency-fix.md` (win-win: tiap optimasi + apa yang dipertahankan + tradeoff yang dihindari + cara ukur).
- [x] 4.3 Jalankan `openspec validate --change latency-fix`, `bun run build`, `cd apps/web && bun run test`, `cd apps/api && bun run test` (atau `uv run pytest` sesuai repo), dan verifikasi tidak ada perubahan kontrak OpenAPI (`docs/openapi.json`).
