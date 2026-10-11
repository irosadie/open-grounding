## 1. Task-plan contract

- [x] 1.1 Extend `TaskSpec` and parser to accept `depends_on` with `refs` compatibility, enforce unique IDs, known references, no cycles, max depth two, and reject dependent MCP tasks; verify with valid, missing-reference, cycle, depth, truncation, and MCP-dependency tests.
- [x] 1.2 Update the planner prompt/context and planner metadata so generated plans know the dependency field and depth bound; verify planner parsing and fallback tests pass.

## 2. Dependency-aware execution

- [x] 2.1 Replace unconditional all-task execution with dependency-ready waves that keep independent tasks concurrent, preserve per-task timeout/error isolation, and skip tasks whose prerequisites fail; verify ordering, parallelism, timeout, and failure-propagation tests.
- [x] 2.2 Add bounded prerequisite-result serialization for dependent RAG and GENERAL tasks without changing task security fields; verify dependent handlers receive context and oversized context is truncated.
- [x] 2.3 Extend `TaskResult` and query task trace with dependency IDs and injected-context size; verify trace fields are emitted for success and skipped dependents.

## 3. Documentation and integration verification

- [x] 3.1 Update the retrieval architecture section from target-only wording to document bounded dependency execution and the MCP dependency limitation; verify the documented behavior matches the implementation.
- [x] 3.2 Run focused planner, executor, and RAG query tests plus `git diff --check`; record any unrelated repository-wide lint/type failures without broad cleanup.
