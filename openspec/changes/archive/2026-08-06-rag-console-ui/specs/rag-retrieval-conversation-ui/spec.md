## ADDED Requirements

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

The retrieval conversation UI SHALL, when streaming is requested, consume the
`text/event-stream` response and render events in the order emitted: `response.started`,
`response.route`, `response.retrieval_summary`, `response.delta`, `response.citations`,
`response.completed`, and `response.failed`. It MUST append answer deltas in order and MUST
NOT render citations or limitations before the completion event.

#### Scenario: Grounded answer streams successfully

- **WHEN** the backend emits a successful ordered stream for a grounded query
- **THEN** the UI shows the route and evidence level, appends answer deltas progressively,
  then renders citations and limitations after the completion event

#### Scenario: Stream fails mid-answer

- **WHEN** the backend emits a `response.failed` event or the stream breaks
- **THEN** the UI shows a failure state, stops appending deltas, and offers a retry without
  fabricating a citation or answer

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