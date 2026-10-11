## 1. Backend similarity contract

- [x] 1.1 Add the tenant-scoped similarity application service and wire it to the existing active index profile, dense embedding adapter, retrieval policy, generation repository, and catalog metadata; verify it returns bounded grouped document results and an empty list for missing text or active generations.
- [x] 1.2 Add `GET /rag/ingestion/{version_id}/similar-documents` with the existing success/error envelopes and safe not-found behavior; verify route tests cover same-KB scoping, current-version exclusion, result limits, and read-only lifecycle behavior.

## 2. Backend verification and API contract

- [x] 2.1 Add focused unit tests for result grouping, preview truncation, provider/retrieval failure handling, and tenant/ACL boundaries; verify the API test suite and type/lint checks pass.
- [x] 2.2 Update the exported OpenAPI contract and verify the new endpoint response is documented without exposing vectors or hidden prompt data.

## 3. Frontend integration

- [x] 3.1 Add the shared response type, API route constant, query key, and React Query hook for similar documents; verify the web typecheck/build succeeds.
- [x] 3.2 Add a non-blocking Similar Documents panel to the review page with loading, empty, error, score, preview, lifecycle, and navigation states; verify parsed-text editing and review actions remain usable in every panel state.

## 4. End-to-end validation

- [x] 4.1 Run the relevant backend tests, frontend checks, and OpenSpec strict validation; verify the review page can display matches from the same knowledge base and no schema/migration changes are introduced.
