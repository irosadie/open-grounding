## Why

Conversation messages are never persisted after a query completes. The `rag_conversation_messages` table exists and the repository protocol has `recent_messages()`, but nothing ever writes to it. This makes multi-turn conversation history impossible — the injection work from `conversation-history-injection` has no data to work with. For a production-grade open source RAG platform used as a chatbot middleware, server-side message persistence is non-negotiable.

## What Changes

- Add `save_message()` to `ConversationHistoryRepository` protocol
- Add `save_message()` implementation to `SqlAlchemyConversationHistoryRepository`
- Add `ensure_conversation()` to create a `rag_conversations` record if it doesn't exist yet
- After every query (grounded or abstain), persist: user message → run query → persist assistant answer
- If `conversation_id` is not provided by client, generate one server-side and return it in the response
- Return `conversationId` in every query response (streaming and non-streaming)

## Capabilities

### New Capabilities
- `conversation-message-persistence`: Save user messages and assistant answers to `rag_conversation_messages` after every query, enabling multi-turn conversation history

### Modified Capabilities
- `conversation-history-injection`: Now has actual data to inject — `_recent_messages()` will return populated history once persistence is in place

## Impact

**Affected code:**
- `apps/api/app/domain/rag/conversation_repositories.py` — add `save_message()` to protocol
- `apps/api/app/infrastructure/rag_conversations.py` — implement `save_message()` + `ensure_conversation()`
- `apps/api/app/application/rag_query_service.py` — persist messages around query execution
- `apps/api/app/interfaces/http/routes.py` — return `conversationId` in response

**Affected systems:**
- `rag_conversation_messages` table — will now receive writes
- `rag_conversations` table — will now receive writes for new conversations
- All query responses — will include `conversationId` field

**Backward compatibility:**
- `conversation_id` remains optional in request — server generates one if not provided
- Existing clients that don't use `conversation_id` are unaffected
- No schema migrations needed — tables already exist
