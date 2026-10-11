## ADDED Requirements

### Requirement: Show streamed query progress

The Query console MUST display the latest progress message while a streamed
query is active and MUST continue appending ordered `response.delta` events as
the final validated answer.

#### Scenario: User sees pipeline progress

- **WHEN** the stream receives a `response.progress` event
- **THEN** the UI MUST update the visible status to that event's message
- **AND** the UI MUST keep the query controls disabled until the stream ends

#### Scenario: Answer content is separate from progress

- **WHEN** progress events are received before answer deltas
- **THEN** the UI MUST NOT append progress messages to the answer text
- **AND** answer text MUST be composed only from `response.delta` payloads

### Requirement: Preserve conversation identity during streaming

The streaming client MUST retain the conversation ID as soon as the server
provides it, before the final answer lifecycle events arrive.

#### Scenario: Follow-up after an interrupted stream

- **WHEN** the initial `response.progress` event includes a `conversationId`
- **THEN** the client MUST store that ID
- **AND** a subsequent query from the same console MUST send it as
  `conversation_id`

### Requirement: Let the user choose streamed or blocking delivery

The Query console MUST expose a Stream checkbox, enabled by default, that
selects whether the request uses the SSE response or the blocking response.
When streaming is enabled, the UI MUST render only the validated answer text
and MUST NOT expose raw SSE/JSON payloads to the user. When streaming is
disabled, the UI MUST render the completed JSON result using the same answer,
evidence, citation, limitation, and feedback presentation.

#### Scenario: User disables streaming

- **WHEN** the user clears the Stream checkbox and submits a valid question
- **THEN** the request MUST set `stream` to `false`
- **AND** the UI MUST show the completed answer after the blocking response
  returns

#### Scenario: User enables streaming

- **WHEN** the user checks the Stream checkbox and submits a valid question
- **THEN** the request MUST set `stream` to `true`
- **AND** the UI MUST append only validated answer text as it arrives
- **AND** the UI MUST NOT display raw JSON or SSE envelope data
