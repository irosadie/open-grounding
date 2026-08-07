## 1. Domain Layer

- [x] 1.1 Add `save_message()` to `ConversationHistoryRepository` protocol in `conversation_repositories.py`
- [x] 1.2 Add `ensure_conversation()` to `ConversationHistoryRepository` protocol in `conversation_repositories.py`

## 2. Infrastructure Layer

- [x] 2.1 Implement `save_message()` in `SqlAlchemyConversationHistoryRepository` in `rag_conversations.py`
- [x] 2.2 Implement `ensure_conversation()` in `SqlAlchemyConversationHistoryRepository` in `rag_conversations.py` using INSERT ... ON CONFLICT DO NOTHING

## 3. Application Layer

- [x] 3.1 Add `_save_turn()` helper to `RagQueryService` — wraps ensure_conversation + save user message + save assistant message, silent on failure
- [x] 3.2 In `_query_admitted()`, generate `conversation_id` server-side if not provided
- [x] 3.3 Call `_save_turn()` (user message) before query pipeline runs
- [x] 3.4 Call `_save_turn()` (assistant message) after query result is returned
- [x] 3.5 Add `conversationId` to `_record_and_return()` result dict

## 4. HTTP Layer

- [x] 4.1 Add `conversationId` to `response.started` SSE event in `_stream_query()`

## 5. Tests

- [x] 5.1 Unit test: `save_message()` persists correct fields for USER and ASSISTANT speakers
- [x] 5.2 Unit test: `ensure_conversation()` is idempotent — no error on duplicate call
- [x] 5.3 Unit test: `_query_admitted()` generates conversation_id when none provided
- [x] 5.4 Unit test: user message saved before query, assistant message saved after
- [x] 5.5 Unit test: persistence failure does not propagate — query result still returned
- [x] 5.6 Unit test: `conversationId` present in response dict
