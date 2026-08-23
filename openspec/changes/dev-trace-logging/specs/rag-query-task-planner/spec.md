## ADDED Requirements

### Requirement: Query planner dev trace event
`QueryPlanner.plan()` SHALL emit a dev trace event after the LLM returns the task breakdown.

#### Scenario: Planner trace in active mode
- **WHEN** `RAG_DEV_TRACE` is active and the planner is triggered
- **THEN** a trace event `"query.plan_tasks"` is emitted with `count` (number of tasks), `types` (list of task type strings e.g. `["RAG", "MCP", "GENERAL"]`), `system_tail` (last 300 chars of system prompt), `user_tail` (last 300 chars of user prompt), and `ms`

#### Scenario: Task list omitted in summary mode
- **WHEN** mode is `"summary"`
- **THEN** `"query.plan_tasks"` summary line contains `count=N types=RAG,MCP` but does NOT include full task detail

#### Scenario: Full task breakdown in verbose mode
- **WHEN** mode is `"verbose"`
- **THEN** `"query.plan_tasks"` JSON line contains `"tasks": [{"type": "RAG", ...}, ...]` with the full task spec array returned by the LLM
