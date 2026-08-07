# Proposal: RAG Retrieval BM25

## Problem

The current retrieval uses dense vectors (and SPLADE sparse vectors) from Qdrant.
Dense semantic search is great for meaning but weak on exact-keyword, out-of-vocabulary,
and rare-term queries (IDs, codes, exact phrases, domain jargon). Adding a proper
**BM25 lexical index** fuses token-based matching with semantic vectors — significantly
improving recall for keyword-heavy queries.

This change adds a configurable BM25 inverted index alongside the existing vector search
and fuses results (Reciprocal Rank Fusion style, configurable weights).

## Proposed Solution

```
query
  → dense vector search (existing)
  → sparse/BM25 search (new, configurable)
  → RRF fusion (configurable k, weights, top-k cap)
  → rerank (existing gate_evidence)
```

## Key Design Decisions

- **Default BM25**: use Qdrant sparse vectors for BM25-style scoring (native, no extra index
  library), OR a dedicated inverted-index store — decided at design review. Lean Qdrant sparse
  to avoid a second engine, keeping the same corpus.
- **Customable**: BM25 `k1`, `b`, field weighting, fusion `k`, dense-vs-lexical balance, top-k caps — all per index profile config.
- **QLever/rank_bm25 option**: pluggable lexicon-free if Qdrant sparse isn't enough.
- **Configurable per index profile**: a KB can tune its retrieval profile.
- **Config default**: standard BM25++.

## What This Is Not

- Not a replacement for semantic search — an augmentation.
- Not the query planner (separate change).
- Not MCP.

## Success Criteria

- BM25 + dense fusion retrieves documents dense-only misses on keyword queries
- Fusion output feeds existing rerank + evidence pipeline unchanged shape
- Config UI per index profile for BM25 params
- Existing tests pass; new retrieval tests cover fusion

## Scope

**In scope:**
- BM25 config model + migration (index profile extension or separate config)
- BM25 retriever adapter + fused retrieval service
- Fusable scoring (sparse + dense normalized)
- Config API + UI (retrieval profile settings)
- Shared schemas/types
- Verification/tests

**Out of scope:**
- Query planner, MCP runtime
- Memory