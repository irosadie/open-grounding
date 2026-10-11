## Why

The query console already receives validated answer deltas through the existing
SSE response, but the client appends every received delta immediately. When the
server flushes several deltas together, the final answer appears all at once
instead of being readable as it is produced.

## What Changes

- Render validated `response.delta` content through a small client-side
  typewriter queue.
- Reveal answer content in ordered, bounded character groups while preserving
  the exact final answer.
- Mark the query completed only after all queued answer content is visible.
- Cancel pending timers and queued content when a query is aborted, replaced,
  or the component unmounts.
- Keep the existing SSE event contract, answer validation boundary, logs, and
  database unchanged.

## Capabilities

### Modified Capabilities

- `rag-retrieval-conversation-ui`: display validated streamed answers
  progressively instead of appending all received chunks synchronously.

## Impact

- `apps/web/hooks/transactions/use-rag-query/use-rag-query-stream.ts` gains
  client-side answer scheduling and completion coordination.
- Existing stream parsing, API routes, database schema, and provider calls are
  unchanged.
- Frontend hook tests cover ordered rendering, completion timing, and abort
  cleanup.
