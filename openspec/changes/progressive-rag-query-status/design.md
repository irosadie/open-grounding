## Context

The existing stream waits for `RagQueryService.query` to return before emitting
the lifecycle events and the validated final answer. The answer must remain
behind guardrail, citation, and grounding validation, but the long-running
pipeline can safely report its current phase.

## Decisions

### Use a separate progress event

The backend emits `response.progress` with `{stage, message}`. Progress is
informational only and is never treated as answer content. Stages are bounded to
`planning`, `retrieving`, `generating`, and `validating`.

### Bridge service callbacks into SSE

The route starts the existing query as an asyncio task and forwards progress
callback messages from a queue while that task is running. This preserves the
existing service orchestration and lets the HTTP response flush status before
the final result is available.

### Preserve the safety boundary

The service emits `generating` before the model call and `validating` before the
answer guardrail/citation checks. It does not emit any answer text until the
existing query result has completed validation. Existing `response.delta`
chunking remains the only answer-content release path.

### UI behavior

The hook stores the latest progress message and the Query console displays it
while the request is streaming. A completed answer replaces the progress status
with the normal answer and citations; a failed request keeps the error state.

### Initialize conversation continuity at stream start

The SSE producer creates a conversation ID when the request does not provide
one and includes it in the initial `response.progress` event. The frontend
stores that ID immediately, while `response.started` continues to provide the
trace metadata after the query service completes. Follow-up queries therefore
reuse the same conversation even when the initial stream is stopped early.

### Selectable response delivery

The Query console keeps streaming enabled by default to preserve the current
experience and adds a checkbox for switching to the blocking response. The
streaming path continues to use SSE envelopes for lifecycle metadata,
conversation continuity, citations, and progress, but the answer area renders
only the validated text assembled from answer deltas. The blocking path parses
the normal JSON result and hydrates the same answer view, so switching modes
does not change grounding, validation, or citation behavior.

## Risks and Mitigations

- Progress messages can be delayed if a provider blocks before the next
  milestone. → Emit an initial `processing` message immediately from the SSE
  producer.
- A client may not know the new event. → Unknown SSE events remain ignorable;
  all existing events and payloads stay unchanged.
- Progress could be mistaken for answer content. → Use a distinct event name and
  never place answer text in its payload.
