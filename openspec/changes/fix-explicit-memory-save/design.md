## Context

The query service already enqueues `memory.summarize` after the assistant turn is
persisted. The worker loads the conversation and currently returns before the LLM call
when `len(messages) < min_turns_to_summarize`. The fix belongs in the summarizer because
it owns eligibility and can inspect only persisted USER messages without changing the
queue or HTTP contract.

## Decisions

### Detect explicit intent from USER messages only

Add a small normalized-text predicate in the memory summarizer. It recognizes save/
remember wording in Indonesian and English and requires a user-message source. This is
not a general semantic classifier; the LLM remains responsible for deciding whether the
requested content is durable and safe to retain.

### Preserve the configured threshold for normal conversations

Compute `explicit_memory_request` after loading messages. Continue to return early for
short conversations only when that flag is false. This keeps existing tenant tuning and
avoids increasing memory volume for ordinary queries.

### Make the LLM contract explicit

Append a contract instruction that an explicit request is a strong signal to store the
user-stated durable fact, but does not override secret, unsupported, source-only, or
transient-content exclusions. Require the summary to contain the concrete fact or
preference rather than generic consent or policy wording. For high-confidence name and
preference phrases, normalize the concrete fact locally after the LLM has positively
accepted the request. If the model returns only a generic consent rejection, the same
high-confidence normalization is allowed; safety, source-only, unsupported, and
transient rejection reasons still block the fallback. Secret markers never enter this
fallback. Include focused tests for the rendered prompt and normalization.

## Files

- `apps/api/app/application/memory_summarizer.py`
- `apps/api/tests/test_memory_summarizer.py`

No migration, schema, OpenAPI, frontend, or queue changes are required.
