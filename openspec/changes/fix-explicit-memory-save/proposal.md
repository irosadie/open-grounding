## Why

An explicit request such as “simpan informasi nama saya” is currently ignored by the
memory worker when the conversation contains only the user and assistant turn. The
worker is correctly enqueued, but the configured minimum of three turns causes it to
exit before the summarization LLM is called, so an explicitly requested durable fact is
never saved.

## What Changes

- Detect an explicit user request to remember, save, or store personal context in the
  memory summarizer.
- Allow that explicitly requested context to be summarized immediately, while keeping
  the configured minimum-turn threshold for ordinary conversations.
- Make the memory decision prompt tell the summarization LLM that an explicit save
  request is a strong eligibility signal, while preserving secret and policy filters.
- Add regression coverage for Indonesian and English save requests and for ordinary
  short conversations that must still be skipped.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rag-conversation-memory`: an opted-in conversation with an explicit user request to
  remember durable personal context is eligible before the normal minimum-turn count.

## Impact

- `apps/api/app/application/memory_summarizer.py` and its backend tests.
- Existing memory configuration, database schema, queue payload, API response, and
  Qdrant contract remain unchanged.
