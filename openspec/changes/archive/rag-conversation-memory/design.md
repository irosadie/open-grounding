# Design: RAG Conversation Memory

## Context

The grounded query pipeline has session-scoped conversation history via `rag_conversations`
and `rag_conversation_messages`. This change adds a persistent memory layer that survives
across sessions, scoped per user per knowledge base.

Existing tables used:
- `rag_conversations` — session container
- `rag_conversation_messages` — individual turns
- `rag_answer_runs` — trace per answer

New tables needed:
- `rag_memory_configs` — per-KB memory configuration
- `rag_memory_chunks` — summarized memory units per user per KB

Qdrant collections:
- `rag` — existing, for document chunks
- `memory` — new, for memory chunk embeddings (per tenant namespace)

---

## Architecture

### Entity: MemoryConfig

Attached 1:1 to a KnowledgeBase. Controls whether memory is enabled for that KB and
how it behaves.

```python
@dataclass(frozen=True)
class MemoryConfig:
    id: str
    tenant_id: str
    knowledge_base_id: str
    enabled: bool                        # master opt-in switch
    summarization_model_profile_id: str  # FK → ModelProfile (generation model)
    embedding_profile_id: str            # FK → ModelProfile (embedding model)
    retention_days: int                  # default 90, min 1, max 365
    retrieval_top_k: int                 # default 5, max 20
    min_turns_to_summarize: int          # default 3, min 1
    system_prompt: str                   # Jinja2 for summarizer LLM
    created_at: datetime
    updated_at: datetime
```

### Entity: MemoryChunk

A summarized memory unit representing one conversation session.

```python
@dataclass(frozen=True)
class MemoryChunk:
    id: str
    tenant_id: str
    knowledge_base_id: str
    user_id: str
    conversation_id: str             # source conversation
    summary: str                     # LLM-generated summary
    qdrant_point_id: str             # vector store reference
    turn_count: int                  # number of turns summarized
    expires_at: datetime             # computed from retention_days at creation
    created_at: datetime
```

---

## Data Flow

### Write Path (Background — no query latency)

```
conversation ends (or session timeout)
  → worker job: SummarizeConversationJob
      → load conversation messages from DB
      → if turn_count < min_turns_to_summarize → skip
      → render Jinja2 system prompt with {{ conversation_messages }}, {{ knowledge_base_name }}
      → call summarization LLM → get summary text
      → embed summary via embedding_profile
      → upsert to Qdrant collection "memory" with payload:
          { tenant_id, knowledge_base_id, user_id, chunk_id, expires_at }
      → save MemoryChunk to DB
      → mark conversation as "summarized"
```

### Read Path (Query time — adds ~50-100ms)

```
incoming query (with conversation context)
  → check if KB has MemoryConfig and enabled=true
  → if yes:
      → embed current query via same embedding_profile
      → Qdrant search in "memory" collection
          → filter: tenant_id + knowledge_base_id + user_id
          → filter: expires_at > now()
          → top_k: retrieval_top_k
      → retrieve top-K memory chunks from DB by qdrant_point_ids
      → inject memories as system context block before generation:
          "Relevant memories from prior sessions:\n- {memory1}\n- {memory2}"
  → proceed with standard grounded query
```

### Pruning (Background — periodic)

```
scheduled job: PruneExpiredMemoryJob (daily)
  → query rag_memory_chunks WHERE expires_at < now()
  → delete from Qdrant by point_id
  → delete from DB
```

---

## Worker Jobs

Two new worker jobs added to existing worker infrastructure:

**1. `memory.summarize`**
- Triggered when: conversation is marked complete OR idle for >30min
- Input: `{ conversation_id, tenant_id, knowledge_base_id, user_id }`
- Output: MemoryChunk created, Qdrant point upserted

**2. `memory.prune`**
- Triggered: daily cron via Redis scheduled job
- Input: `{ tenant_id }` or global sweep
- Output: expired chunks deleted from Qdrant + DB

---

## Qdrant Collection: `memory`

Separate from `rag` collection. Naming: `memory` (single collection, filtered by tenant/kb/user payload).

Point payload schema:
```json
{
  "tenant_id": "uuid",
  "knowledge_base_id": "uuid",
  "user_id": "uuid",
  "chunk_id": "uuid",
  "expires_at": "iso8601"
}
```

Filters applied at query time: `tenant_id + knowledge_base_id + user_id + expires_at > now()`

---

## Query API Extension

`POST /rag/query` gains optional `memory` field:

```json
{
  "memory": {
    "enabled": true    // optional per-request override, default uses KB config
  }
}
```

Response trace includes memory metadata:
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

## API Endpoints

```
POST   /rag/knowledge-bases/{id}/memory-config        → create/replace MemoryConfig
GET    /rag/knowledge-bases/{id}/memory-config        → get config (404 if not set)
DELETE /rag/knowledge-bases/{id}/memory-config        → delete config + all memories for KB

GET    /rag/memory                                    → list user's memory chunks (paginated)
DELETE /rag/memory                                    → clear all user memory (all KBs)
DELETE /rag/memory/{chunk_id}                         → delete specific memory chunk
```

All endpoints tenant + user scoped.

---

## Decisions

### Background summarization over real-time

Summarizing during an active query adds 200-800ms latency (LLM call). Users should not
wait for memory writes. Background worker decouples write path from read path entirely.

### Dedicated Qdrant collection for memory

Mixing memory chunks with document chunks in `rag` collection pollutes document retrieval.
Memory retrieval needs different filter logic (user-scoped, TTL-filtered). Separate
collection keeps both concerns clean.

### TTL-based expiry over explicit delete

Users rarely proactively delete data. TTL ensures memory doesn't accumulate indefinitely,
satisfies reasonable privacy expectations, and reduces operational burden. Explicit delete
still available for users who want it.

### Per user per KB scoping

Cross-KB memory would require disambiguation logic ("which KB is this memory from?") and
risks domain leakage. Per-KB isolation is simpler, more predictable, and cleaner for
deletion semantics (delete KB → all memory for that KB gone).

### min_turns_to_summarize

Conversations with 1-2 turns rarely contain enough signal worth summarizing. This threshold
prevents noisy, low-value memory chunks from accumulating.

---

## Risks / Trade-offs

- [Summarization quality] — poor summaries degrade retrieval quality. Mitigated by
  configurable model selection + prompt template per KB.
- [Qdrant memory collection grows unbounded] — mitigated by TTL pruning job.
- [Privacy] — memory persists user conversation data. Mitigated by explicit opt-in,
  clear UI for viewing/deleting memory, and TTL.
- [Embedding drift] — if embedding model changes, old memory vectors become stale.
  Mitigated by storing `embedding_profile_id` on MemoryChunk; stale chunks can be
  re-embedded or pruned on model change.
- [Worker failure] — if summarization job fails, conversation is not summarized.
  Mitigated by retry logic in worker + dead letter queue.

## Open Questions

- Should memory chunks be visible to users in the retrieval UI, or only in a dedicated memory management page?
- Should there be a global tenant-level memory toggle in addition to per-KB toggle?
