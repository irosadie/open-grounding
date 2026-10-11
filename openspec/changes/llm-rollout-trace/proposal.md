## Why

The existing `RAG_DEV_TRACE` output is useful for stage summaries, but it does not preserve the exact LLM request or the complete agent loop. Developers cannot reliably inspect the system/developer/user messages, tool definitions, tool arguments/results, follow-up LLM calls, retries, and failures that caused a response. A Codex-style persistent rollout trace is needed so a single request can be inspected and tuned after the fact.

## What Changes

- Add an opt-in persistent rollout recorder controlled by `RAG_LLM_TRACE_ENABLED=true|false`, defaulting to `false`.
- Write one ordered JSONL rollout file per trace/session under a configurable `RAG_LLM_TRACE_DIR`.
- Record the complete execution timeline: session metadata, user input, assembled context, exact outbound LLM payloads, provider responses, stream chunks, tool calls, tool results, retries, policy decisions, errors, compaction, and turn completion.
- Capture all application LLM call paths, including generation, query planning, decomposition, memory summarization, and other direct provider calls found during implementation.
- Capture MCP/tool execution at the execution boundary, including arguments, bounded result/error payload, status, and duration.
- Keep the existing `RAG_DEV_TRACE` stdout modes unchanged; the persistent rollout trace is a separate opt-in diagnostic channel.
- Redact credentials and authorization material while retaining prompt, tool, and model payload content when the feature is explicitly enabled.
- Add tests, local inspection guidance, and a gitignore rule for the default trace directory.
- Do not change public API response shapes, business decisions, tenant authorization, or database schema.

## Capabilities

### New Capabilities

- `llm-rollout-tracing`: Opt-in, ordered, persistent JSONL recording of the complete LLM/tool execution timeline for debugging and prompt tuning.

### Modified Capabilities

<!-- Existing business capabilities are not behaviorally changed; the new capability defines the diagnostic side channel. -->

## Impact

- **Configuration:** `apps/api/app/core/settings.py` gains boolean enablement and trace directory settings mapped to environment variables.
- **Core runtime:** add a trace context/recorder with per-trace sequence numbers, JSON serialization, redaction, and best-effort file writes.
- **LLM boundaries:** instrument generation, planner, decomposer, memory, calibration, and any remaining provider call sites so no outbound chat/generation request bypasses tracing when enabled.
- **Tool boundaries:** instrument `TaskExecutor` and `McpRuntimeService` for requested, started, completed, denied, timeout, and failed tool events.
- **Entry points:** start and finish trace sessions for HTTP query requests and background worker operations.
- **Tests/docs:** add unit/integration coverage and document `RAG_LLM_TRACE_ENABLED=true` usage and sensitive-data handling.
- **No migration or OpenAPI change:** rollout files are local development artifacts, not persisted application data.
