## 1. Backend memory scheduling

- [x] 1.1 Extend the memory enqueue wrapper to accept retry-safe job identities and verify existing callers retain their current payload shape with a focused worker test.
- [x] 1.2 Add best-effort post-query scheduling in `RagQueryService` for enabled knowledge bases, skip explicit memory-disabled requests, and verify enqueue failures do not change the query result with backend unit tests.
- [x] 1.3 Verify the scheduling path handles repeated low-turn completions and relies on the existing summarizer threshold/duplicate guards without introducing a schema migration.
- [x] 1.4 Make the OpenAI summarizer request compatible with models that reject custom temperature values, with a focused regression test.
- [x] 1.5 Lazily provision the Qdrant memory collection on first summary write and add a focused regression test.

## 2. Frontend conversation continuity

- [x] 2.1 Store `conversationId` from the `response.started` SSE event in `useRagQueryStream`, send it on subsequent requests, expose it in the hook result, and clear it in `reset`.
- [x] 2.2 Add a frontend regression test proving the first request omits `conversation_id` and the follow-up request reuses the server-issued ID.

## 3. Verification

- [x] 3.1 Run targeted API tests and static checks for the changed worker/query surfaces.
- [x] 3.2 Run targeted web tests plus typecheck/lint for the changed hook surface.
- [x] 3.3 Verify locally that a new multi-question retrieval session creates a conversation with more than two messages and that the `memory.summarize` job is consumed when memory is enabled.
- [x] 3.4 Exclude the current user turn from the recent-history snapshot before injecting conversation messages into generation, with a service-level regression test.
