## Why

The API quality gate is currently red even though the feature-focused tests pass: the repository has accumulated lint violations, environment/type-check failures, and two broken test doubles. This prevents reliable regression checks and obscures real defects.

## What Changes

- Bring the API Ruff check to zero without changing product behavior.
- Make the API mypy check reproducible with the project's supported Python/dependency setup.
- Fix the authentication and ingestion worker test failures at their actual repository/mock boundaries.
- Re-run the full API test, lint, type, and diff checks.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is a quality and test-baseline cleanup with no intended user-facing contract change; specs are intentionally skipped.

## Impact

Touches backend Python formatting/import hygiene, type-check configuration or annotations, test doubles, and developer verification commands. No endpoint schema, database migration, or frontend behavior is intended to change.
