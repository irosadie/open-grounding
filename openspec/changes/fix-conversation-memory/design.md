## Context

The API already returns `conversationId` in the first SSE event, and the query service
already persists both user and assistant messages. The retrieval hook currently parses the
event only for its trace ID and the page does not pass a conversation ID on later submits.
The worker module already exposes `enqueue_memory_summarize`, but the application query
flow never calls it. See the proposal and delta specs for the user-visible behavior.

## Goals / Non-Goals

**Goals:**

- Keep a retrieval page session on one server-owned conversation ID.
- Schedule memory summarization only for knowledge bases with enabled memory.
- Keep scheduling asynchronous and best-effort so query latency and availability are not
  coupled to Redis or the worker.
- Permit more than one scheduling attempt before the minimum turn threshold is reached,
  while relying on the existing `is_conversation_summarized` guard for idempotent writes.

**Non-Goals:**

- No database schema or public request/response contract changes.
- No change to summarization prompts, model selection, retention, embedding, or Qdrant
  retrieval behavior.
- No automatic backfill of the already-isolated historical conversations in the local
  database.

## Decisions

### Schedule from the query service after completion

The query service will call a small internal scheduling helper after the admitted query
returns. This guarantees the assistant message has already been persisted and covers
grounded, answered, abstained, and refused terminal paths without duplicating calls across
the many finish helpers. The helper will inspect per-KB memory configuration before
enqueueing. An explicit request-level memory disable skips scheduling.

Alternative considered: enqueue from each `_finish_*` helper. That duplicates orchestration
across several terminal paths and makes it easier for one path to drift.

### Use distinct job identities for repeated turns

The existing enqueue wrapper will accept an optional job ID. The query service will provide
a unique identity per conversation, knowledge base, and completion attempt. This avoids a
completed low-turn job permanently blocking a later attempt with the existing fixed
`mem:<conversation_id>` identity. The summarizer's existing conversation-summarized check
remains the final idempotency guard.

Alternative considered: keep one deterministic job ID and enqueue only after counting
messages. That would add another persistence query and still requires a reliable threshold
transition; distinct attempts keep the worker contract simple.

### Store continuity inside the existing stream hook

The hook will own the conversation ID because it owns the request payload and SSE parsing.
It will set the ID from `response.started`, use it as the default request value on later
calls, expose it in the hook result, and clear it in `reset`. The page requires no new UI
control and keeps the existing stream API backward compatible for callers that pass an
explicit ID.

### Use provider-compatible defaults for summarization

The memory summarizer will leave the optional OpenAI temperature parameter unset. Some
configured reasoning models reject custom temperature values and only accept their
provider default. This does not change model selection or the summarization prompt; it
allows the existing configured model to complete the request.

### Provision the memory collection on first write

The memory summarizer will check for the fixed `memory` Qdrant collection immediately
before the first point upsert and create it with the current embedding vector length and
cosine distance when absent. A concurrent creator is treated as success. This keeps the
existing single-collection retrieval contract while making a fresh local Qdrant instance
usable without a manual bootstrap step.

## Risks / Trade-offs

- [Extra skipped jobs] → A short conversation can enqueue a job before reaching the
  minimum turn count; distinct jobs are intentional, and the worker exits quickly when the
  summarizer's threshold check fails.
- [Redis unavailable] → Scheduling is wrapped in a warning-level best-effort path; the
  query result remains available and a later query can retry scheduling.
- [Existing local conversations] → Conversations already split into two-message sessions
  will not be merged automatically; new page sessions use continuity and will produce
  eligible multi-turn conversations.

## Migration Plan

No migration is required. Restart the API/worker and web dev processes after deployment.
Existing memory configuration and tables remain compatible. Rollback consists of reverting
the query scheduling and hook state changes; persisted messages and any created memory
chunks remain valid.
