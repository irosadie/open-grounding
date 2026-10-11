## ADDED Requirements

### Requirement: Stream safe query progress

The RAG streaming endpoint MUST be able to emit bounded `response.progress`
events while planning, retrieving evidence, generating, and validating a query.

#### Scenario: Progress precedes the final answer

- **WHEN** a streamed query is processing
- **THEN** the endpoint MAY emit `response.progress` events with a `stage` and
  human-readable `message` before the final answer events
- **AND** progress payloads MUST NOT contain answer text, hidden reasoning, or
  unvalidated source claims

#### Scenario: Final answer remains validation-gated

- **WHEN** the model is generating or the answer is being validated
- **THEN** the endpoint MUST NOT emit `response.delta` answer content yet
- **AND** `response.delta` MUST continue to contain only the validated final
  answer content
