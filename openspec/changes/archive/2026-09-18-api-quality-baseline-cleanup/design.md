## Context

See `proposal.md`. The current API baseline reports safe Ruff violations across application and test modules, missing third-party typing metadata during mypy, and failures caused by test repositories/mocks no longer matching the production boundaries.

## Goals / Non-Goals

**Goals:**

- Remove all Ruff findings using safe automated fixes where possible and small manual edits where needed.
- Resolve mypy errors through correct project configuration, dependency typing, or narrow annotations rather than suppressing unrelated type checking.
- Keep test fixtures faithful to the production repository/session contracts.
- Preserve runtime behavior and API contracts.

**Non-Goals:**

- No broad refactor, feature work, endpoint redesign, schema migration, or unrelated cleanup.
- No unsafe Ruff fixes that alter control flow or semantics without a regression test.
- No blanket `# type: ignore` or global disabling of meaningful mypy rules.

## Decisions

### Use Ruff safe fixes first, then targeted manual edits

Ruff's safe import and mechanical fixes will be applied to the API surface, followed by manual handling of remaining line-length, unused-symbol, and style findings. This minimizes hand-edited churn while keeping the final diff reviewable.

### Fix typing at the dependency boundary

For third-party packages without usable stubs, use the narrowest project-supported approach: install or configure the relevant typing package when available, and isolate unavoidable untyped imports at their import boundary. Do not lower strictness for application code.

### Repair test doubles instead of weakening production behavior

The auth in-memory repository will implement the transaction protocol expected by the login use case, and the ingestion worker test will configure the async session result shape expected by the repository. Production atomicity and repository behavior remain authoritative.

## Risks / Trade-offs

- [Risk] Mechanical formatting creates a large diff → Mitigation: limit changes to Ruff-reported files and review behavior-sensitive hunks.
- [Risk] Type-check configuration can hide real errors → Mitigation: keep strict mode enabled and use narrow import-boundary handling only for packages that lack stubs.
- [Risk] Test fixture changes can mask regressions → Mitigation: assert the same transaction/query behavior used by production code and run the complete API suite.

## Migration Plan

No runtime migration is required. Apply code/config/test corrections, run the full checks, and revert the quality-only change as a unit if any behavior regression appears.
