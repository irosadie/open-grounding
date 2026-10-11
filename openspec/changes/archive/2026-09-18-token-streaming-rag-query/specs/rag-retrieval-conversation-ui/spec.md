## MODIFIED Requirements

### Requirement: Streaming answers render SSE events in emitted order
The retrieval conversation UI SHALL, when streaming is requested, consume the
`text/event-stream` response and render events in the order emitted: `response.started`,
`response.route`, `response.retrieval_summary`, one or more `response.delta` events,
`response.citations`, `response.completed`, and `response.failed`. It MUST append answer
deltas in order to form the released answer and MUST NOT render citations or limitations
before the completion event.

#### Scenario: Grounded answer streams successfully
- **WHEN** the backend emits a successful ordered stream for a grounded query with
  multiple answer deltas
- **THEN** the UI shows the route and evidence level, appends all answer deltas in
  order, then renders citations and limitations after the completion event

#### Scenario: Stream fails mid-answer
- **WHEN** the backend emits a `response.failed` event or the stream breaks
- **THEN** the UI shows a failure state, stops appending deltas, and offers a retry
  without fabricating a citation or answer
