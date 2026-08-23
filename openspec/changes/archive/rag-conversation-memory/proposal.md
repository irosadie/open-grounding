# Proposal: RAG Conversation Memory

## Problem

The current conversation history is session-scoped — it only persists within a single
browser session. When a user starts a new session, all prior context is lost. This forces
users to re-explain their background, preferences, and prior work every time they open
a new conversation.

For a RAG platform used in production, this is a significant usability gap. A legal
researcher who has been asking questions about contract law for weeks should not have to
re-establish context every session. A support engineer who prefers concise technical
answers should not have to re-state that preference repeatedly.

## Proposed Solution

A **hybrid summarization + vector memory** system that:

1. Summarizes completed conversation sessions in the background (no query latency impact)
2. Embeds memory summaries into a dedicated per-user-per-KB vector collection
3. Retrieves semantically relevant memories at query time and injects them as context
4. Enforces explicit user opt-in — memory is never on by default
5. Applies configurable TTL-based retention + pruning per knowledge base

Memory is scoped **per user per knowledge base** — ensuring domain isolation, clean
deletion semantics, and precise retrieval without cross-domain noise.

## Key Design Decisions

- **Hybrid summarization + vector**: raw messages are summarized before embedding — reduces noise, improves retrieval quality, saves storage
- **Background worker**: summarization runs after session ends via worker queue — zero latency impact on query path
- **Per user per KB scoping**: memory isolated by (user_id, knowledge_base_id) — domain clean, privacy manageable
- **Explicit opt-in**: user must enable memory per KB, never default on
- **TTL-based retention**: memory chunks expire automatically — configurable per KB, default 90 days
- **Qdrant dedicated collection**: memory stored in `memory` collection separate from `rag` collection — no cross-contamination
- **Retrieval at query time**: top-K relevant memories injected as system context before generation — not concatenated blindly

## What This Is Not

- Not a replacement for conversation history (session context still exists)
- Not a user profile or CRM system
- Not a knowledge base — memory is user-specific, not shared across users
- Not always-on — requires explicit opt-in per KB

## Success Criteria

- Users can reference prior session context without re-explaining
- Memory retrieval adds <100ms to query latency (async embed already done)
- Memory is provably isolated per user per KB
- Users can view, disable, and clear their memory from the UI
- All existing tests pass; new tests cover memory path

## Scope

**In scope:**
- `MemoryConfig` entity per KB (opt-in toggle, TTL, summarization model, retrieval top-K)
- `MemoryChunk` entity — summarized session memories per user per KB
- Background worker job: session summarization → embed → store in Qdrant `memory` collection
- Query-time memory retrieval + context injection
- API: CRUD for MemoryConfig, list/clear user memory
- Frontend: memory config UI under KB settings, user memory management page
- Shared Zod schemas + types

**Out of scope:**
- Entity/fact extraction from conversations
- Cross-KB memory
- Memory sharing between users
- Real-time memory updates during active session
