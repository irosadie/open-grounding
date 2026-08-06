# Spec: RAG Retrieval BM25

## Overview

Adds a configurable BM25/lexical band fused with dense semantic search via Reciprocal
Rank Fusion, feeding the existing rerank/evidence pipeline. Config per index profile.

---

## Requirements

### REQ-1: RetrievalConfig

**REQ-1.1** The system SHALL provide a `RetrievalConfig` optional, attached 1:1 to an `IndexProfile`.

**REQ-1.2** `RetrievalConfig` SHALL contain:
- `dense_weight` (float, 0.0–5.0, default 1.0)
- `sparse_weight` (float, 0.0–5.0, default 1.0)
- `fusion_k` (int, 1–200, default 60)
- `dense_candidates` (int, 1–200, default 50)
- `sparse_candidates` (int, 1–200, default 50)
- `fused_candidates` (int, 1–200, default 40)
- `enabled` (bool, default true)

**REQ-1.3** If absent, the system SHALL use defaults equivalent to REQ-1.2.

**REQ-1.4** Deleting a `RetrievalConfig` SHALL revert the profile to defaults.

---

### REQ-2: Fused Retrieval

**REQ-2.1** The retrieval service SHALL run dense and sparse searches concurrently (`asyncio.gather`).

**REQ-2.2** Sparse search SHALL use Qdrant sparse vectors as the lexical band.

**REQ-2.3** Dense and sparse result lists SHALL each be rank-ordered (rank 1 = best).

**REQ-2.4** Fused score SHALL be computed as:
`score(id) = dense_weight/(k + rank_dense(id)) + sparse_weight/(k + rank_sparse(id))` where `k = fusion_k`.

**REQ-2.5** Only IDs present in either list SHALL appear in the fused list (missing band contributes 0).

**REQ-2.6** The fused list SHALL be capped at `fused_candidates`, sorted by fused score descending.

**REQ-2.7** The fused output SHALL have the same shape as current retrieval (chunk dicts with `id`, `score`) so downstream rerank/evidence pipeline is unchanged.

---

### REQ-3: Config API

**REQ-3.1** `GET /rag/index-profiles/{id}/retrieval` — get config (defaults if unset)

**REQ-3.2** `PUT /rag/index-profiles/{id}/retrieval` — upsert config

**REQ-3.3** `DELETE /rag/index-profiles/{id}/retrieval` — delete config, revert defaults

All endpoints SHALL be tenant-scoped and ADMIN-gated for writes.

---

### REQ-4: Shared Contracts

**REQ-4.1** Zod schema `retrievalConfigSchema` in `packages/schemas/`.

**REQ-4.2** Response type `RetrievalConfigResponse` in `packages/types/`.

---

### REQ-5: Frontend — Retrieval Profile UI

**REQ-5.1** The index profile settings page SHALL include a "Retrieval" section.

**REQ-5.2** UI SHALL allow editing `dense_weight`, `sparse_weight`, `fusion_k`, candidate counts, enabled toggle.

**REQ-5.3** UI SHALL validate bounds and show inline errors.

---

### REQ-6: Verification

**REQ-6.1** Unit tests for RRF fusion math (weights, k, missing-band, cap, ties).

**REQ-6.2** Integration test: fused retrieval returns results when dense misses but sparse hits.

**REQ-6.3** All existing tests pass.
