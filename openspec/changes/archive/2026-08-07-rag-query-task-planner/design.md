# Design: RAG Query Task Planner

## Context

Builds on `rag-query-decomposition` (already implemented: complexity scorer,
`QueryDecomposer`, `evidence_merger`, decomposition config per KB). This change
upgrades the decomposer into a task planner and wires async execution + resume.

Dependencies (other changes, may land before/parallel):
- `rag-mcp-runtime` — for MCP task execution + tool registry
- `rag-retrieval-bm25` — for hybrid BM25 + vector retrieval

Until those land, RAG tasks use existing hybrid retrieval and MCP tasks are
planned but rejected with a clear "capability not enabled" trace.

## Architecture

### Task Plan (from Planner)

```json
[
  {
    "id": "t1",
    "type": "RAG",
    "intent": "retrieve_policy_evidence",
    "query": "leave policy for department A",
    "knowledge_base_ids": ["..."],
    "refs": []
  },
  {
    "id": "t2",
    "type": "MCP",
    "intent": "lookup_live_headcount",
    "tool_ref": "hr:get_headcount",
    "arguments": {"dept": "A"}
  },
  {
    "id": "t3",
    "type": "GENERAL",
    "intent": "synthesize_productivity_factors",
    "query": "common productivity factors under new leave policy"
  }
]
```

### TaskResult Envelope

```python
@dataclass
class TaskResult:
    task_id: str
    task_type: str            # RAG | MCP | GENERAL
    status: str               # success | error | timeout | skipped | denied
    error: str | None
    duration_ms: int
    # type-specific payload
    rag: list[dict] | None        # merged evidence chunks (id, score, text, source)
    mcp: dict | None              # { tool, result_text, truncated }
    general: str | None           # text answer
```

### Async Executor

`asyncio.gather(return_exceptions=True)` across all tasks. Each task runs with its
own `asyncio.timeout`. One failing task does not cancel others.

- RAG executor → `RagHybridRetrievalService.retrieve` (+ BM25 fuse when available)
- MCP executor → `McpRuntimeService.invoke_tool` (capability-gated; disabled until runtime exists)
- GENERAL executor → LLM call with a general-knowledge prompt (no evidence)

### Resumer

- RAG results from all RAG tasks → `evidence_merger.merge_evidence` → dedup → ranked evidence
- Rerank via `gate_evidence` (candidate count, independent sources, top score)
- MCP results → supplementary context block (labeled "Live tool results")
- GENERAL results → supplementary context (labeled "Related context")
- Final context assembly for generation:
  - Ranked evidence (from RAG, scored)
  - Supplementary context (MCP + GENERAL, unscored, labeled)

### Generation

Uses existing `RagGenerationService` with the assembled context. Answer grounded in
ranked evidence; MCP/GENERAL blocks are supplementary and clearly separated so the
answer never fabricates citations from unscored context.

## Decisions

### Typed tasks over uniform sub-queries

The whole point of the planner is routing, not just splitting. Typed tasks let the
executor choose the right engine per task and let the resumer treat results correctly.

### MCP capability gating

Until `rag-mcp-runtime` ships, planner may emit MCP tasks but the executor returns
`status="skipped"` with reason `capability_not_enabled`, recorded in trace. No silent
failure.

### General tasks have no evidence citation

GENERAL task output goes to supplementary context only. It can inform the answer but
must not appear as a cited source. This preserves groundedness guarantees.

### Per-task timeout isolation

A hanging MCP or GENERAL call must not block RAG tasks. Per-task timeout (configurable,
default 15s) via `asyncio.timeout` inside each executor branch.

## Risks / Trade-offs

- [Planner cost] — planner LLM call adds latency. Gated by complexity scorer first (reuse).
- [MCP task without runtime] — skipped with clear trace until runtime lands.
- [Cross-type merge] — rerank only RAG; MCP/GENERAL kept separate to avoid meaningless score fusion.
- [Task explosion] — bounded by `max_tasks` guardrail (default 4), planner truncates.

## Open Questions

- Should a single query produce a task graph (dependencies between tasks) or a flat list?
  → Flat list first; graph support deferred.
