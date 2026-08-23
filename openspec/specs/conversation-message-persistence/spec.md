# conversation-message-persistence Specification

## Purpose
TBD - created by archiving change conversation-message-persistence. Update Purpose after archive.
## Requirements
### Requirement: ConversationHistoryRepository exposes save_message
The `ConversationHistoryRepository` protocol SHALL expose a `save_message()` method that persists a single `ConversationMessage` to the `rag_conversation_messages` table. The method MUST be idempotent on the message ID.

#### Scenario: Save a user message
- **WHEN** `save_message()` is called with a `ConversationMessage` with speaker `USER`
- **THEN** the message MUST be persisted to `rag_conversation_messages` with correct tenant, conversation, speaker, content, and timestamp

#### Scenario: Save an assistant message
- **WHEN** `save_message()` is called with a `ConversationMessage` with speaker `ASSISTANT`
- **THEN** the message MUST be persisted to `rag_conversation_messages` with speaker `ASSISTANT`

### Requirement: ConversationHistoryRepository exposes ensure_conversation
The `ConversationHistoryRepository` protocol SHALL expose an `ensure_conversation()` method that creates a `rag_conversations` record for the given `conversation_id` if one does not already exist. If it already exists, it MUST be a no-op.

#### Scenario: New conversation
- **WHEN** `ensure_conversation()` is called with a `conversation_id` that does not exist in `rag_conversations`
- **THEN** a new record MUST be created with the given tenant, user, and conversation ID

#### Scenario: Existing conversation
- **WHEN** `ensure_conversation()` is called with a `conversation_id` that already exists
- **THEN** no duplicate record is created and no error is raised

### Requirement: User message is persisted before query execution
The `RagQueryService` SHALL persist the user's message to `rag_conversation_messages` before running the query pipeline. If `conversation_id` is not provided, the service MUST generate a new UUID and use it for the entire request lifecycle.

#### Scenario: Query with existing conversation_id
- **WHEN** a query is submitted with an existing `conversation_id`
- **THEN** the user message MUST be saved under that conversation before retrieval begins

#### Scenario: Query without conversation_id
- **WHEN** a query is submitted without a `conversation_id`
- **THEN** the service MUST generate a new UUID as `conversation_id`, save the user message under it, and use it throughout the request

### Requirement: Assistant answer is persisted after query execution
After a query completes (grounded or abstain), the `RagQueryService` SHALL persist the assistant's answer as a `ConversationMessage` with speaker `ASSISTANT`. For abstain routes, the limitations text MUST be saved as the assistant message content.

#### Scenario: Grounded answer persisted
- **WHEN** a query returns a grounded answer
- **THEN** the answer text MUST be saved to `rag_conversation_messages` with speaker `ASSISTANT` under the same conversation

#### Scenario: Abstain answer persisted
- **WHEN** a query returns an abstain route
- **THEN** the limitations text MUST be saved as the assistant message with speaker `ASSISTANT`

### Requirement: conversationId is returned in every query response
Every query response (streaming and non-streaming) SHALL include a `conversationId` field containing the server-owned conversation identifier. Clients MUST use this value in subsequent requests to continue the conversation.

#### Scenario: Non-streaming response includes conversationId
- **WHEN** a non-streaming query completes
- **THEN** the response payload MUST include `"conversationId": "<uuid>"`

#### Scenario: Streaming response includes conversationId
- **WHEN** a streaming query completes
- **THEN** the `response.started` SSE event MUST include `"conversationId": "<uuid>"`

#### Scenario: New conversation returns generated conversationId
- **WHEN** a query is submitted without a `conversation_id`
- **THEN** the response MUST include the server-generated `conversationId` so the client can use it in follow-up requests

### Requirement: Message persistence does not block or fail the query
If `save_message()` raises an exception, the query pipeline MUST continue and return the answer. Persistence failures SHALL be logged as warnings but MUST NOT propagate as HTTP errors.

#### Scenario: DB write fails on user message
- **WHEN** `save_message()` for the user message raises a database exception
- **THEN** the query MUST continue and return a result; the error MUST be logged

#### Scenario: DB write fails on assistant message
- **WHEN** `save_message()` for the assistant message raises a database exception
- **THEN** the response is already computed and MUST be returned; the error MUST be logged

