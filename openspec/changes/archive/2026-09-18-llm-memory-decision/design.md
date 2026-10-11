## Context

The current memory worker loads a completed conversation, renders the configured memory prompt, calls the configured summarization model, and persists every non-empty response. The decision to retain content is therefore implicit in whether the model returned text. RAG answer generation is a separate path with its own evidence, citation, validation, and safety rules; this change must not couple the two paths.

## Goals / Non-Goals

**Goals:**

- Make memory eligibility an explicit decision made by the configured memory LLM.
- Preserve only concise, durable, user-relevant context that the conversation supports.
- Fail closed when the model returns an invalid or ambiguous decision.
- Preserve the existing tenant opt-in, retention, embedding, queue, and retrieval contracts.

**Non-Goals:**

- Changing grounded RAG answer generation, evidence thresholds, citations, or guardrails.
- Adding a manual memory command or a new user-facing memory trigger.
- Adding a database column or migration for the transient decision.
- Persisting model reasoning or decision explanations as user memory.

## Decisions

### 1. Use a structured decision envelope

The memory model will be required to return JSON with a small contract:

```json
{
  "should_store": true,
  "summary": "The user prefers concise answers.",
  "reason": "Durable user preference"
}
```

`should_store` is the only persistence gate. `summary` is required and bounded when the decision is positive. `reason` is diagnostic only and is not persisted or shown as memory content. This keeps the existing `summary` database field and avoids a migration.

The configured memory prompt remains customizable, but the runtime will append the decision policy and output contract so older prompts cannot silently restore unconditional persistence.

### 2. Fail closed on malformed or unsafe output

The parser will accept only a valid decision envelope. A malformed response, a non-boolean decision, a positive decision without a non-empty summary, or a summary that exceeds the existing bounded memory limits will be treated as a negative decision and logged. It will not create a Qdrant point or database chunk.

### 3. Separate user-stated context from retrieved evidence

The decision prompt will identify message speakers and instruct the model to use user messages as the authority for personal facts and preferences. Assistant responses that merely repeat retrieved documents are not sufficient evidence for user memory. Durable user claims may be retained even when they conflict with a knowledge-base document; that conflict affects the grounded answer path, not the memory write decision.

### 4. Keep the existing scheduling boundary

`RagQueryService` will continue to enqueue memory summarization after a completed query when the knowledge base has opted in. The worker and summarizer remain asynchronous and best-effort. The only new gate is inside the summarizer, immediately before embedding, Qdrant upsert, and database persistence.

When the decision is negative, the conversation remains eligible for a later evaluation as additional turns arrive. A positive decision continues to use the existing summarized-conversation idempotency check.

### 5. Test the memory path independently

Tests will cover positive decisions, negative decisions, source-only content, malformed output, empty summaries, and the existing persistence path. Existing RAG query tests remain the regression boundary proving that grounded answers and their guardrails are unchanged.

## Risks / Trade-offs

- [Risk] A model may incorrectly classify a transient statement as durable memory. → Mitigation: explicit policy in the prompt, speaker-aware examples, bounded summaries, and unit tests for transient/source-only conversations.
- [Risk] A provider may ignore the JSON contract. → Mitigation: strict parsing and fail-closed behavior; no memory is safer than an unreviewed write.
- [Risk] Negative decisions can cause repeated background evaluations while a conversation continues. → Mitigation: keep the existing minimum-turn threshold and evaluate the full conversation only when the worker is scheduled; a later positive decision still gets one persisted chunk.
- [Risk] Existing custom memory prompts may not mention the new envelope. → Mitigation: append the runtime contract to every configured prompt and treat legacy free-form output as non-storable.
