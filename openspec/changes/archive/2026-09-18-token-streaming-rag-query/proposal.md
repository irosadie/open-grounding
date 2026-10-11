## Why

The query page already uses SSE, but the backend currently emits the answer as a
single `response.delta` after the complete query finishes. The UI therefore cannot
render the validated answer progressively, which makes long answers feel blocked.

## What Changes

- Split a validated final answer into ordered SSE answer deltas.
- Update the frontend stream hook to append deltas in arrival order while keeping
  the existing single-delta behavior backward compatible.
- Preserve the current safety boundary: no provisional or unvalidated model tokens
  are exposed to clients.
- Add backend and frontend tests covering multiple deltas and their ordering.
- Update the query streaming documentation and API contract description.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rag-grounded-answer-generation`: define that a validated answer may be emitted
  as multiple ordered `response.delta` events, with no unvalidated content.
- `rag-retrieval-conversation-ui`: ensure the client appends ordered answer deltas
  instead of replacing the accumulated answer.

## Impact

- `apps/api/app/interfaces/http/routes.py` will emit validated answer chunks from
  the existing SSE endpoint.
- `apps/web/hooks/transactions/use-rag-query/use-rag-query-stream.ts` will append
  incoming answer chunks.
- Existing non-streaming responses and the SSE event names remain unchanged.
- No database, provider, or migration changes are required.
