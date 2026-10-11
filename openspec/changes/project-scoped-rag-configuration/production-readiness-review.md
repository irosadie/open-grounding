# Production-readiness review

Scope: `project-scoped-rag-configuration`
Review date: 2026-09-18

## Rollback and pause controls

- [x] Application rollback is additive: re-enable `RAG_PROJECT_LEGACY_KB_WRITES_ENABLED`
  and `RAG_PROJECT_LEGACY_FALLBACK_ENABLED`, then deploy the previous application version.
- [x] Production rollback does not downgrade `20260918_02`; Project, membership, review,
  and audit rows remain available for a later retry.
- [x] The compatibility cutoff is explicit through
  `RAG_PROJECT_COMPATIBILITY_END_DATE` and the operations runbook.
- [x] The project migration was rehearsed on an isolated representative database clone:
  current → upgrade (idempotent) → downgrade to `20260918_01` → upgrade → upgrade.

## Legacy compatibility and query safety

- [x] New shared configuration writes are Project-scoped; legacy KB writes are controlled
  by an explicit feature flag.
- [x] Legacy fallback is limited to a single-KB resolution and never merges profiles from
  a multi-KB request.
- [x] One-KB inference, same-Project multi-KB inference, explicit mismatch, cross-tenant
  IDs, archived Projects, and legacy fallback have regression coverage.
- [x] Project resolution occurs before planner, retrieval, MCP, memory, and generation
  side effects; rejected scopes return stable errors and bounded metrics.

## Audit, retention, and data preservation

- [x] Project membership moves, Project lifecycle changes, migration review state, policy
  changes, and scope conflicts carry tenant-scoped audit/reason metadata.
- [x] Audit metadata is bounded and excludes prompts, credentials, provider arguments,
  source payloads, and other unbounded content.
- [x] The migration assigns ownership without rewriting documents, indexes, ACLs, or
  historical policy rows; legacy records remain reviewable.
- [x] Project and policy records use tenant predicates and cross-tenant repository tests.

## Verification evidence

- [x] Backend suite: 428 passed, 17 skipped.
- [x] Frontend suite: 37 passed; shared schemas: 23 passed; route smoke test passed.
- [x] Monorepo lint and typecheck passed.
- [x] OpenAPI was regenerated and strict OpenSpec validation passed.

The repository contains other active user changes; they were preserved. The migration
rehearsal used a disposable database clone and did not downgrade or mutate the shared
development database.
