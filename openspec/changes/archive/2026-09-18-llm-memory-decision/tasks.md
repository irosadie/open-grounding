## 1. Memory Decision Contract

- [x] 1.1 Add a strict internal memory-decision model/parser for `should_store`, bounded `summary`, and diagnostic `reason`; verify malformed JSON, non-boolean decisions, missing summaries, and oversized summaries fail closed in unit tests
- [x] 1.2 Update the default memory prompt and runtime prompt wrapper to require the decision envelope, prioritize durable user-stated facts/preferences, and reject transient, assistant-only, source-only, secret, or unsupported content; verify rendered prompts preserve the existing conversation variables

## 2. Summarizer Integration

- [x] 2.1 Wire the structured decision through OpenAI and Ollama memory summarization without changing the RAG generation adapter or query answer path; verify a positive decision proceeds to embedding, Qdrant upsert, and database persistence
- [x] 2.2 Gate persistence on a positive decision with a non-empty summary and keep negative decisions eligible for later conversation evaluation; verify rejected decisions do not call embedding, Qdrant, or memory-chunk persistence
- [x] 2.3 Preserve tenant opt-in, retention, conversation idempotency, and worker retry behavior without a database migration; verify existing disabled-memory, already-summarized, and below-minimum-turn tests still pass

## 3. Regression Verification

- [x] 3.1 Add scenarios for a durable user-stated fact being accepted, a retrieved-document-only fact being rejected, and a user fact conflicting with retrieved evidence remaining eligible for memory; verify the grounded answer path remains unchanged
- [x] 3.2 Run focused memory and RAG query tests plus API lint/type checks, and validate the OpenSpec change with `openspec validate llm-memory-decision --type change --strict`
