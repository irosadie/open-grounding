# rag-latency-slo Specification

## Purpose
Sistem menjawab query RAG dan memantau ingestion dalam anggaran latency yang aman, tanpa mengorbankan korektness, isolasi tenant, auditability, atau stabilitas upstream. Optimasi bersifat win-win: paralelisasi terbatas, pooling, dan degradasi anggun, bukan shortcut yang memotong keamanan atau observability.

## ADDED Requirements
### Requirement: Query path memenuhi anggaran latency dengan paralelisasi terbatas
The system SHALL serve RAG query path (plan → retrieve → generate → stream first-token) within defined budgets by running independent stages concurrently under a bounded semaphore with per-branch timeouts, while preserving tenant scope, policy filter, and response shape.

#### Scenario: Tahap independen berjalan paralel
- **WHEN** query masuk dengan memory, decomposition, planner, dan otorisasi KB yang independen
- **THEN** sistem menjalankannya secara konkuren (bukan serial 6x await) dan total latency mendekati tahap terlambat, bukan penjumlahan semua tahap

#### Scenario: Cabang opsional gagal atau timeout
- **WHEN** cabang opsional (memory/decomposition/planner) timeout atau error dalam budgetnya
- **THEN** query tetap lanjut dengan fallback kosong + penanda `triggered:false`, retrieval/generation wajib tidak di-skip, dan kegagalan tercatat dengan trace ID

### Requirement: Tidak ada N+1 dan full-scan di hot path
The system SHALL NOT issue per-item queries in a loop on hot paths; it MUST batch via `WHERE IN` (or equivalent) and enforce `LIMIT`/pagination on catalog/list endpoints. Large knowledge bases MUST NOT trigger unbounded full-table loads.

#### Scenario: Memory chunk lookup
- **WHEN** memory retriever mendapat N chunk_id dari Qdrant
- **THEN** sistem mengambil ringkasan dalam 1 batch query, bukan N `find_by_id` serial

#### Scenario: Similar-documents dan list dokumen
- **WHEN** similar-documents atau daftar dokumen diminta untuk KB besar
- **THEN** sistem hanya memuat kandidat terbatas (bounded limit + pagination), bukan seluruh `list_by_knowledge_base` tanpa limit

### Requirement: Resource eksternal dipakai dengan pooling, timeout, dan retry aman
The system SHALL reuse singletons/pools for DB session factory and HTTP clients, apply short timeouts on read/query path, and retry at most once with jitter only for idempotent reads. CPU-bound embedding MUST NOT block the event loop.

#### Scenario: Embedding dan Qdrant di bawah tekanan
- **WHEN** Ollama/OpenAI/Qdrant lambat atau gagal sekali
- **THEN** query gagal-cepat dalam budget (bukan hang 30s), koneksi tidak bocor (client di-close/di-pool), dan FastEmbed berjalan di worker thread dengan model ter-cache

#### Scenario: MCP server hang
- **WHEN** satu MCP server hang atau handshake lama
- **THEN** query tidak membayar penalti penuh `timeout_seconds`; eksekusi tool dibatasi budget per-server dengan circuit-breaker dan degradasi anggun

### Requirement: Trace/audit tidak memblokir respons user
The system SHALL persist answer runs, trace details, conversation turns, and MCP audit records asynchronously after the user-visible response (or stream start), with failure logging that never fails the query.

#### Scenario: Trace write lambat
- **WHEN** DB lambat saat menulis trace
- **THEN** user tetap menerima jawaban/stream tepat waktu; trace yang gagal tercatat untuk rekonsiliasi tanpa mengubah jawaban

### Requirement: Console polling dan BFF tidak menimbulkan fan-out
The system SHALL bound frontend polling fan-out (single aggregated poller for ingestion lists, visibility-aware, backoff on error) and SHALL NOT hang queries on auth refresh or 401 handling. Stream completion MUST surface promptly without artificial typewriter backlog.

#### Scenario: 20 dokumen ingestion aktif
- **WHEN** 20 dokumen non-terminal ditampilkan
- **THEN** browser mengirim maksimal 1 agregat poll per interval (bukan 20 request/3 detik), berhenti saat semua terminal, dan tidak mem-poll saat tab hidden

#### Scenario: Token hampir expired dan 401
- **WHEN** access token dekat expiry atau upstream 401
- **THEN** refresh didedup (singleflight), retry maksimal 1x, dan interceptor menolak promise (agar react-query masuk error state) bukan menggantung selamanya

#### Scenario: Stream selesai
- **WHEN** SSE `response.completed` tiba sementara antrean typewriter masih ada
- **THEN** UI mempercepat drain (adaptive) dan menandai selesai tanpa menunggu 10+ detik animasi; konten akhir identik, hanya waktu sinyal yang akurat
