## Why

The console reports that no memory chunks exist even though memory is enabled for the
`docme` knowledge base. Completed queries are persisted as isolated two-message
conversations, and the `memory.summarize` worker is never triggered, so the configured
memory pipeline cannot reach the summarization step.

## What Changes

- Preserve the server-issued conversation ID in the retrieval UI and send it with
  subsequent questions in the same session.
- Enqueue memory summarization after a completed query for each enabled knowledge base,
  using retry-safe unique job identities while retaining the summarizer's existing
  eligibility and duplicate guards.
- Keep the OpenAI summarizer request compatible with models that only accept their
  default sampling parameter.
- Provision the Qdrant memory collection lazily when the first summary is persisted.
- Keep enqueue failures non-blocking so a successful query remains successful.
- Add focused backend and frontend regression coverage for conversation continuity and
  memory job scheduling.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rag-conversation-memory`: completed eligible conversations must trigger the existing
  background summarization job when memory is enabled.
- `rag-retrieval-conversation-ui`: consecutive questions in one retrieval session must
  reuse the server-issued conversation ID.

## Impact

- Frontend hook and retrieval screen state in `apps/web`.
- Backend query orchestration and BullMQ memory enqueue path in `apps/api`.
- Existing SSE and response contracts remain unchanged; `conversationId` is already
  emitted by the API.
- No database migration is required.
