# Production-readiness review

Scope: `answer-behavior-and-guardrails`
Review date: 2026-09-18

## Security and authorization

- [x] Policy writes require authenticated tenant ADMIN authorization.
- [x] Query callers cannot submit persona, source-policy, greeting, or output-budget overrides.
- [x] Effective policy resolution is tenant-scoped and knowledge-base overrides use tenant predicates.
- [x] New deployment tenants receive explicit versioned defaults during bootstrap.

## Fail-closed behavior

- [x] Input guardrails run before persistence of the user turn, retrieval, planner execution, generation, and memory scheduling.
- [x] MCP calls are bounded by permission, schema, call count, timeout, payload, freshness, and confirmation rules.
- [x] Denied, failed, timed-out, stale, and cross-tenant MCP results are excluded from answer evidence.
- [x] Output guardrails and provenance validation run before answer persistence or SSE release.
- [x] Missing effective policy raises a safe operational failure instead of falling back to permissive hard-coded behavior.

## Redaction and observability

- [x] MCP invocation audit records store empty raw arguments plus an argument hash.
- [x] Policy decision audit records store only stage, version, decision, stable reason, and trace ID.
- [x] MCP answer references expose server/tool/invocation/trace/timestamp metadata, never credentials or raw arguments.
- [x] Rollout traces use hashes and bounded previews at the policy-sensitive boundaries.

## Provider and rollback

- [x] Effective output budgets are passed through the provider-neutral generation port to OpenAI and Ollama mappings.
- [x] Historical policy rows remain immutable; activation retires the previous active version and preserves audit history.
- [x] Migration is reversible through the dedicated Alembic revision and the explicit default is reproducible.

## Verification evidence

- [x] Strict OpenSpec validation passes.
- [x] Backend policy/query/MCP/task tests pass.
- [x] Shared schema and package typechecks pass.
- [x] OpenAPI was regenerated from FastAPI and contains the policy endpoints.
- [x] Full web test suite is clean, including the `ConsoleSidebar` QueryClient test harness.

The repository was already carrying unrelated working-tree changes before this change was implemented; they were preserved and not used as implementation evidence.
