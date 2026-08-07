## Context

The `rag_conversation_messages` and `rag_conversations` tables exist and are fully migrated. The `ConversationHistoryRepository` protocol only exposes `recent_messages()` — there is no write path. The `conversation-history-injection` change wired up the read path correctly, but without persistence, the tables are always empty.

**Current state:**
- `rag_conversation_messages` — table exists, never written to
- `rag_conversations` — table exists, only written to by memory summarizer (not by query flow)
- `ConversationHistoryRepository` — read-only protocol
- `RagQueryService` — no save calls anywhere
- `conversation_id` — optional in request, never returned in response

**Constraints:**
- No new migrations needed — tables already exist
- Persistence failures must never fail the query — availability over consistency
- `conversation_id` must be server-generated if not provided — clients must not forge history

## Goals / Non-Goals

**Goals:**
- Persist user + assistant messages after every query
- Generate `conversation_id` server-side when not provided
- Return `conversationId` in every response so clients can continue conversations
- Keep persistence failures silent (log only, never HTTP 500)

**Non-Goals:**
- Changing how history is injected into generation (already done)
- Adding UI toggles or per-KB conversation config
- Conversation management endpoints (list, delete, export)
- Changing the memory summarization flow

## Decisions

### Decision 1: Generate conversation_id server-side when missing

**Choice:** If `conversation_id` is not in the request, `RagQueryService` generates a UUID before saving the user message and uses it for the full request lifecycle.

**Rationale:**
- Prevents client history forgery — server owns the ID
- Clients don't need to pre-create conversations
- Simple: one UUID generated once per new conversation

**Alternatives considered:**
- **Require conversation_id always**: Rejected — breaks backward compat and adds friction for simple integrations
- **Let client generate**: Rejected — security risk, clients could inject fake history

### Decision 2: Persist in RagQueryService, not in the HTTP layer

**Choice:** Save messages inside `RagQueryService._save_turn()`, called from `_query_admitted()`.

**Rationale:**
- HTTP layer should not own business logic
- Service layer already owns conversation_id threading
- Consistent between streaming and non-streaming paths (both go through the same service)

**Alternatives considered:**
- **Persist in route handler**: Rejected — duplicates logic between stream and non-stream handlers, leaks domain concerns into HTTP layer

### Decision 3: Persist abstain answers as assistant messages

**Choice:** Save limitations text as assistant message even for abstain routes.

**Rationale:**
- Conversation history should be complete — LLM needs to know it abstained previously
- Prevents user re-asking the same unanswerable question in the same session
- Consistent behavior — every turn has exactly one user + one assistant message

**Alternatives considered:**
- **Skip saving on abstain**: Rejected — creates gaps in conversation thread, LLM loses context

### Decision 4: Persistence failures are silent

**Choice:** Wrap all `save_message()` calls in try/except, log warnings, never raise.

**Rationale:**
- Query availability is more important than history completeness
- A missed message is recoverable; a failed query is not
- Enterprise users expect the RAG answer to always come back

### Decision 5: Return conversationId in response and SSE started event

**Choice:** Add `conversationId` to `_record_and_return()` result dict and to `response.started` SSE event.

**Rationale:**
- Client needs the ID to continue the conversation in follow-up requests
- `response.started` is the first SSE event — client gets the ID immediately without waiting for completion
- Non-streaming response already returns a dict — trivial to add the field

## Risks / Trade-offs

**[Risk]** Race condition if client sends two requests with the same new `conversation_id` simultaneously  
→ **Mitigation:** `ensure_conversation()` uses INSERT ... ON CONFLICT DO NOTHING — idempotent by design

**[Risk]** Large conversations accumulate many messages, slowing `recent_messages()` query  
→ **Mitigation:** Already bounded by `rag_query_recent_messages` setting; index on `(conversation_id, created_at)` already exists via migration

**[Trade-off]** Abstain answers saved as assistant messages increases message count  
→ **Benefit:** Complete conversation thread for better multi-turn context

## Migration Plan

No database migrations needed — `rag_conversations` and `rag_conversation_messages` tables already exist.

**Deployment:**
1. Add write methods to protocol + infrastructure
2. Add `_save_turn()` helper to `RagQueryService`
3. Wire into `_query_admitted()` — save user message before query, assistant message after
4. Add `conversationId` to response dict and SSE started event
5. Deploy — zero downtime, fully backward compatible

**Rollback:** Revert `_save_turn()` call in `_query_admitted()`. Tables remain intact with whatever was written.

## Open Questions

None.
