# Proposal: RAG Query Task Planner

## Problem

The current query pipeline treats every query the same: decompose → retrieve → generate.
But real queries need different strategies:
- Questions answerable from indexed documents → **RAG** (retrieval)
- Questions needing external data or live tool access → **MCP** (tool call)
- General knowledge or clarification → **GENERAL** (LLM directly)

Decomposing a query naively into sub-queries loses the intent of *what kind of tool*
each part needs. This change upgrades the existing `rag-query-decomposition` architecture
into a **task planner**: the decomposer outputs a typed task plan, an async executor
runs tasks in parallel (hybrid BM25 + vector retrieval for RAG, MCP tool calls, general
LLM), then a resumer merges and reranks results before final grounded generation.

## Proposed Solution

A query planner pipeline that runs **before** generation:

```
incoming query
  → Query Planner (LLM, configurable) → typed task plan
      [{id, type: RAG|MCP|GENERAL, intent, query, refs, args}]
  → AsyncExecutor (parallel)
      RAG  → hybrid BM25 + dense retrieval per task
      MCP  → call MCP runtime tool (pending rag-mcp-runtime)
      GEN  → general LLM answer (no retrieval)
  → Resume + merge (cross-type result envelope)
  → Rerank evidence (RAG results fused + MCP/GENERAL as supplementary context)
  → grounded generation (final answer, cites sources)
```

This is **opt-in per request & per KB**, configurable (model, prompt, guardrails, task
capabilities), and fully traceable.

## Key Design Decisions

- **Typed task plan**: RAG, MCP, GENERAL each with own result schema; unified `TaskResult` envelope for resume.
- **Async parallel execution**: `asyncio.gather` across tasks with per-task timeout.
- **Resume strategy aware of types**: rerank is meaningful only for RAG evidence; MCP/GENERAL outputs become supplementary context, not conflated with vector score.
- **Capability gating**: each tenant config enables/disables MCP task execution (needs `rag-mcp-runtime`).
- **Configurable**: model profile, Jinja2 planner prompt, guardrails (max tasks, task-type allowlist), per request override.
- **Trace**: full task plan + per-task outcome + resume decisions recorded.

## What This Is Not

- Not the MCP runtime (that's `rag-mcp-runtime`).
- Not BM25 retrieval (that's `rag-retrieval-bm25`).
- Not default behavior until evaluation-gated and configured.

## Success Criteria

- Planner produces a typed task plan for complex queries
- RAG + GENERAL tasks execute in parallel and results merge correctly
- MCP tasks dispatch to the MCP runtime when enabled
- Per-task isolation: one failing task does not kill others
- Rerank produces a single grounded evidence set for final generation
- Full task + trace visibility
- Config UI per knowledge base

## Scope

**In scope:**
- Task types (`RAG`, `MCP`, `GENERAL`) + task result envelope
- Query planner LLM + guardrails (reuse/upgrade `query_decomposer.py`)
- Async executor (parallel, per-task timeout, isolation)
- Resumer (merge + cross-type context assembly)
- Rerank evidence via existing `gate_evidence` + evidence merger
- Trace + task metadata
- API + shared contracts + frontend config UI updates
- Integration with `rag-mcp-runtime` (consume tool registry)

**Out of scope:**
- MCP runtime implementation (depends on `rag-mcp-runtime` change)
- BM25 implementation (depends on `rag-retrieval-bm25` change)
- Conversation memory integration (existing feature, orthogonal)