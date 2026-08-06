# Spec: RAG Query Task Planner

## Overview

The query pipeline routes work into typed tasks (`RAG`, `MCP`, `GENERAL`) via an
LLM planner, executes them asynchronously in parallel, then resumes and reranks
results before grounded generation. Opt-in per request and per KB.

---

## Requirements

### REQ-1: Task Plan

**REQ-1.1** The system SHALL produce a task plan: an ordered list of typed tasks.

**REQ-1.2** Supported task types SHALL be `RAG`, `MCP`, and `GENERAL`.

**REQ-1.3** Each `RAG` task SHALL contain: `query`, optional `knowledge_base_ids`, and `intent`.

**REQ-1.4** Each `MCP` task SHALL contain: `tool_ref` (server:tool name) and `arguments` (object).

**REQ-1.5** Each `GENERAL` task SHALL contain: `query` and `intent`.

**REQ-1.6** The planner SHALL bound the number of tasks to `max_tasks` (default 4, configurable 1–8). Excess tasks SHALL be truncated and recorded in trace.

**REQ-1.7** If the planner fails or returns invalid JSON, the system SHALL fall back to a single `RAG` task with the original query, recording `planner_fallback` in trace.

---

### REQ-2: Planner

**REQ-2.1** The planner SHALL run only after the linguistic complexity scorer indicates the query is complex enough (reuse `min_complexity_score`).

**REQ-2.2** The planner LLM SHALL be selected from `ModelProfile` generation models (reuse decomposition config model).

**REQ-2.3** Planner prompts SHALL be configurable Jinja2 templates (system + user), validated at save time.

**REQ-2.4** Planner variables SHALL include: `{{ query }}`, `{{ max_tasks }}`, `{{ available_tools }}`, `{{ knowledge_base_name }}`.

**REQ-2.5** The planner SHALL return a JSON array of task objects. Non-array or schema-invalid responses SHALL trigger fallback (REQ-1.7).

**REQ-2.6** The planner SHALL be skip-able per request via `decomposition`/`planner` override in query payload.

---

### REQ-3: Async Executor

**REQ-3.1** All tasks SHALL run concurrently via `asyncio.gather(return_exceptions=True)`.

**REQ-3.2** Each task SHALL have its own timeout (`task_timeout_seconds`, default 15, configurable).

**REQ-3.3** A timed-out or failed task SHALL NOT cancel other tasks.

**REQ-3.4** Task outcomes SHALL be recorded as `TaskResult` with status: `success`, `error`, `timeout`, `skipped`, or `denied`.

**REQ-3.5** `RAG` task execution SHALL use hybrid retrieval (dense + sparse, plus BM25 when `rag-retrieval-bm25` is active).

**REQ-3.6** `MCP` task execution SHALL dispatch to the MCP runtime (`rag-mcp-runtime`).

**REQ-3.7** If MCP runtime is unavailable or MCP capability is disabled for the KB/request, the MCP task SHALL return `status="skipped"` with `reason="capability_not_enabled"` — never a silent failure.

**REQ-3.8** `GENERAL` task execution SHALL call the configured generation LLM with a general-knowledge prompt (no evidence).

---

### REQ-4: Resume and Merge

**REQ-4.1** All `RAG` task evidence SHALL be merged via the existing evidence merger (dedup by chunk ID, rank by max score, cap at `top_k`).

**REQ-4.2** Merged RAG evidence SHALL be reranked using the existing `gate_evidence` decision (candidate count, independent sources, top score).

**REQ-4.3** `MCP` results SHALL be assembled into a labeled supplementary context block: `[Live tool results:]`.

**REQ-4.4** `GENERAL` results SHALL be assembled into a labeled supplementary context block: `[Related context:]`.

**REQ-4.5** Supplementary context (MCP/GENERAL) SHALL NOT be fused into the vector-ranked evidence set.

**REQ-4.6** If all RAG tasks fail and there is no supplementary context, the system SHALL route to `ABSTAIN` with a clear limitation.

---

### REQ-5: Generation

**REQ-5.1** Final generation SHALL be grounded in the ranked RAG evidence set.

**REQ-5.2** Supplementary context SHALL be appended to the generation prompt, clearly separated from ranked evidence, and SHALL NOT be citable as a source.

**REQ-5.3** Generation SHALL reuse `RagGenerationService` and existing grounded answer parsing.

---

### REQ-6: Trace

**REQ-6.1** Query response trace SHALL include:
```json
{
  "planner": {
    "triggered": true,
    "complexity_score": 0.78,
    "task_count": 3,
    "planner_fallback": false
  },
  "tasks": [
    {"id": "t1", "type": "RAG", "status": "success", "duration_ms": 120, "evidence_count": 5},
    {"id": "t2", "type": "MCP", "status": "skipped", "reason": "capability_not_enabled"},
    {"id": "t3", "type": "GENERAL", "status": "success", "duration_ms": 400}
  ],
  "resume": {
    "merged_evidence_count": 6,
    "dedup_removed": 2,
    "rerank_route": "grounded",
    "supplementary_blocks": 2
  }
}
```

**REQ-6.2** Planner fallback, per-task status, and resume decisions SHALL always be recorded even on the abstain path.

---

### REQ-7: Query API Extension

**REQ-7.1** `POST /rag/query` SHALL accept an optional `planner` override:
```json
{
  "planner": {
    "enabled": true,
    "max_tasks": 4,
    "task_types": ["RAG", "GENERAL"]
  }
}
```

**REQ-7.2** `task_types` SHALL restrict which task types the planner may emit.

**REQ-7.3** If `planner.enabled` is `false`, the query SHALL use the standard single-pass pipeline (no planning).

**REQ-7.4** If the field is absent, per-KB config SHALL be used.

---

### REQ-8: Planner Config (per KB)

**REQ-8.1** `PlannerConfig` SHALL be optional, attached 1:1 to a KB, with:
- `enabled` (bool)
- `model_profile_id` (FK → generation ModelProfile)
- `system_prompt` + `user_prompt_template` (Jinja2)
- `max_tasks` (int 1–8)
- `task_timeout_seconds` (int 1–60)
- `task_types` allowlist (subset of RAG/MCP/GENERAL)
- `mcp_enabled` (bool, gate for MCP dispatch)
- `guardrails` (JSON)

**REQ-8.2** API: `GET/POST/DELETE /rag/knowledge-bases/{id}/planner` and `GET .../planner/defaults`.

**REQ-8.3** Reuses the same validation rules as decomposition config (model kind, Jinja2, numeric bounds).

---

### REQ-9: Frontend — Planner Config UI

**REQ-9.1** The decomposition config page SHALL be renamed/extended to "Query Planner" with:
- model profile selector (generation)
- planner system + user prompt editors with `{{ available_tools }}` hint
- max_tasks, task_timeout, task_types multi-select, mcp_enabled toggle
- guardrails editor

**REQ-9.2** A task run viewer SHALL show the task plan + per-task status + resume summary from trace.

---

### REQ-10: Integration with MCP Runtime

**REQ-10.1** When MCP capability is enabled, the planner prompt SHALL include `available_tools` (names + descriptions from `McpTool` registry where `allowed=true`).

**REQ-10.2** MCP executor SHALL call `McpRuntimeService.invoke_tool` and map `TOOL_DENIED`/`TOOL_TIMEOUT` to task status accordingly.

**REQ-10.3** The runtime dependency SHALL be optional: if the MCP change is not deployed, MCP tasks are skipped (REQ-3.7).
