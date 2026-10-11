## MODIFIED Requirements

### Requirement: Streaming answers render SSE events in emitted order

The retrieval conversation UI SHALL, when streaming is requested, consume the
`text/event-stream` response and render validated `response.delta` content in
event order through a bounded client-side typewriter queue, even when multiple
deltas arrive in the same network read. It MUST preserve the exact
concatenation of all answer deltas and MUST NOT mark the response completed
until the final queued answer unit is visible.

#### Scenario: Multiple deltas arrive together

- **WHEN** the stream receives two or more ordered `response.delta` events
- **THEN** the answer is revealed progressively in the same order
- **AND** the final rendered answer equals the concatenation of all deltas

#### Scenario: Grounded answer streams successfully

- **WHEN** the backend emits a successful ordered stream for a grounded query
  with multiple answer deltas
- **THEN** the UI shows the route and evidence level, reveals all answer
  deltas in order, then renders citations and limitations after completion

#### Scenario: Stream fails mid-answer

- **WHEN** the backend emits a `response.failed` event or the stream breaks
- **THEN** the UI shows a failure state, stops appending deltas, and offers a
  retry without fabricating a citation or answer

#### Scenario: Stream completion arrives before the queue drains

- **WHEN** `response.completed` is received while answer units remain queued
- **THEN** the hook keeps the request visually active
- **AND** it marks the request completed only after the final answer unit is
  rendered

#### Scenario: Active stream is aborted or replaced

- **WHEN** the user aborts the stream or starts a new query
- **THEN** pending answer units and timers from the old request are discarded
- **AND** stale content MUST NOT appear in the new answer

#### Scenario: Non-streaming query

- **WHEN** the query is requested with streaming disabled
- **THEN** the complete JSON answer is rendered immediately
- **AND** the existing completion state is preserved
