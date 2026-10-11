# Latency Fix — Pendekatan Production-Grade yang Win-Win

Dokumen ini menjelaskan **cara** menurunkan latency RAG + console tanpa mengorbankan korektness, isolasi tenant, auditability, UX, atau stabilitas upstream. Prinsipnya: **setiap milidetik yang dipotong harus dibayar dengan teknik, bukan dengan memotong jaminan.**

OpenSpec change: `openspec/changes/latency-fix/` (proposal, `specs/rag-latency-slo/spec.md`, design, tasks).

## 1. Prinsip win-win

1. **Kontrak tidak berubah.** Bentuk JSON/SSE, path endpoint, klaim JWT, filter tenant/kebijakan, dan relevansi ranking tetap. Yang berubah hanya *cara eksekusi* (paralel, batch, pool).
2. **Bounded, bukan liar.** Setiap paralelisasi dibatasi semaphore (4-6), timeout per cabang, dan retry max 1x + jitter hanya untuk read idempotent. Tanpa ini, latency turun saat sepi tapi meledak saat ramai (thundering herd, OOM, stampede upstream).
3. **Wajib vs opsional dibedakan.** Retrieval/generation wajib berhasil; memory/decomposition/planner/MCP opsional boleh fail-soft ke `{triggered:false}` + log. Query tidak boleh gagal hanya karena cabang hiasan timeout.
4. **Jangan pindah antrean, hilangkan antrean.** Trace/audit dipindah ke background *setelah* respons dimulai, bukan dihapus. Polling N→1 (agregat), bukan dimatikan.
5. **Ukur dulu.** Setiap klaim latency harus punya span/metric sebelum/sesudah: `query.plan ms` (sudah ada via `tracer.emit`), plus `db_pool_wait`, `qdrant_ms`, `embed_ms`, `trace_async_fail`, `poll_req_per_min`.

## 2. Backend query path: dari sum menjadi max

**Masalah:** `apps/api/app/application/rag_query_service.py:261,291,303,311,320,355-356` menjalankan 6 tahap independen secara serial. Total = jumlah semua RTT.

**Pendekatan aman:**

- Jalankan `recent_messages`, `retrieve_memory`, `decomposition_meta`, `planner_meta`, `authorized_ids+generation` dalam `TaskGroup`/`gather` dengan semaphore 4-6.
- Tiap cabang punya timeout sendiri (mis. memory 2s karena sudah ada `wait_for(2s)` di `memory_retriever.py:39`; planner/decomp ikut budget LLM).
- Opsional gagal → fallback kosong + catat trace; wajib gagal → gagalkan query seperti biasa.
- Urutan semantik dipertahankan: `save_turn(user)` tetap setelah guardrail lolos, sebelum retrieval — yang diparalelkan hanya bacaan independen, bukan urutan tulis.

**Yang dipertahankan:** tenant scope, policy filter Qdrant, bentuk `decomposition_meta.effectivePolicy`, dan `trace_id` di semua cabang.
**Tradeoff yang dihindari:** `gather` tanpa batas → N query DB/LLM bersamaan saat trafik naik. Semaphore + pool limit mencegahnya.

## 3. Resource reuse: singleton + pool + lifecycle eksplisit

**Masalah:**

- `apps/api/app/application/provider_resolver.py:33`, `apps/api/app/application/rag_query_service.py:902`, `apps/api/app/infrastructure/rag_health.py:62` membuat `create_session_factory(settings)` per panggilan (TCP+pool init berulang). Singleton `_session_factory` sudah ada di `apps/api/app/infrastructure/database.py:139` — tinggal pakai.
- `apps/api/app/interfaces/http/dependencies.py:126`, `apps/api/app/infrastructure/providers/ollama_provider.py:21`, `apps/api/app/infrastructure/generation_adapter.py:179` membuat `httpx.AsyncClient`/`AsyncOpenAI` per request tanpa `aclose` → leak koneksi + handshake berulang.
- `apps/api/app/infrastructure/providers/fastembed_provider.py:37-40,48` menjalankan inferensi ONNX di event loop + load `SparseTextEmbedding` per call → blokir seluruh worker async.

**Pendekatan aman:**

- Session factory singleton via lifespan; tiap request tetap pinjam `AsyncSession` sendiri dari pool (tidak ada session dipakai lintas request).
- `httpx.AsyncClient` + Qdrant + OpenAI client via FastAPI lifespan/dependency dengan `limits=max_connections` + `aclose` saat shutdown.
- Timeout read path dipendekkan untuk query (5-8s, bukan 30s); retry max 1x + jitter hanya untuk operasi idempotent (Qdrant query, GET). Write tidak di-retry buta.
- `FastEmbed` dibungkus `asyncio.to_thread` + model di-cache; `Ollama.embed` satu client + paralel terbatas (semaphore 4) dengan error per-teks terisolasi (satu teks gagal tidak menggagalkan batch).

**Yang dipertahankan:** batas transaksi per request, tidak ada state antar tenant, hasil embedding identik.
**Tradeoff yang dihindari:** cache hasil embedding antar tenant (risiko bocor data) — yang di-cache hanya model/konfig statis.

## 4. N+1 dan full-scan: batch + limit + indeks aditif

**Masalah:**

- `apps/api/app/application/memory_retriever.py:153-154` loop `find_by_id` per chunk → N RTT serial.
- `apps/api/app/application/rag_query_service.py:1335-1336` loop otorisasi KB serial.
- `apps/api/app/application/similar_documents_service.py:69-102` serial + `list_by_knowledge_base` tanpa `LIMIT` (`apps/api/app/infrastructure/rag_catalog.py:886-905`) → full scan KB besar + filter di Python.
- `apps/web/hooks/transactions/use-rag-ingestion/use-documents.ts:17-26` fetch list tanpa `page/page_size`.

**Pendekatan aman:**

- Ganti loop dengan `WHERE IN` 1 query; otorisasi + `generations/profile` via gather terbatas.
- `similar-documents` hanya load katalog untuk `version_id` yang muncul di hasil retrieval, bukan seluruh KB; tambah `LIMIT` di SQL + pagination di API + `useInfiniteQuery`/windowing di FE.
- Indeks komposit `(tenant_id, knowledge_base_id)`, `(tenant_id, chunk_id)` bersifat aditif dan backward-compatible; ukur write path agar tidak memperlambat ingestion.

**Yang dipertahankan:** hasil identik (hanya lebih sedikit baris ditransfer), tenant filter tetap di SQL, bukan di Python.
**Tradeoff yang dihindari:** menaikkan `LIMIT` raksasa agar "cepat" — justru OOM. Batasi + paginasi.

## 5. Trace/audit: keluar dari critical path, bukan dihapus

**Masalah:** `apps/api/app/application/rag_query_service.py:1124,1144,1160,1305,1318` melakukan 5-8 `commit+refresh` serial sebelum user dapat jawaban; `mcp_runtime_service.py:234` audit DB memblokir return.

**Pendekatan aman:**

- Tulis `answer_runs`, `trace_details`, `ensure_conversation/save_message`, audit MCP via `BackgroundTasks`/`asyncio.create_task` setelah respons/stream dimulai, dengan try/except + log + `trace_id`.
- Kegagalan trace tidak menggagalkan query; tercatat sebagai `trace_async_fail` untuk rekonsiliasi.
- Belakang flag `TRACE_ASYNC=true` agar bisa dimatikan cepat bila antrean menumpuk.

**Yang dipertahankan:** kelengkapan audit + `trace_id` di respons.
**Tradeoff yang dihindari:** menghapus trace demi cepat — itu menukar latency dengan hilangnya observability dan kepatuhan.

## 6. Upstream yang bisa hang: budget + circuit-breaker + backoff

- **Qdrant** (`apps/api/app/infrastructure/qdrant.py:94-105`): timeout pendek + 1x retry read; `provision_payload_indexes:29-37` pindah ke startup/background, bukan per query.
- **MCP** (`apps/api/app/application/mcp_runtime_service.py:159-234`, `infrastructure/mcp/connection_manager.py:16-33`): cache `list_tools` per server (TTL + hormati `freshness_seconds`), satu `wait_for` (hapus ganda dengan `http_client.py:30`), budget per-server + circuit-breaker (open setelah N gagal). Satu server hang tidak menenggelamkan query; tenant filter tetap server-side.
- **Docling** (`apps/api/app/infrastructure/rag/parsers/docling_serve_adapter.py:69,162-177`): fixed poll 3s → exponential backoff + jitter + batal saat disconnect; timeout total tetap 120s.
- **LLM generation:** budget lebih longgar dari retrieval, tapi tetap ada timeout + 1x retry; stream dimulai secepat `response.started`, bukan setelah semua trace selesai.

## 7. Frontend: N→1 polling, singleflight refresh, sinyal selesai yang jujur

**Masalah:**

- Tiap kartu (`apps/web/app/console/document/version-card.tsx:28`) memanggil `useRagIngestionStatus` dengan `refetchInterval: 3000` (`use-ingestion-status.ts:39-45`); parent me-render `versions.map` (`ingestion-content.tsx:437`) → 20 dokumen = ~400 req/menit via BFF buffering (`proxy/[...path]/route.ts:202-212`).
- Refresh token serial sebelum upstream (`proxy route:188-199`) + retry serial (`222-254`) → dekat expiry +1 RTT, expired 3 hop; N poller = N refresh paralel tanpa dedup.
- Interceptor 401 `return new Promise(()=>{})` (`services/axios/interceptor.ts:63-75`) → promise gantung, spinner selamanya.
- Typewriter `16ms x 3 char` + `pendingCompletionRef` (`use-rag-query-stream.ts:52-53,411-416`) → SSE selesai tapi UI `streaming` 10+ detik untuk jawaban panjang.
- List tanpa pagination + early-return blocking (`review-content.tsx:71-80`, `console-guard.tsx:17-24`) → TTI = query terlambat.

**Pendekatan aman:**

- Satu `useIngestionStatuses(ids)` di parent: 1 request/interval, `refetchIntervalInBackground:false`, backoff saat error, berhenti saat semua terminal, berhenti saat tab hidden. Kartu jadi presentasional. Freshness sama (interval tetap 3s), beban N→1.
- Refresh dedup via promise-cache (singleflight) per tick + retry max 1x; interceptor wajib `reject` agar react-query masuk error state + retry/error boundary jalan.
- Typewriter adaptif: `charsPerTick ∝ backlog` + flush langsung saat `response.completed`. Konten akhir identik, hanya sinyal selesai yang akurat.
- `use-documents` tambah `page/page_size` + infinite/windowing; review page progressive render (panel similar/meta/editor punya skeleton sendiri, tidak tertahan satu query); `ConsoleGuard` tidak menahan seluruh `children` saat sesi loading.
- Polling global (`needs-review 30s`, `readiness 30s`, `calibration 2s`) semuanya visibility-aware + `staleTime` eksplisit.

**Yang dipertahankan:** tidak ada status yang di-skip, tidak ada data yang tidak di-refresh saat dibutuhkan.
**Tradeoff yang dihindari:** mematikan polling (status basi) atau menaikkan interval ke 60s (UX basi) — agregat memberi keduanya: segar + murah.

## 8. Cara ukur (jangan percaya perasaan)

- Backend: bandingkan p50/p95 per span sebelum/sesudah — `query.plan`, cabang paralel, `qdrant_ms`, `embed_ms`, `db_pool_wait`, `trace_async_fail`.
- Frontend: `poll_req_per_min`, TTFB BFF, time-to-first-token SSE, time-to-`completed` (harus ≈ waktu SSE, bukan +10s), jumlah refresh/detik saat expiry.
- Guard regresi: test N+1 (assert 1 query untuk N chunk), test `LIMIT` (KB 10k dokumen tidak OOM), test interceptor 401 (promise reject), test typewriter (completed ≤ 500ms setelah SSE), lint `noExplicitAny`/`noConsole` tetap hijau, `docs/openapi.json` tidak berubah bentuk.

## 9. Checklist kontributor (agar tidak kambuh)

- [ ] Tidak ada `await` di dalam `for` di hot path? → batch/gather terbatas.
- [ ] Tidak ada `create_session_factory` / `AsyncClient()` / `AsyncOpenAI()` per request? → singleton/lifespan.
- [ ] Tidak ada CPU-bound di event loop? → `to_thread` + cache model.
- [ ] Tidak ada `select` tanpa `.limit()` di list? → limit + pagination + indeks.
- [ ] Tidak ada DB write di critical path respons? → background + log gagal.
- [ ] Tidak ada `refetchInterval` per kartu? → agregat di parent + visibility guard.
- [ ] Tidak ada `new Promise(()=>{})`? → reject/throw agar query selesai.
- [ ] Tidak ada sinyal `completed` yang tertahan animasi? → flush adaptif.
- [ ] Timeout + retry + jitter eksplisit untuk setiap upstream baru?
- [ ] Span/metric baru untuk setiap optimasi baru?
