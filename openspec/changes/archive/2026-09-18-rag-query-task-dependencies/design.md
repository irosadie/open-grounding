## Context

See `proposal.md` and the two delta specs for the behavior contract. The current `TaskSpec` has an unused reference field and `TaskExecutor` sends every task to `asyncio.gather` at once. The query service already owns the planner and task handlers, so dependency scheduling can remain inside the application boundary without changing the HTTP contract, persistence model, or retrieval authorization path.

## Goals / Non-Goals

**Goals:**

- Add a validated, bounded dependency graph to the existing typed task plan.
- Preserve parallel execution for independent tasks and per-task timeout/error isolation.
- Make successful prerequisite output available to dependent RAG and GENERAL tasks through bounded context.
- Keep MCP task behavior safe and backward-compatible by rejecting MCP tasks that declare dependencies until a tool-input contract exists.
- Expose dependency metadata in the existing trace payload.

**Non-Goals:**

- No new endpoint, database table, migration, or frontend settings surface.
- No recursive replanning, unbounded dependency depth, or conditional branching language.
- No change to ACL, tenant, knowledge-base, or generation authorization decisions.
- No change to the existing evidence merge and supplementary-context rules.

## Decisions

### Validate the graph at the task-plan boundary

Extend `TaskSpec` with `depends_on` while retaining `refs` as a compatibility alias for older planner output. Parse and validate after max-task truncation so a reference to a removed task cannot execute accidentally. Validation will enforce unique IDs, known references, no self-reference or cycle, a maximum depth of two, and no dependencies on MCP tasks. `QueryPlanner` already converts parser failures into the existing single-task fallback.

Alternative considered: let the executor discover malformed graphs at runtime. Rejected because invalid planner output should follow the existing deterministic fallback path and never partially execute.

### Schedule in dependency-ready waves

`TaskExecutor.execute` will maintain the original task order, a completed-result map, and a pending set. Each iteration finds tasks whose prerequisites are complete, marks tasks with unsuccessful prerequisites as skipped, and runs the remaining ready tasks through `asyncio.gather(return_exceptions=True)`. This keeps independent tasks concurrent while guaranteeing that dependents start only after all prerequisites have a result.

Alternative considered: one coroutine per task that waits on futures. Rejected because wave scheduling makes cycle/missing-result handling explicit and preserves deterministic result ordering with less coordination state.

### Inject context by deriving an effective task spec

Before invoking a dependent RAG or GENERAL handler, serialize compact successful prerequisite outputs into a marked `DEPENDENCY CONTEXT` block and append it to the effective query. The original task spec remains unchanged for trace identity and security fields. Context is deterministically truncated to a fixed character bound owned by the executor; knowledge-base IDs and tenant authorization are never taken from dependency output. MCP tasks remain one-argument handlers and cannot be dependents in this phase.

Alternative considered: change every handler protocol to accept a second context argument. Rejected because it would expand the handler surface and break existing test and integration handlers for no user-visible benefit.

### Extend task trace without changing the API schema

Add dependency IDs and injected-context size to `TaskResult`, then include them in the existing task trace dictionaries. The current response and trace containers are open mappings, so no route or OpenAPI schema change is required.

## Risks / Trade-offs

- [Risk] Dependency context can contain prompt-injection text from retrieved content → Mitigation: label it as untrusted prerequisite context, keep the existing retrieval/generation policy path, and bound its size.
- [Risk] A dependent task may be skipped even though other evidence exists → Mitigation: preserve successful independent results and record the skip reason so resume/abstain behavior remains observable.
- [Risk] Truncating a planner output can invalidate a later dependency → Mitigation: validate the truncated task list and use the existing single-task fallback when references are no longer resolvable.
- [Risk] Existing callers still emit `refs` → Mitigation: accept `refs` as a backward-compatible input alias while emitting and documenting `depends_on`.

## Migration Plan

No data migration is required. Deploy parser, scheduler, and trace changes together. Existing flat plans remain valid and continue to execute as one parallel wave. Rollback is code-only; old plans do not depend on the new fields.
