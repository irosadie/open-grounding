# Design: RAG Retrieval BM25

## Context

`RagHybridRetrievalService` (in `rag_hybrid_retrieval.py`) already runs dense vector +
SPLADE sparse search in parallel via `asyncio.gather` against Qdrant. Results go to
rerank then evidence selection.

BM25 augments this with token-based lexical scoring. The cleanest approach that keeps
a single vector engine is to use Qdrant **sparse vectors** carrying BM25-compatible
weights (SPLADE/BM25-ish) and fuse with dense via Reciprocal Rank Fusion.

> Decision: implement **fusion over Qdrant sparse vectors** as BM25-lexical source by
> default. Keep an adapter seam so a real `rank_bm25` inverted index can be swapped in.

## Architecture

### Config (extends IndexProfile)

```python
@dataclass(frozen=True)
class RetrievalConfig:
    index_profile_id: str
    dense_weight: float          # default 1.0
    sparse_weight: float         # default 1.0  (SPLADE/BM25-lexical)
    fusion_k: int                # RRF k, default 60
    dense_candidates: int        # default 50
    sparse_candidates: int       # default 50
    fused_candidates: int        # default 40
    reranker_candidates: int     # default 24
    bm25_k1: float | None        # reserved (real BM25), default None → use sparse weights
    bm25_b: float | None
    enabled: bool
```

Stored as a new table `rag_retrieval_configs` (1:1 with index profile) OR as JSON on
the index profile. Decision: separate table for forward-compat + settings UI.

### Fused Retrieval

1. Run dense search → ranked list D (id, dense_score)
2. Run sparse/BM25 search → ranked list S (id, sparse_score)
3. Normalize each list to ranks
4. RRF: `score(id) = sum( 1/(k + rank_dense(id)) * dense_weight, 1/(k + rank_sparse(id)) * sparse_weight )`
5. Cap to `fused_candidates`
6. Return as standard chunk list (id, score) → downstream unchanged

### Repr

Reuse `EvidenceContext`:
writes.

## Decisions

### Fusion over single-index stores

Using Qdrant sparse vectors for the lexical band avoids a second database and keeps
the corpus identical (same tenant + KB + generation filters). RRF is robust to score
scale differences between dense and sparse — no score calibration needed.

### Configurable weights

Exact-keyword queries benefit from higher `sparse_weight`; semantic queries from higher
`dense_weight`. Per index profile so a support KB and a legal KB tune differently.

### Plug for real BM25

If the SPLADE beats are insufficient for exact-term recall (rare IDs/codes), a
`rank_bm25` inverted index can be added behind the same `SearchAdapter` without changing
the fusion logic.

## Risks / Trade-offs

- [SPLADE sparse ≠ true BM25] — `_b`em coverage of rare terms. Mitigated by pluggable adapter; document the difference.
- [Fusion adds latency] — second Qdrant query. Mitigated by parallel `asyncio.gather` (already parallel).
- [Weight tuning] — naive weights hurt both bands. Mitigated by config + eval.

## Open Questions

- Should sparse search use raw SPLADE vectors (already stored) or a separate BM25-weight
  sparse index per term? Lean: reuse existing sparse vectors, treat as lexical band.
