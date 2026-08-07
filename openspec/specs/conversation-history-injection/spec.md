# conversation-history-injection Specification

## Purpose
TBD - created by archiving change conversation-history-injection. Update Purpose after archive.
## Requirements
### Requirement: GenerationAdapter supports messages array
The `GenerationAdapter` protocol SHALL accept an optional `messages` parameter containing a list of role-based message dicts in addition to the existing `prompt` parameter. When `messages` is provided, the adapter MUST use it as the conversation history context. When only `prompt` is provided, the adapter MUST behave exactly as before (backward compatible).

#### Scenario: Generate with messages array
- **WHEN** `generate()` is called with `messages=[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]`
- **THEN** the adapter MUST forward those messages to the LLM provider in native chat format

#### Scenario: Generate with prompt only (backward compat)
- **WHEN** `generate()` is called with only `prompt` and no `messages`
- **THEN** the adapter MUST behave identically to the current implementation

#### Scenario: Both prompt and messages provided
- **WHEN** `generate()` is called with both `prompt` and `messages`
- **THEN** `messages` takes precedence and `prompt` is appended as the final user message

### Requirement: Recent conversation messages are injected into generation
The `RagQueryService` SHALL capture the return value of `_recent_messages()` and pass the messages as structured chat history to the generation step. Messages MUST be formatted with explicit `USER` and `ASSISTANT` roles derived from `ConversationSpeaker` values.

#### Scenario: Conversation ID provided with prior messages
- **WHEN** a query is submitted with a `conversation_id` that has prior messages in the database
- **THEN** the generation request MUST include those messages as role-based chat history before the current question

#### Scenario: No conversation ID provided
- **WHEN** a query is submitted without a `conversation_id`
- **THEN** no conversation history is injected and generation proceeds as before

#### Scenario: Conversation ID provided but no prior messages
- **WHEN** a query is submitted with a `conversation_id` that has zero prior messages
- **THEN** no conversation history is injected and generation proceeds normally

### Requirement: Conversation history respects token budget
The number of recent messages injected SHALL be bounded by `rag_query_recent_messages` setting (already exists). The service MUST NOT inject more messages than this limit.

#### Scenario: History exceeds configured limit
- **WHEN** a conversation has more messages than `rag_query_recent_messages`
- **THEN** only the most recent N messages (up to the limit) are injected

#### Scenario: History within limit
- **WHEN** a conversation has fewer or equal messages than `rag_query_recent_messages`
- **THEN** all available messages are injected

### Requirement: Long-term memory and conversation history coexist
When both Qdrant-based long-term memory chunks and short-term conversation history are available, both SHALL be included in the generation context. Long-term memory is passed as `supplementary` context; short-term history is passed as the `messages` array. Neither MUST override or discard the other.

#### Scenario: Both memory and history available
- **WHEN** a query has both memory chunks retrieved from Qdrant and recent messages from DB
- **THEN** generation receives both — messages array for history and supplementary for memory context

#### Scenario: Only memory available
- **WHEN** a query has memory chunks but no conversation history
- **THEN** generation receives only supplementary context (existing behavior preserved)

#### Scenario: Only history available
- **WHEN** a query has conversation history but no memory chunks
- **THEN** generation receives only the messages array and no supplementary context

### Requirement: LLMGenerationAdapter formats messages for provider
The `LLMGenerationAdapter` SHALL convert the `messages` list to the provider-native format before sending. For OpenAI and Ollama, messages MUST be inserted between the system prompt and the final user message containing the grounded prompt.

#### Scenario: OpenAI provider with messages
- **WHEN** `generate()` is called with messages and provider is OpenAI
- **THEN** the API call MUST include `[system, ...history_messages, user_with_prompt]` in the messages array

#### Scenario: Ollama provider with messages
- **WHEN** `generate()` is called with messages and provider is Ollama
- **THEN** the API call MUST include `[system, ...history_messages, user_with_prompt]` in the messages array

