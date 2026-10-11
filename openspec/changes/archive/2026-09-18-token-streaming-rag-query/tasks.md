## 1. Contract and backend

- [x] 1.1 Implement bounded, word-aware answer chunking in the existing SSE producer and verify every emitted `response.delta` is derived from the validated final answer.
- [x] 1.2 Add backend route tests proving multiple ordered deltas concatenate to the exact final answer and that failures emit no answer deltas.

## 2. Frontend rendering

- [x] 2.1 Update the stream hook to append `response.delta` payloads while preserving single-delta compatibility and verify it with hook tests.
- [x] 2.2 Add or update UI stream tests for progressive answer rendering and mid-stream failure behavior.

## 3. Documentation and verification

- [x] 3.1 Update streaming documentation and generated OpenAPI descriptions to describe ordered validated answer deltas without claiming provisional token streaming.
- [x] 3.2 Run targeted API and web tests, type checks, lint, and OpenSpec validation; verify the query page renders the answer progressively.
