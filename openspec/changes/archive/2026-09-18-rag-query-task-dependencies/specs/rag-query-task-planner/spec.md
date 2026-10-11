## MODIFIED Requirements

### Requirement: Query pipeline routes work into typed tasks via an LLM planner
The system SHALL produce a task plan — an ordered list of typed tasks (`RAG`, `MCP`, `GENERAL`) — from an LLM planner when complexity gating passes. A `RAG` or `GENERAL` task MAY declare `depends_on` task IDs; `MCP` tasks MUST NOT declare dependencies in this phase. The planner MUST bound task count to `max_tasks` (default 4, configurable 1–8), validate dependency references and cycles, and enforce a maximum dependency depth of two. Excess tasks SHALL be truncated and recorded in trace. If the planner fails or returns invalid JSON or an invalid dependency graph, the system SHALL fall back to a single `RAG` task with the original query, recording `planner_fallback` in trace.

#### Scenario: Planner produces a valid dependency-aware task plan
- **WHEN** the planner LLM returns a valid JSON array of typed task objects with valid dependencies
- **THEN** the executor runs independent tasks concurrently, runs dependent tasks after their prerequisites, and records the full plan in trace

#### Scenario: Planner produces a valid task plan
- **WHEN** the planner LLM returns a valid JSON array of typed task objects without dependencies
- **THEN** the executor runs the tasks concurrently and records the full plan in trace

#### Scenario: Planner returns invalid JSON
- **WHEN** the planner LLM returns a non-array or schema-invalid response
- **THEN** the system falls back to a single RAG task with the original query and records `planner_fallback: true` in trace; no error is surfaced to the caller

#### Scenario: Planner returns an invalid dependency graph
- **WHEN** the planner LLM returns a missing dependency, cycle, or dependency depth greater than two
- **THEN** the system falls back to a single RAG task with the original query and records `planner_fallback: true` in trace; no error is surfaced to the caller

### Requirement: All tasks execute concurrently with per-task isolation
The system SHALL run all currently-ready independent tasks concurrently and SHALL schedule each dependent task only after all of its prerequisites complete. Each task SHALL have its own timeout (`task_timeout_seconds`, default 15). A timed-out or failed task SHALL NOT cancel unrelated tasks. Task outcomes SHALL be recorded as `TaskResult` with status: `success`, `error`, `timeout`, `skipped`, or `denied`.

#### Scenario: One task times out while others succeed
- **WHEN** an MCP task exceeds `task_timeout_seconds` while RAG and GENERAL tasks complete
- **THEN** the MCP task is recorded as `status="timeout"`, unrelated tasks continue, and any dependent task is recorded as skipped with a dependency failure reason

#### Scenario: Dependent task waits for prerequisite
- **WHEN** task `b` depends on task `a`
- **THEN** task `b` does not start until task `a` has completed and its successful result is available as bounded context

### Requirement: Full task plan and resume decisions are recorded in trace
The system SHALL record in the query trace: planner triggered flag, complexity score, task count, planner fallback flag, per-task id/type/status/duration/evidence count, dependency IDs, injected dependency-context size, merged evidence count, dedup removed count, rerank route, and supplementary block count. Planner fallback, per-task status, dependency failure, and resume decisions SHALL always be recorded even on the abstain path.

#### Scenario: Query completes via abstain path
- **WHEN** the query route resolves to `ABSTAIN` after task execution
- **THEN** the trace still contains the full task plan, dependency metadata, per-task statuses, and resume summary including the abstain reason
