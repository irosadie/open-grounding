## Why

The non-streaming query response already has a stable JSON contract. The
streaming path also sends answer deltas inside JSON-shaped SSE payloads, so the
browser renders the answer as plain text instead of a ChatGPT-like Markdown
response. The stream needs a text presentation contract without losing live
pipeline status or validated answer metadata.

## What Changes

- Keep `stream=false` as the existing JSON response contract.
- Keep pipeline status events structured and live in the SSE stream.
- Emit streamed `response.delta` events as raw Markdown data, not a JSON answer
  object.
- Render streamed and blocking answer text with the existing Markdown renderer.
- Keep `Inferences` and `Limitations` at the end of the generated Markdown
  answer when those sections contain content.
- Preserve answer validation, citations, tenant controls, and persistence.

## Capabilities

### Modified Capabilities

- `rag-retrieval-conversation-ui`: render the stream as Markdown while keeping
  status events and the JSON mode unchanged.

## Impact

- `apps/api/app/interfaces/http/routes.py` changes only the encoding of answer
  SSE deltas; progress and metadata event contracts remain structured.
- `apps/web/hooks/transactions/use-rag-query/use-rag-query-stream.ts` accepts
  structured status data and raw Markdown delta data.
- `apps/web/app/console/query/retrieval-content.tsx` renders Markdown.
- No database, migration, logging, or provider-persistence changes are
  required.
