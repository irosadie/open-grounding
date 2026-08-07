# rag-query-task-planner Specification

## Purpose
Defines the query task planner pipeline: LLM-driven typed task plan generation
(RAG/MCP/GENERAL), async parallel execution with per-task isolation and timeout,
evidence merge and resume, supplementary context assembly, and grounded generation.
Opt-in per request and per knowledge base via `PlannerConfig`.

## Requirements

### Requirement: Query pipeline routes work into typed tasks via an LLM planner
The system SHALL produce a task plan — an ordered list of typed tasks (`RAG`, `MCP`,
`GENERAL`) — from an LLM planner when complexity gating passes. The planner MUST bound
task count to `max_tasks` (default 4, configurable 1–8). Excess tasks SHALL be
truncated and recorded in trace. If the planner fails or returns invalid JSON, the
system SHALL fall back to a single `RAG` task with the original query, recording
`planner_fallback` in trace.

#### Scenario: Planner produces a valid task plan
- **WHEN** the planner LLM returns a valid JSON array of typed task objects
- **THEN** the executor runs each task concurrently and records the full plan in trace

#### Scenario: Planner returns invalid JSON
- **WHEN** the planner LLM returns a non-array or schema-invalid response
- **THEN** the system falls back to a single RAG task with the original query and
  records `planner_fallback: true` in trace; no error is surfaced to the caller

### Requirement: All tasks execute concurrently with per-task isolation
The system SHALL run all tasks via `asyncio.gather(return_exceptions=True)`. Each task
SHALL have its own timeout (`task_timeout_seconds`, default 15). A timed-out or failed
task SHALL NOT cancel other tasks. Task outcomes SHALL be recorded as `TaskResult` with
status: `success`, `error`, `timeout`, `skipped`, or `denied`.

#### Scenario: One task times out while others succeed
- **WHEN** an MCP task exceeds `task_timeout_seconds` while RAG and GENERAL tasks complete
- **THEN** the MCP task is recorded as `status="timeout"` and the pipeline resumes
  with evidence from the successful tasks; no error is surfaced to the caller

### Requirement: MCP tasks are skipped when capability is not enabled
The system SHALL dispatch `MCP` tasks to `McpRuntimeService` only when MCP capability
is enabled for the knowledge base and request. If the MCP runtime is unavailable or
capability is disabled, MCP tasks SHALL return `status="skipped"` with
`reason="capability_not_enabled"` — never a silent failure.

#### Scenario: MCP runtime is not deployed
- **WHEN** the MCP runtime change is not deployed and a planner emits an MCP task
- **THEN** the task is recorded as skipped with reason and the pipeline continues
  with RAG and GENERAL results

### Requirement: RAG evidence is merged and reranked; MCP and GENERAL become supplementary context
The system SHALL merge all RAG task evidence via the existing evidence merger (dedup by
chunk ID, rank by max score, cap at `top_k`) and rerank using the existing `gate_evidence`
decision. MCP results SHALL be assembled as `[Live tool results:]` context blocks.
GENERAL results SHALL be assembled as `[Related context:]` context blocks.
Supplementary context SHALL NOT be fused into the vector-ranked evidence set and SHALL
NOT be citable as a source. If all RAG tasks fail and there is no supplementary context,
the system SHALL route to `ABSTAIN`.

#### Scenario: All RAG tasks fail with no supplementary context
- **WHEN** all RAG tasks return errors or timeouts and no MCP or GENERAL tasks succeed
- **THEN** the system routes to `ABSTAIN` with a clear limitation recorded in trace

### Requirement: Full task plan and resume decisions are recorded in trace
The system SHALL record in the query trace: planner triggered flag, complexity score,
task count, planner fallback flag, per-task id/type/status/duration/evidence count,
merged evidence count, dedup removed count, rerank route, and supplementary block count.
Planner fallback, per-task status, and resume decisions SHALL always be recorded even
on the abstain path.

#### Scenario: Query completes via abstain path
- **WHEN** the query route resolves to `ABSTAIN` after task execution
- **THEN** the trace still contains the full task plan, per-task statuses, and resume
  summary including the abstain reason

### Requirement: Planner is configurable per knowledge base via PlannerConfig
The system SHALL provide an optional `PlannerConfig` per knowledge base with: `enabled`,
`model_profile_id`, `system_prompt`, `user_prompt_template` (Jinja2), `max_tasks` (1–8),
`task_timeout_seconds` (1–60), `task_types` allowlist (RAG/MCP/GENERAL subset),
`mcp_enabled`, and `guardrails` JSON. API: `GET/POST/DELETE
/rag/knowledge-bases/{id}/planner` and `GET .../planner/defaults`. Planner can be
overridden per-request via the `planner` field in the query payload.

#### Scenario: Caller disables planner per-request
- **WHEN** a query payload contains `"planner": {"enabled": false}`
- **THEN** the system uses the standard single-pass pipeline without task planning
  regardless of the per-KB PlannerConfig setting

### Requirement: Planner config UI extends the decomposition settings page
The system SHALL provide a "Query Planner" settings page per knowledge base with:
model profile selector, planner system and user prompt editors with `{{ available_tools }}`
hint, max_tasks, task_timeout, task_types multi-select, mcp_enabled toggle, and a task
run viewer showing the task plan, per-task status, and resume summary from the trace.

#### Scenario: Operator saves planner config
- **WHEN** an operator fills in the planner config form and clicks Save
- **THEN** the `PlannerConfig` record is created or updated for the knowledge base and
  subsequent queries against that KB use the new planner settings
