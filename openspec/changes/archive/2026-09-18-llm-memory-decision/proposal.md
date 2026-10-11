## Why

Conversation memory is currently summarized by an LLM, but every non-empty summary is persisted. This can retain transient discussion or source-derived claims even when the conversation contains no durable user memory. The memory LLM should explicitly decide whether a conversation contains a safe, useful, long-term user fact or preference before any chunk is written.

## What Changes

- Extend the memory summarization contract so the LLM returns an explicit store decision alongside the candidate summary.
- Persist a memory chunk only when the LLM decision is positive and the summary is non-empty.
- Instruct the memory LLM to prefer durable user-stated facts, preferences, and context; ignore transient questions, assistant/source-only claims, secrets, and unsupported document facts.
- Keep the existing tenant opt-in, retention, embedding, Qdrant, worker, and memory retrieval behavior intact.
- Leave ordinary grounded RAG generation, evidence binding, citations, and answer guardrails unchanged.

## Capabilities

### New Capabilities

<!-- None. This change refines the existing conversation-memory capability. -->

### Modified Capabilities

- `rag-conversation-memory`: Require an LLM decision gate before persisting a long-term memory chunk and define which conversation content is eligible for storage.

## Impact

- Backend memory summarizer prompt and structured LLM response parsing.
- Memory worker persistence decision and related unit/integration tests.
- Existing memory configuration remains backward compatible; no RAG query request or grounded-answer contract changes.
