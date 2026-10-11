# rag-query-task-dependencies Specification

## Purpose
Provides bounded dependency-aware execution so nested retrieval questions can use the result of an earlier subquestion while independent work continues in parallel.

## Requirements

### Requirement: Planner tasks may declare bounded dependencies
The system SHALL accept a task dependency field containing zero or more task IDs on `RAG` and `GENERAL` tasks. Every referenced task ID MUST exist in the same plan, dependencies MUST be acyclic, and the dependency depth MUST NOT exceed two levels. `MCP` tasks MUST NOT declare dependencies in this phase. The planner MUST preserve the knowledge-base selection and authorization scope already assigned to every task.

#### Scenario: Valid nested retrieval plan
- **WHEN** a plan contains task `b` with `depends_on: ["a"]` and task `a` exists at depth one
- **THEN** the plan is accepted and task `b` is scheduled after task `a` completes

#### Scenario: Invalid dependency graph
- **WHEN** a plan contains an unknown dependency, a cycle, a dependency deeper than two levels, or an MCP task with a dependency
- **THEN** the plan is rejected as invalid and the query pipeline falls back to one RAG task using the original query

### Requirement: Dependent tasks receive bounded prerequisite context
The system SHALL make successful prerequisite results available to a dependent task as clearly marked context. The injected context MUST be bounded by the configured execution limit and MUST NOT change the task's knowledge-base IDs, authorization scope, or security policy inputs.

#### Scenario: Subquestion uses a prior result
- **WHEN** task `a` succeeds and task `b` depends on `a`
- **THEN** task `b` receives a bounded context containing task `a`'s result before it executes

#### Scenario: Context exceeds the bound
- **WHEN** prerequisite results exceed the dependency-context limit
- **THEN** the context passed to the dependent task is truncated deterministically and execution continues

### Requirement: Dependency failures propagate explicitly
The system SHALL not execute a dependent task when any prerequisite is unsuccessful. The dependent task MUST be recorded as `status="skipped"` with a dependency failure reason, while unrelated ready tasks continue to execute.

#### Scenario: Required prerequisite fails
- **WHEN** task `a` times out or returns an error and task `b` depends on `a`
- **THEN** task `b` is skipped with an explicit dependency failure status and independent tasks are unaffected
