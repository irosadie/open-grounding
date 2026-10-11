## Context

The API has two delivery paths behind one query route. Blocking requests return
the current JSON envelope. Streaming requests must carry both progress metadata
and answer content, so the response remains `text/event-stream`; only answer
delta payloads need to switch from JSON objects to Markdown text.

## Decisions

### Preserve JSON for blocking mode

`stream=false` is unchanged. The existing response envelope remains the stable
machine-readable contract for clients that need structured fields.

### Use typed SSE events for status and raw data SSE for answer deltas

Progress, route, retrieval summary, citations, completion, and failure events
continue to use compact JSON data. `response.delta` uses SSE text data lines so
the answer is Markdown rather than `{"answer": ...}`. The parser accepts both
forms during the transition, but new stream responses use raw Markdown deltas.

### Render the same validated Markdown in the UI

The service already creates the final validated answer text from facts,
inferences, conflicts, and limitations. The UI uses `react-markdown` with GFM
support for both modes, so headings, bullets, and emphasis are presented as a
conversation answer instead of literal Markdown syntax.

### Preserve the safety boundary

Only the already validated final answer is converted to Markdown and emitted.
Pipeline status remains separate from answer content. No raw hidden reasoning
or unvalidated provider token is released.

## Risks / Mitigations

- **Risk:** Markdown lines could be parsed as separate SSE fields. → Prefix
  every Markdown line with `data:` and join data lines in the client parser.
- **Risk:** Existing clients expect JSON delta data. → Keep parser fallback for
  the old `{answer: ...}` shape while the backend emits raw text going forward.
- **Risk:** Citation or limitation metadata could be lost. → Keep citations and
  completion metadata as separate structured events and retain existing tests.
