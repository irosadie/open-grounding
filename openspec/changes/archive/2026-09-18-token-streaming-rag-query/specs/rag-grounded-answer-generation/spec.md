## MODIFIED Requirements

### Requirement: SSE emits only safe final answer content
The system SHALL support SSE events for start, route, retrieval summary, answer delta,
citations, completion, and failure. It MUST emit answer deltas only after the final
answer has passed required validation. A validated answer MAY be split across multiple
ordered `response.delta` events, and concatenating those events in order MUST reproduce
the released answer. The system MUST NOT emit secrets, raw vectors, hidden prompts,
hidden reasoning, or cross-tenant metadata.

#### Scenario: Validated answer streams to a client
- **WHEN** a query requests streaming and answer validation succeeds
- **THEN** the client receives ordered SSE events ending in final citations,
  limitations, evidence level, and trace identity, and the ordered answer deltas
  concatenate to the validated answer

#### Scenario: Unvalidated generation never reaches the stream
- **WHEN** answer validation fails after any bounded repair attempt
- **THEN** the system emits a safe abstention or failure outcome and emits no answer delta
