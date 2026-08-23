# Spec: RAG Query Decomposition

## Overview

Query decomposition is an opt-in pre-retrieval stage that breaks complex multi-intent
queries into atomic sub-queries, retrieves evidence for each independently, deduplicates
and merges the evidence pool, then generates a grounded answer from the merged context.

---

## Requirements

### REQ-1: DecompositionConfig Entity

**REQ-1.1** The system SHALL provide a `DecompositionConfig` entity that is optionally
attached 1:1 to a `KnowledgeBase`.

**REQ-1.2** `DecompositionConfig` SHALL contain:
- `enabled` (bool) — master switch
- `model_profile_id` (FK → ModelProfile) — LLM used for decomposition; MUST reference a generation model, not an embedding model
- `system_prompt` (text) — Jinja2 template, validated at save time
- `user_prompt_template` (text) — Jinja2 template, validated at save time
- `max_sub_queries` (int, 1–5, default 3)
- `max_depth` (int, 1–3, default 2)
- `min_complexity_score` (float, 0.0–1.0, default 0.6)
- `guardrails` (JSON) — extensible, validated as object at save time

**REQ-1.3** Creating a `DecompositionConfig` with a `model_profile_id` that references
an embedding or sparse profile SHALL be rejected with error `INVALID_MODEL_PROFILE_KIND`.

**REQ-1.4** Jinja2 templates SHALL be validated for syntax errors at save time. Invalid
templates SHALL be rejected with error `INVALID_PROMPT_TEMPLATE`.

**REQ-1.5** `DecompositionConfig` SHALL be deletable. Deletion removes the config and
reverts the KB to standard pipeline.

---

### REQ-2: Complexity Scorer

**REQ-2.1** The system SHALL score query complexity using a lightweight linguistic scorer
that runs without any LLM call.

**REQ-2.2** The scorer SHALL produce a float score in range [0.0, 1.0].

**REQ-2.3** The scorer SHALL consider the following signals:
- Conjunction keywords (language-agnostic list, configurable via guardrails)
- Comparison patterns ("difference between", "X vs Y", "perbedaan antara")
- Multi-entity detection (>1 quoted terms or capitalized proper nouns)
- Causal/impact chains ("impact", "effect of", "dampak", "karena")
- Multiple interrogatives or multiple `?` characters

**REQ-2.4** If the query complexity score is below `min_complexity_score`, the system
SHALL skip LLM decomposition entirely and proceed with the standard grounded query pipeline.

**REQ-2.5** The complexity score SHALL be recorded in the trace regardless of whether
decomposition was triggered.

---

### REQ-3: LLM Decomposer

**REQ-3.1** The system SHALL call the LLM specified in `DecompositionConfig.model_profile_id`
to decompose the query into sub-queries.

**REQ-3.2** The LLM call SHALL use the rendered `system_prompt` and `user_prompt_template`
with variables: `{{ query }}`, `{{ max_sub_queries }}`, `{{ knowledge_base_name }}`.

**REQ-3.3** The decomposer SHALL expect the LLM to return a JSON array of strings.
If the response is not a valid JSON array, the system SHALL fall back to the standard
pipeline and record `decomposition_fallback: true` in the trace.

**REQ-3.4** The number of sub-queries SHALL be bounded to `max_sub_queries`. Any excess
sub-queries returned by the LLM SHALL be silently truncated.

**REQ-3.5** Each sub-query SHALL be a non-empty string. Empty or whitespace-only entries
SHALL be discarded.

**REQ-3.6** If after truncation and filtering zero sub-queries remain, the system SHALL
fall back to the standard pipeline.

**REQ-3.7** The decomposer LLM call timeout SHALL be bounded to 10 seconds. A timeout
SHALL trigger fallback to standard pipeline.

---

### REQ-4: Parallel Sub-Retrieval

**REQ-4.1** The system SHALL execute retrieval for all sub-queries concurrently using
`asyncio.gather`.

**REQ-4.2** Each sub-query SHALL use the existing `RagHybridRetrieval` pipeline
(dense + sparse + rerank) with the same index profile as the parent query.

**REQ-4.3** If a sub-query retrieval fails, the system SHALL log the failure, skip that
sub-query's evidence, and continue with the remaining sub-queries.

**REQ-4.4** If all sub-query retrievals fail, the system SHALL fall back to the standard
pipeline with the original query.

---

### REQ-5: Evidence Deduplication and Merge

**REQ-5.1** The system SHALL deduplicate evidence chunks by chunk ID (exact match).

**REQ-5.2** When the same chunk appears in multiple sub-query results, the system SHALL
retain the instance with the highest relevance score.

**REQ-5.3** After deduplication, chunks SHALL be re-sorted by descending relevance score.

**REQ-5.4** The merged evidence pool SHALL be capped at the same `top_k` limit as the
standard pipeline.

**REQ-5.5** The count of removed duplicates SHALL be recorded in the trace.

---

### REQ-6: Query API Extension

**REQ-6.1** `POST /rag/query` SHALL accept an optional `decomposition` object:
```json
{
  "decomposition": {
    "enabled": true,
    "max_sub_queries": 3
  }
}
```

**REQ-6.2** If `decomposition.enabled` is explicitly `false`, decomposition SHALL be
skipped regardless of KB config.

**REQ-6.3** If `decomposition.max_sub_queries` is provided, it SHALL override the KB
config value for that request only. Value MUST be in range 1–5.

**REQ-6.4** If the `decomposition` field is absent, the KB config SHALL be used.

**REQ-6.5** If the KB has no `DecompositionConfig`, decomposition SHALL be skipped.

---

### REQ-7: Trace Integration

**REQ-7.1** Every query response SHALL include decomposition metadata in the trace,
even when decomposition was not triggered:
```json
{
  "decomposition": {
    "triggered": false,
    "complexity_score": 0.42,
    "reason": "score_below_threshold"
  }
}
```

**REQ-7.2** When decomposition is triggered, the trace SHALL include:
```json
{
  "decomposition": {
    "triggered": true,
    "complexity_score": 0.78,
    "sub_queries": ["sub-query 1", "sub-query 2"],
    "sub_evidence_counts": [4, 3],
    "merged_evidence_count": 6,
    "dedup_removed": 1,
    "decomposition_fallback": false
  }
}
```

---

### REQ-8: DecompositionConfig API

**REQ-8.1** `POST /rag/knowledge-bases/{id}/decomposition` — create or replace config

**REQ-8.2** `GET /rag/knowledge-bases/{id}/decomposition` — get config (returns 404 if not set)

**REQ-8.3** `DELETE /rag/knowledge-bases/{id}/decomposition` — delete config

**REQ-8.4** All endpoints MUST be tenant-scoped.

---

### REQ-9: Frontend Config UI

**REQ-9.1** The KB detail/settings page SHALL include a "Query Decomposition" section.

**REQ-9.2** The UI SHALL allow enabling/disabling decomposition, selecting a model profile
(filtered to generation models only), editing prompts with a textarea, and setting numeric
guardrail values.

**REQ-9.3** The UI SHALL show a live preview of available Jinja2 template variables.

**REQ-9.4** The UI SHALL surface validation errors from the API (invalid template, invalid
model kind) inline on the form fields.

---

### REQ-10: Default Prompt Templates

**REQ-10.1** The API SHALL provide a `GET /rag/knowledge-bases/{id}/decomposition/defaults`
endpoint that returns the default system prompt and user prompt template so the UI can
pre-populate the form.
