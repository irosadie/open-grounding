## Why

The RAG SSE endpoint currently emits no useful event while the query service is
planning, retrieving evidence, or generating an answer. The UI therefore looks
stuck until the validated result is ready.

## What Changes

- Add validation-safe `response.progress` SSE events for planning, retrieval,
  generation, and answer validation.
- Send the conversation ID in the initial progress event so the client can
  preserve conversation continuity even if the stream is interrupted early.
- Add a Query console checkbox that lets the user choose streamed answer
  delivery or the existing blocking JSON response.
- Keep the streamed answer user-facing as validated text only; transport
  metadata remains internal to the SSE client and is never rendered as JSON.
- Keep `response.delta` answer content gated behind the existing final answer
  and citation validation boundary.
- Render the latest progress message in the Query console while the stream is
  active.
- Preserve existing answer, citation, completion, and failure event contracts.

## Capabilities

### Modified Capabilities

- `rag-grounded-answer-generation`: expose pipeline progress without exposing
  unvalidated answer content.
- `rag-retrieval-conversation-ui`: display live progress while a query is
  streaming and append only validated answer deltas.

## Impact

- `apps/api/app/application/rag_query_service.py` gains an optional progress
  callback at pipeline milestones.
- `apps/api/app/interfaces/http/routes.py` forwards callback events through the
  existing SSE stream.
- `apps/web/hooks/transactions/use-rag-query/use-rag-query-stream.ts` and the
  Query console render progress events.
- No database, provider, or migration changes are required.
