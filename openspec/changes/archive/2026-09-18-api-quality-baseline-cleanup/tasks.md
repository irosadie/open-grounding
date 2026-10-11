## 1. Ruff baseline

- [x] 1.1 Apply safe Ruff fixes across `apps/api/app` and `apps/api/tests`, then verify the remaining findings are limited to intentional manual fixes.
- [x] 1.2 Resolve all remaining Ruff findings with minimal edits and verify `uv run --project . --group dev ruff check app tests` passes.

## 2. Mypy baseline

- [x] 2.1 Resolve missing third-party typing and Python-version compatibility errors while keeping strict checking enabled; verify `uv run --project . python -m mypy app` passes.

## 3. Test regressions

- [x] 3.1 Update the auth repository test double to implement the production transaction boundary and verify `tests/test_auth_service.py` passes.
- [x] 3.2 Correct the ingestion worker async session mock to return the repository's expected row/result shape and verify `tests/workers/test_worker_consolidation.py` passes.

## 4. Final verification

- [x] 4.1 Run the full API test suite, `git diff --check`, and OpenSpec validation; verify no new API contract or OpenAPI drift is introduced.
