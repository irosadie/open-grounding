# Design: RAG Query Decomposition

## Context

The grounded query pipeline shipped in `rag-grounded-query` handles single-intent queries
well. Query decomposition was explicitly deferred until an evaluation-gated implementation
could be proposed. This change delivers that implementation.

The existing pipeline is:
```
query → retrieve (Qdrant hybrid) → rerank → generate (LLM stream) → trace
```

Query decomposition extends this with an optional pre-retrieval stage:
```
query → [complexity score] → [LLM decompose] → parallel retrieve → dedup/merge → generate → trace
```

## Architecture

### New Entity: DecompositionConfig

Attached 1:1 to a KnowledgeBase. Optional — if absent, KB uses standard pipeline.

```python
@dataclass(frozen=True)
class DecompositionConfig:
    id: str
    tenant_id: str
    knowledge_base_id: str
    enabled: bool
    model_profile_id: str          # FK → ModelProfile (LLM, not embedding)
    system_prompt: str             # Jinja2 template
    user_prompt_template: str      # Jinja2 template, must render sub-queries list
    max_sub_queries: int           # 1–5, default 3
    max_depth: int                 # 1–3, default 2
    min_complexity_score: float    # 0.0–1.0, default 0.6
    guardrails: dict               # extensible JSON
    created_at: datetime
    updated_at: datetime
```

### Complexity Scorer

Lightweight linguistic scorer — no LLM call, runs in <1ms.

Signals that increase complexity score:
- Conjunction keywords: "dan", "serta", "also", "and", "versus", "compared to"
- Comparison patterns: "perbedaan antara", "difference between", "X vs Y"
- Multi-entity detection: >1 named entities or quoted terms
- Causal/impact chains: "dampak", "impact", "effect of", "karena"
- Temporal multi-hop: "sebelum dan sesudah", "before and after"
- Question multiplicity: multiple `?` or coordinated interrogatives

Score is a float 0.0–1.0. If score < `min_complexity_score`, skip decomposition entirely.

### LLM Decomposer

Called only when complexity score >= threshold.

Input: rendered Jinja2 prompt with `{{ query }}`, `{{ max_sub_queries }}`, `{{ knowledge_base_name }}`

Output: structured list of sub-queries (JSON array), validated and bounded to `max_sub_queries`.

Default system prompt (overridable):
```
You are a query decomposition assistant. Given a complex user query, break it into
{{ max_sub_queries }} or fewer atomic sub-queries that can each be answered independently
from a document retrieval system. Return ONLY a JSON array of strings. No explanation.
```

Default user prompt template (overridable):
```
Query: {{ query }}
Knowledge base: {{ knowledge_base_name }}
Sub-queries (max {{ max_sub_queries }}):
```

### Parallel Sub-Retrieval

Each sub-query runs the existing `RagHybridRetrieval` independently via `asyncio.gather`.
No new retrieval logic — reuses existing dense + sparse + rerank pipeline per sub-query.

### Evidence Deduplication + Merge

After all sub-retrievals complete:
1. Collect all chunks across sub-queries
2. Dedup by chunk ID (exact match)
3. Score each unique chunk by max relevance score across sub-queries
4. Re-sort by merged relevance score
5. Apply global `top_k` cap (same as standard pipeline)

### Trace Integration

Extends existing `RagAnswerTrace` with decomposition metadata:

```python
decomposition: {
    "triggered": bool,
    "complexity_score": float,
    "sub_queries": ["...", "..."],
    "sub_evidence_counts": [3, 4, 2],
    "merged_evidence_count": 7,
    "dedup_removed": 2
}
```

All sub-queries and their evidence visible in trace viewer.

### Query API Change

`POST /rag/query` payload gains optional field:
```json
{
  "message": "...",
  "knowledge_base_ids": ["..."],
  "mode": "grounded",
  "stream": true,
  "decomposition": {
    "enabled": true,       // optional override, defaults to KB config
    "max_sub_queries": 3   // optional override
  }
}
```

If `decomposition` field absent → use KB config. If KB config absent → skip decomposition.

## Decisions

### Hybrid approach over pure LLM

Pure LLM decomposition adds ~200-500ms latency and cost to every query. Most queries
are simple. Linguistic pre-screening eliminates decomposition overhead for the majority
of requests while preserving full LLM power for genuinely complex ones.

### Per-KB config over global config

Different knowledge bases serve different domains. A legal KB needs different
decomposition behavior than a product FAQ KB. Global config forces a lowest-common-denominator
setting that works poorly for all domains.

### Reuse ModelProfile for LLM selection

The `ModelProfile` system already handles provider credentials, model selection, and
API key management. A separate "decomposition LLM" concept would duplicate all of that.
The only constraint: model must be a generation model (not embedding) — enforced at
config creation time.

### Jinja2 for prompt templates

Already in Python stdlib ecosystem. Supports variable injection, conditionals, and loops
if needed for advanced prompt engineering. Templates validated at save time.

### Dedup by chunk ID, rank by max score

Semantic dedup (cosine similarity threshold) is expensive and introduces a threshold
hyperparameter. Chunk ID dedup is deterministic, fast, and correct — the same chunk
retrieved by two sub-queries should appear once, scored by the best relevance it achieved.

## Risks / Trade-offs

- [LLM decomposer quality depends on model] — smaller models may produce poor sub-queries.
  Mitigated by allowing per-KB model selection and prompt customization.
- [Parallel retrieval increases Qdrant load] — N sub-queries = N retrieval calls concurrently.
  Bounded by `max_sub_queries` ≤ 5. Acceptable for current scale.
- [Complexity scorer false positives] — simple queries with "and" get scored as complex.
  Mitigated by tunable `min_complexity_score` threshold per KB.
- [Prompt injection via user query] — user query rendered in Jinja2 template.
  Mitigated by escaping query variable and validating template at save time.

## Open Questions

- Should `DecompositionConfig` be editable via API only, or also importable via YAML for
  infrastructure-as-code deployments?
- Should sub-query traces be queryable independently, or always nested under parent trace?
