# rag-retrieval-conversation-ui Specification

## Purpose
TBD - created by archiving change rag-console-ui. Update Purpose after archive.

## Requirements

### Requirement: Query composition requires a knowledge base and a bounded message

The retrieval conversation UI SHALL require the user to select at least one knowledge base and
enter a non-empty message before submitting a query to `/rag/query`. It MUST validate the
message length client-side against the backend bound and MUST NOT submit an empty or oversized
message.

#### Scenario: User submits a valid question

- **WHEN** an authenticated user selects one or more knowledge bases and submits a bounded
  message
- **THEN** the UI sends the query through the BFF proxy to `/rag/query` and begins rendering
  the response stream or single response

#### Scenario: User submits without a knowledge base

- **WHEN** a user attempts to submit with no knowledge base selected or an empty message
- **THEN** the UI blocks submission and shows validation errors without contacting the backend

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

### Requirement: Citations render with snippet and locator

The retrieval conversation UI SHALL render each citation with its title, snippet, and locator
when available, linking back to the source document version in the ingestion workbench when
permitted. It MUST NOT display raw vectors, hidden prompts, or cross-tenant metadata.

#### Scenario: Answer includes citations

- **WHEN** a completed answer includes one or more citations
- **THEN** the UI lists each citation with title, snippet, and locator and the user can open
  the cited source if authorized

### Requirement: Insufficient evidence and abstain routes are surfaced clearly

The retrieval conversation UI SHALL visibly distinguish a `clarify` or `abstain` route and an
evidence level of low or none from a grounded answer. It MUST NOT present an abstention as a
factual answer and MUST show the stated limitation.

#### Scenario: The backend abstains due to insufficient evidence

- **WHEN** the query route is `abstain` or the evidence level is `none`
- **THEN** the UI shows that the system could not answer from the available evidence and
  displays the limitation rather than a fabricated answer

### Requirement: Answer feedback is recordable for retained traces

The retrieval conversation UI SHALL allow the user to submit optional 1-5 rating and bounded
comment feedback to `/rag/query/traces/{trace_id}/feedback` for a completed, retained answer.
It MUST disable feedback when the trace is unavailable and MUST NOT fabricate a trace
identifier.

#### Scenario: User rates a completed answer

- **WHEN** a user submits a rating and optional comment for a retained completed answer
- **THEN** the UI records the feedback against the trace and confirms success or shows that
  the trace is no longer available
