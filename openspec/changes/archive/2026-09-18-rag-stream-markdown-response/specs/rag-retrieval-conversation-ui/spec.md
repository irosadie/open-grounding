## MODIFIED Requirements

### Requirement: Streaming answers render SSE events in emitted order

The retrieval conversation UI SHALL consume the `text/event-stream` response
when streaming is requested. Progress and metadata events SHALL remain
structured, while each validated `response.delta` event SHALL carry Markdown
text that the UI renders progressively in emitted order. The UI MUST preserve
the exact concatenation of all answer deltas and MUST NOT mark the response
completed until the final queued answer unit is visible.

#### Scenario: Streamed grounded answer uses Markdown

- **WHEN** the backend emits progress events followed by Markdown answer
  deltas, citations, and completion metadata
- **THEN** the UI renders the answer as Markdown with ChatGPT-like formatting
- **AND** status, citations, and limitations remain available as structured
  response state

#### Scenario: Multiple deltas arrive together

- **WHEN** the stream receives two or more ordered `response.delta` events
- **THEN** the answer is revealed progressively in the same order
- **AND** the final rendered answer equals the concatenation of all deltas

#### Scenario: Grounded answer streams successfully

- **WHEN** the backend emits a successful ordered stream for a grounded query
  with multiple answer deltas
- **THEN** the UI shows the route and evidence level, reveals all answer
  deltas in order, then renders citations and limitations after completion

#### Scenario: Inferences and limitations appear at the end

- **WHEN** the validated answer contains inferences or limitations
- **THEN** the Markdown answer places those sections after the main answer
- **AND** the UI renders their bullets as Markdown content

#### Scenario: Non-streaming mode keeps JSON

- **WHEN** the query is requested with streaming disabled
- **THEN** the API returns the existing JSON envelope
- **AND** the UI renders its answer content with the same Markdown renderer

#### Scenario: Stream completion arrives before the queue drains

- **WHEN** `response.completed` is received while answer units remain queued
- **THEN** the hook keeps the request visually active
- **AND** it marks the request completed only after the final answer unit is
  rendered

#### Scenario: Active stream is aborted or replaced

- **WHEN** the user aborts the stream or starts a new query
- **THEN** pending answer units and timers from the old request are discarded
- **AND** stale content MUST NOT appear in the new answer

#### Scenario: Stream status remains visible

- **WHEN** the query is planning, retrieving, generating, or validating
- **THEN** the UI continues to show the latest status message
- **AND** status data is not appended to the Markdown answer

#### Scenario: Non-streaming query

- **WHEN** the query is requested with streaming disabled
- **THEN** the complete JSON answer is rendered immediately
- **AND** the existing completion state is preserved

#### Scenario: Stream fails mid-answer

- **WHEN** the backend emits a `response.failed` event or the stream breaks
- **THEN** the UI shows a failure state and stops appending answer deltas
- **AND** it does not fabricate citations or completion metadata
