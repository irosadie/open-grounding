## Context

The existing `/rag/query?stream=true` path already uses an SSE BFF and emits the
required lifecycle events, but `_stream_query` waits for the complete validated query
result and emits the answer in one `response.delta`. The frontend hook currently
replaces its answer state whenever it receives a delta.

The existing safety contract requires validation before answer content is released.
This design keeps that boundary intact and makes the released answer progressive at the
SSE/UI layer.

## Goals / Non-Goals

**Goals:**

- Emit a validated answer as multiple ordered SSE deltas.
- Preserve the current event names, payload shape, routes, and single-delta clients.
- Render the deltas progressively in the console UI.
- Keep all raw model output behind the existing schema, citation, and guardrail checks.

**Non-Goals:**

- Exposing provisional model tokens before validation.
- Changing the generation provider port or adding a provider-specific streaming API.
- Changing the blocking response, persistence model, or conversation contract.
- Redesigning the SSE BFF or adding WebSockets.

## Decisions

### Chunk only the released answer

The backend will keep calling the existing query service and will split only the final
`answer` string returned after validation. Chunks will use bounded word-aware segments
so punctuation and words are not unnecessarily cut. Each chunk uses the existing
`response.delta` event and `answer` field, so older clients that expect one event remain
compatible.

Alternative considered: stream raw provider tokens and validate afterward. Rejected
because it would expose content before citation and policy validation, contradicting
the existing safety contract.

### Append deltas in the client

The stream hook will append each `response.delta` payload to the current answer instead
of replacing it. A single delta therefore behaves exactly as before, while multiple
deltas compose the final answer. Parsing remains event-order based and citations and
limitations remain gated by `response.completed`.

### Keep chunking server-owned

Chunking belongs in the SSE producer so every client receives the same ordered payload
and no client needs to infer boundaries. No new request field or public setting is
introduced in this change.

## Risks / Trade-offs

- [Risk] Chunking after validation does not reduce time-to-first-answer; it only makes
  the released answer render progressively. → Mitigation: keep the behavior explicit
  in documentation and preserve the safety-first contract.
- [Risk] Very small chunks increase event overhead. → Mitigation: use a bounded,
  word-aware chunk size and cover ordering with tests.
- [Risk] A stream may terminate after some deltas. → Mitigation: the UI keeps the
  failed state and does not present citations or limitations as complete results.

## Migration Plan

Deploy the backend and frontend together. Existing clients continue to work because
the event name and payload field are unchanged; they may simply observe multiple delta
events. Roll back by reverting the backend chunk loop and client append behavior.
