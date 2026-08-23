# Spec: RAG Conversation Memory

## Overview

Conversation memory is an opt-in persistent memory layer that summarizes completed
conversation sessions, embeds the summaries into a dedicated vector store, and retrieves
semantically relevant memories at query time to inject as additional context before
generation. Memory is scoped per user per knowledge base.

---

## Requirements

### REQ-1: MemoryConfig Entity

**REQ-1.1** The system SHALL provide a `MemoryConfig` entity attached 1:1 to a
`KnowledgeBase`. If absent, the KB operates without memory.

**REQ-1.2** `MemoryConfig` SHALL contain:
- `enabled` (bool) — master opt-in switch, default false
- `summarization_model_profile_id` (FK → ModelProfile) — MUST reference a generation model
- `embedding_profile_id` (FK → ModelProfile) — MUST reference a dense embedding model
- `retention_days` (int, 1–365, default 90)
- `retrieval_top_k` (int, 1–20, default 5)
- `min_turns_to_summarize` (int, 1–20, default 3)
- `system_prompt` (text, Jinja2 template) — prompt for summarization LLM

**REQ-1.3** Creating a `MemoryConfig` with a `summarization_model_profile_id` that
references an embedding or sparse profile SHALL be rejected with `INVALID_MODEL_PROFILE_KIND`.

**REQ-1.4** Creating a `MemoryConfig` with an `embedding_profile_id` that references
a generation or sparse profile SHALL be rejected with `INVALID_MODEL_PROFILE_KIND`.

**REQ-1.5** The `system_prompt` Jinja2 template SHALL be validated at save time.
Invalid templates SHALL be rejected with `INVALID_PROMPT_TEMPLATE`.

**REQ-1.6** Available Jinja2 variables for `system_prompt`:
`{{ conversation_messages }}`, `{{ knowledge_base_name }}`, `{{ turn_count }}`

**REQ-1.7** Deleting a `MemoryConfig` SHALL cascade-delete all `MemoryChunk` records
for that KB and remove their corresponding Qdrant points.

---

### REQ-2: MemoryChunk Entity

**REQ-2.1** A `MemoryChunk` represents a summarized conversation session and SHALL contain:
- `id` (uuid)
- `tenant_id` (FK → tenants)
- `knowledge_base_id` (FK → rag_knowledge_bases)
- `user_id` (FK → users)
- `conversation_id` (FK → rag_conversations)
- `summary` (text) — LLM-generated summary
- `qdrant_point_id` (str) — reference to vector store point
- `embedding_profile_id` (str) — profile used to embed this chunk
- `turn_count` (int) — number of turns summarized
- `expires_at` (datetime) — computed at creation: `now() + retention_days`
- `created_at` (datetime)

**REQ-2.2** One conversation SHALL produce at most one `MemoryChunk`. Attempting to
summarize an already-summarized conversation SHALL be a no-op.

**REQ-2.3** `MemoryChunk.expires_at` SHALL be computed from the KB's `MemoryConfig.retention_days`
at the time of chunk creation. Changing `retention_days` later SHALL NOT retroactively
update existing chunks.

---

### REQ-3: Summarization Worker Job

**REQ-3.1** A worker job `memory.summarize` SHALL be available in the ingestion worker
queue infrastructure.

**REQ-3.2** The job SHALL be triggered when a conversation is marked complete or has
been idle for >30 minutes with at least `min_turns_to_summarize` turns.

**REQ-3.3** The job SHALL:
1. Load conversation messages from DB
2. Check `turn_count >= min_turns_to_summarize` — if not, skip silently
3. Check conversation not already summarized — if already, skip silently
4. Render Jinja2 `system_prompt` with conversation data
5. Call summarization LLM via existing provider registry
6. Embed resulting summary via `embedding_profile_id`
7. Upsert to Qdrant `memory` collection with payload: `{ tenant_id, knowledge_base_id, user_id, chunk_id, expires_at }`
8. Save `MemoryChunk` to DB
9. Mark conversation as `summarized`

**REQ-3.4** If the summarization LLM call fails, the job SHALL retry up to 3 times with
exponential backoff before moving to dead letter queue.

**REQ-3.5** If Qdrant upsert fails after successful LLM call, the job SHALL retry
Qdrant upsert only (do not re-call LLM).

---

### REQ-4: Pruning Worker Job

**REQ-4.1** A worker job `memory.prune` SHALL run daily to delete expired memory chunks.

**REQ-4.2** The job SHALL:
1. Query all `MemoryChunk` records where `expires_at < now()`
2. Delete corresponding Qdrant points by `qdrant_point_id`
3. Delete `MemoryChunk` records from DB

**REQ-4.3** Pruning SHALL be batched — process max 500 chunks per job run to avoid
long-running transactions.

**REQ-4.4** Pruning failures for individual chunks SHALL be logged and skipped — the
job SHALL continue processing remaining chunks.

---

### REQ-5: Query-time Memory Retrieval

**REQ-5.1** At query time, if the KB has `MemoryConfig.enabled = true` AND the request
does not explicitly disable memory, the system SHALL retrieve relevant memories.

**REQ-5.2** Memory retrieval SHALL:
1. Embed the current query using `MemoryConfig.embedding_profile_id`
2. Search Qdrant `memory` collection filtered by: `tenant_id + knowledge_base_id + user_id + expires_at > now()`
3. Return top-`retrieval_top_k` results

**REQ-5.3** Retrieved memories SHALL be injected as a system context block before
generation, clearly labeled:
```
[Relevant context from prior conversations:]
- {memory_summary_1}
- {memory_summary_2}
```

**REQ-5.4** If memory retrieval fails (Qdrant unavailable, timeout), the system SHALL
log the failure, skip memory injection, and proceed with the standard query pipeline.
Memory retrieval failure SHALL NOT fail the query.

**REQ-5.5** Memory retrieval timeout SHALL be bounded to 2 seconds.

**REQ-5.6** Memory retrieval SHALL NOT be performed if the user has no memory chunks
for the given KB (fast path check via DB count before Qdrant call).

---

### REQ-6: Query API Extension

**REQ-6.1** `POST /rag/query` SHALL accept an optional `memory` object:
```json
{
  "memory": {
    "enabled": false
  }
}
```

**REQ-6.2** If `memory.enabled` is explicitly `false`, memory retrieval SHALL be skipped
regardless of KB config.

**REQ-6.3** If the `memory` field is absent, KB config SHALL be used.

**REQ-6.4** Query response trace SHALL include memory metadata:
```json
{
  "memory": {
    "triggered": true,
    "chunks_retrieved": 3,
    "oldest_memory_age_days": 12
  }
}
```

---

### REQ-7: MemoryConfig API

**REQ-7.1** `POST /rag/knowledge-bases/{id}/memory-config` — create or replace config

**REQ-7.2** `GET /rag/knowledge-bases/{id}/memory-config` — get config (404 if not set)

**REQ-7.3** `DELETE /rag/knowledge-bases/{id}/memory-config` — delete config + cascade
delete all memory chunks for this KB

**REQ-7.4** `GET /rag/knowledge-bases/{id}/memory-config/defaults` — return default
system prompt template

All endpoints MUST be tenant-scoped.

---

### REQ-8: User Memory Management API

**REQ-8.1** `GET /rag/memory?knowledge_base_id={id}` — list authenticated user's memory
chunks for a KB, paginated (page, page_size), ordered by created_at desc

**REQ-8.2** `DELETE /rag/memory?knowledge_base_id={id}` — clear all memory chunks for
authenticated user in a specific KB

**REQ-8.3** `DELETE /rag/memory/{chunk_id}` — delete specific memory chunk (user can
only delete their own)

All endpoints MUST be user-scoped — users can only see and manage their own memory.

---

### REQ-9: Frontend — MemoryConfig UI

**REQ-9.1** The KB settings page SHALL include a "Conversation Memory" section.

**REQ-9.2** The UI SHALL allow:
- Enabling/disabling memory
- Selecting summarization model (filtered to generation models)
- Selecting embedding model (filtered to dense embedding models)
- Setting retention days (slider or input, 1–365)
- Setting retrieval top-K (slider, 1–20)
- Setting min turns to summarize (input, 1–20)
- Editing system prompt (textarea with Jinja2 variable hints)

**REQ-9.3** The UI SHALL show a preview of available Jinja2 template variables.

**REQ-9.4** Validation errors from the API SHALL be surfaced inline on form fields.

---

### REQ-10: Frontend — User Memory Management UI

**REQ-10.1** A memory management page SHALL be accessible at `/console/memory`.

**REQ-10.2** The page SHALL list the authenticated user's memory chunks grouped by
knowledge base, showing: summary preview, KB name, turn count, created date, expiry date.

**REQ-10.3** The user SHALL be able to delete individual memory chunks or clear all
memory for a KB from this page.

**REQ-10.4** If memory is disabled for a KB, that KB SHALL NOT appear in the memory
management page.
