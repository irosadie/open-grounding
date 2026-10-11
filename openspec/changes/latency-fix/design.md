## Context

Hot path saat ini membayar penjumlahan latensi: `rag_query_service.py:261,291,303,311,320,355-356` serial 6 tahap; `provider_resolver.py:33` + `rag_query_service.py:902` membuat session factory per call; `ollama_provider.py:21-29` loop serial; `fastembed_provider.py:37-40,48` blocking event loop; `memory_retriever.py:153-154` N+1; `similar_documents_service.py:69-102` serial + `list_by_knowledge_base` tanpa limit (`rag_catalog.py:886-905`); trace 5-8 commit serial (`rag_query_service.py:1124,1144,1160,1305,1318`); Qdrant tanpa retry/timeout pendek (`qdrant.py:94-105`, `dependencies.py:126`); MCP lock serial + spawn per server. Frontend: fan-out `use-ingestion-status.ts:39-45` per `version-card.tsx:28`, BFF buffering `proxy/[...path]/route.ts:202-212`, refresh serial `188-199,222-254`, interceptor gantung `interceptor.ts:63-75`, typewriter gate `use-rag-query-stream.ts:52-53,411-416`, list tanpa pagination `use-documents.ts:17-26`. Lihat `proposal.md` dan `specs/rag-latency-slo/spec.md` untuk perilaku yang dijanjikan.

## Goals / Non-Goals

**Goals:**

- Potong p50/p95 query + ingestion-status + TTFB console tanpa mengubah kontrak API, isolasi tenant, filter kebijakan, atau bentuk SSE/JSON.
- Setiap paralelisasi bersifat bounded (semaphore + timeout + fail-soft) agar tidak menukar latency dengan OOM, stampede upstream, atau inkonsistensi.
- Setiap resource reuse (session, HTTP client, model) bersifat singleton/pool dengan lifecycle eksplisit (lifespan/di-close).
- Trace/audit tetap lengkap tapi tidak di critical path.

**Non-Goals:**

- Tidak mengubah model auth, expiry token, klaim JWT, atau path endpoint.
- Tidak mengubah ranking/retrieval relevance, chunking, atau prompt generation — hanya cara eksekusinya.
- Tidak memindah workload ke edge runtime; tetap `nodejs` BFF + FastAPI.
- Tidak menambah cache semantik yang bisa membocorkan data antar tenant; cache hanya untuk model/konfig statis atau hasil dengan kunci tenant+resource+version.

## Decisions

- **Bounded gather, bukan `gather` liar:** independen (`recent_messages`, `retrieve_memory`, `decomposition_meta`, `planner_meta`, `authorized_ids`+`generations`) dijalankan via `asyncio.TaskGroup`/`gather` dengan semaphore (mis. 4-6) + timeout per cabang (memory 2s, planner/decomp sesuai budget LLM). Opsional fail-soft ke `{triggered:false}`; retrieval/generation wajib. Menang: latency = max(cabang), bukan sum. Aman: tidak ada thundering herd ke DB/LLM.
- **Singleton session + shared HTTP client:** gunakan `_session_factory` yang sudah ada di `database.py:139` (jangan `create_session_factory` per call); `httpx.AsyncClient` + `AsyncOpenAI` + Qdrant client via FastAPI lifespan/dependency dengan `limits=max_connections` + `aclose`. Timeout read path dipendekkan (query 5-8s, bukan 30s); retry max 1x + jitter hanya untuk GET/query idempotent. Menang: hemat handshake + tidak bocor. Aman: tidak mengubah transaksi; tiap request tetap dapat session sendiri dari pool.
- **N+1 → batch + limit:** `memory_retriever` pakai `WHERE chunk_id IN (...)`; otorisasi KB pakai batch/gather terbatas; `similar_documents_service` hanya load katalog untuk `version_id` yang muncul di hasil retrieval (bukan full `list_by_knowledge_base`), plus `LIMIT` di `rag_catalog.py` dan pagination `page/page_size` di `use-documents`. Tambah indeks komposit `(tenant_id, knowledge_base_id)` / `(tenant_id, chunk_id)` bila belum ada (aditif). Menang: O(1) RTT. Aman: hasil identik, hanya lebih sedikit baris yang ditransfer.
- **Trace async after-response:** `answer_runs.create`, `trace_details.*`, `ensure_conversation/save_message`, MCP audit dipindah ke `asyncio.create_task`/`BackgroundTasks` setelah respons/stream dimulai, dengan try/except + log + trace ID. Query tidak `await` 5-8 commit. Menang: hemat 5-8 RTT di critical path. Aman: audit tetap ditulis; kegagalan tidak menggagalkan jawaban dan bisa direkonsiliasi.
- **Embedding aman-CPU:** `FastEmbed.embed/encode_sparse` dibungkus `asyncio.to_thread` + `SPLADE` model di-cache (jangan load per call); `Ollama.embed` satu `AsyncClient` + paralel terbatas (semaphore 4) + error per-teks terisolasi. Menang: event loop tidak terblokir. Aman: hasil embedding identik, tidak ada shared mutable state.
- **Qdrant + MCP budget:** `provision_payload_indexes` jalan saat startup/background (bukan per query); `_query` timeout pendek + 1x retry read; MCP `list_tools` di-cache per server dengan TTL + `freshness_seconds` benar-benar dicek, `call_tool` satu `wait_for` (jangan ganda) + circuit-breaker per server (open setelah N gagal berurutan) + budget total MCP per query. Menang: satu server hang tidak menenggelamkan query. Aman: tenant filter tetap diterapkan server-side.
- **Docling poll backoff:** `docling_serve_adapter.py:69,162-177` dari fixed 3s → exponential backoff + jitter (mis. 1s→2s→4s max 8s) + timeout total tetap 120s + batal saat client disconnect. Menang: lebih responsif untuk dokumen cepat, hemat request. Aman: tidak ada polling ketat yang membanjiri parser.
- **Frontend agregat + singleflight + flush adaptif:** satu `useIngestionStatuses(ids)` di parent (`ingestion-content.tsx`) dengan 1 interval + `refetchIntervalInBackground:false` + backoff error + stop saat semua terminal; kartu jadi presentasional. Refresh token di BFF pakai promise-cache per `jti`/per tick (singleflight) agar N poller tidak N refresh. Interceptor 401 `reject` (bukan `new Promise(()=>{})`). Typewriter adaptif: `charsPerTick = f(backlog)` + langsung flush + `onCompleted` saat `response.completed` (konten sama, sinyal tepat). `use-documents` tambah pagination/`useInfiniteQuery` + windowing render. Menang: request/menit turun order-of-magnitude, TTI akurat. Aman: tidak ada data yang di-skip; polling tetap hidup saat dibutuhkan.
- **Observabilitas dulu:** manfaatkan `tracer.emit("query.plan", ms=...)` yang ada + tambah span per cabang paralel dan metric `db_pool_wait`, `qdrant_ms`, `embed_ms`, `trace_async_fail`. Tanpa metric, optimasi buta.

## Risks / Trade-offs

- [Risk] Paralel DB/LLM menaikkan concurrency sesaat. → Mitigasi: semaphore 4-6 + pool limit + timeout per cabang; load test dengan KB besar sebelum naik.
- [Risk] Trace async bisa hilang saat crash sebelum flush. → Mitigasi: log gagal + retry ringan + pertahankan trace ID di respons agar bisa direkonsiliasi; bukan hapus trace.
- [Risk] Timeout pendek memotong query lambat yang valid. → Mitigasi: budget per jenis (retrieval 5-8s, LLM generation lebih longgar), retry 1x read idempotent, fallback kosong hanya untuk cabang opsional.
- [Risk] Agregat polling menunda status satu dokumen. → Mitigasi: interval sama (3s) tapi 1 request; freshness identik, beban N→1.
- [Risk] Indeks baru memperlambat write. → Mitigasi: indeks komposit sempit + ukur write path ingestion; indeks aditif dan bisa di-rollback.

## Migration Plan

1. Mendaratkan perubahan non-skema dulu (bounded gather, singleton, to_thread, agregat polling, interceptor, typewriter) — tanpa migrasi, bisa rollback per file.
2. Tambah indeks DB aditif + `LIMIT`/pagination (baca tetap kompatibel dengan data lama).
3. Pindahkan trace ke background di belakang flag/env (mis. `TRACE_ASYNC=true`) agar bisa dimatikan cepat bila antrean menumpuk.
4. Ukur p50/p95 per span (tracer + metric) sebelum/sesudah; jika regresi, kembalikan flag tanpa deploy ulang skema.
5. Dokumentasikan pola di `docs/latency-fix.md` agar kontributor baru tidak mengembalikan N+1/fan-out.
