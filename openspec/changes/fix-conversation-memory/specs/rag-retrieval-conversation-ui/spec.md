## ADDED Requirements

### Requirement: Retrieval sessions preserve conversation continuity

After receiving the server-issued conversation ID from a streaming query response, the
retrieval UI SHALL include that ID in subsequent query requests made during the same page
session. Starting a new page session or explicitly resetting the query state SHALL clear
the stored conversation ID.

#### Scenario: Follow-up question reuses the server conversation
- **WHEN** the UI receives a `conversationId` in `response.started` and the user submits another question
- **THEN** the next request includes that conversation ID as `conversation_id`

#### Scenario: First question starts a new conversation
- **WHEN** the user submits a question before any conversation ID has been received
- **THEN** the request omits `conversation_id` and the UI stores the ID returned by the server

#### Scenario: Reset starts a fresh conversation
- **WHEN** the retrieval query state is reset
- **THEN** the stored conversation ID is cleared and the next question starts a new conversation
