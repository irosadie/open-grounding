## Why

The query planner currently emits a flat task list and executes every task in parallel. This supports decomposition, but not true multi-hop questions where a later subquestion needs the result of an earlier one. The retrieval architecture already defines bounded sequential dependencies, so the planner and executor should now support that contract without sacrificing parallelism for independent tasks.

## What Changes

- Allow planner tasks to declare bounded `depends_on` task IDs.
- Validate dependency references, cycles, task count, and maximum dependency depth before execution.
- Execute independent tasks concurrently while scheduling dependent tasks only after their prerequisites complete.
- Inject a bounded, clearly marked summary of successful prerequisite results into the dependent task context.
- Skip dependent tasks when a prerequisite fails, times out, or is unavailable, while preserving existing per-task isolation and resume behavior.
- Record dependency metadata and injected-context size in the task trace.
- Fall back to the existing single RAG task when the planner produces an invalid dependency graph.

## Capabilities

### New Capabilities

- `rag-query-task-dependencies`: Bounded dependency-aware planning and sequential execution for nested retrieval questions.

### Modified Capabilities

- `openspec/specs/rag-query-task-planner/spec.md`: Extend the planner contract from a flat parallel task list to a validated bounded dependency graph while retaining parallel execution for independent tasks.

## Impact

- Backend domain task-plan validation and task execution scheduling.
- LLM planner prompt and parsing behavior.
- RAG query orchestration and task trace output.
- Unit and integration tests for planner validation, scheduling, context injection, and failure propagation.
- Retrieval architecture documentation; no new HTTP endpoint or database migration is required.
