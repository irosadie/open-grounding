## Context

The repository already has `DevTracer` in `apps/api/app/core/dev_trace.py`. It emits summary or NDJSON stdout events and intentionally truncates prompts, so it is not suitable as a complete persisted rollout. LLM calls currently exist in several paths: grounded generation, query decomposition, query planning, memory summarization, calibration, and provider adapters. MCP execution is split between task orchestration and `McpRuntimeService`.

The existing query flow already creates a query trace identity, while worker jobs carry document/version and job identities. The design should reuse those identities at entry points and avoid putting diagnostic state into domain entities, public DTOs, or database tables.

## Goals / Non-Goals

**Goals:**

- Make the exact outbound LLM payload and complete tool loop inspectable after a request.
- Provide a simple `true|false` environment switch with safe default-off behavior.
- Preserve event order and correlate nested planner, tool, and follow-up LLM activity.
- Cover every current outbound chat/generation/summarization call path through a deliberate call-site inventory.
- Keep trace failures best-effort and isolated from application behavior.

**Non-Goals:**

- No user-facing trace viewer or public trace API in this change.
- No replacement for database-backed answer traces, MCP audit records, or `RAG_DEV_TRACE` stdout diagnostics.
- No recording of embedding vectors or arbitrary infrastructure logs unless they are part of an LLM/tool event.
- No production-grade centralized observability, OpenTelemetry exporter, or automatic deletion service.
- No execution of recorded traces or automatic prompt mutation; replay tooling can be added later using the stable format.

## Decisions

### D1: Add a separate boolean flag and preserve `RAG_DEV_TRACE`

Use `rag_llm_trace_enabled: bool = False`, mapped by pydantic-settings to `RAG_LLM_TRACE_ENABLED`, plus `rag_llm_trace_dir` mapped to `RAG_LLM_TRACE_DIR`. The existing `RAG_DEV_TRACE` remains the lightweight console channel.

**Why:** A boolean is easy to turn on for a debugging session, and separating the channels avoids breaking the existing `off|summary|verbose` contract or making console verbosity imply full prompt/data persistence.

**Alternative rejected:** Reusing `RAG_DEV_TRACE=verbose` would change its current meaning, still has no durable per-session file, and would make accidental sensitive-data persistence more likely.

### D2: Use a context-local rollout recorder

Create a recorder/context module under `apps/api/app/core/llm_rollout_trace.py`. A request or worker entry point starts a trace context with an existing or generated trace ID. A `ContextVar` exposes the active recorder to nested provider and tool boundaries without adding a trace parameter to every domain protocol.

The recorder exposes a no-op implementation when disabled and a best-effort enabled implementation with `record(event, payload, ...)`, `start_turn`, and `close` operations. Each enabled trace writes to `{RAG_LLM_TRACE_DIR}/{UTC date}/rollout-{trace_id}.jsonl`.

**Why:** Context-local state follows async task boundaries, supports concurrent task execution, and avoids leaking trace concerns into business entities and public contracts.

**Alternative rejected:** Passing a recorder through every service and repository signature would create broad contract churn and make it easy to miss a nested provider or tool path.

### D3: Stable event envelope with explicit event catalog

Each line uses this shape:

```json
{
  "schema_version": 1,
  "seq": 12,
  "ts": "2026-09-18T10:00:00.000Z",
  "trace_id": "...",
  "turn_id": "...",
  "event": "llm_request",
  "payload": {}
}
```

The first implementation supports `session_meta`, `turn_started`, `user_message`, `context_assembled`, `llm_request`, `llm_stream_chunk`, `llm_response`, `tool_catalog`, `tool_call_requested`, `tool_execution_started`, `tool_result`, `tool_error`, `policy_decision`, `compaction`, `turn_completed`, and `turn_failed`.

**Why:** A stable envelope makes files grepable and replayable while allowing event payloads to evolve under `schema_version`.

### D4: Record at transport and execution boundaries

Instrument immediately before and after each provider transport call. For OpenAI SDK calls, record the message/input body, tools, model parameters, response content/tool calls, usage, finish reason, and provider request ID without credentials. For Ollama/HTTP calls, record the JSON body and sanitized response/error. Instrument `McpRuntimeService.invoke_tool` and `TaskExecutor` around validation, permission, execution, timeout, and result handling.

Add a repository-wide inventory test/search for direct provider calls so new call sites do not silently bypass the recorder. Existing `DevTracer` prompt-tail events may remain for human console output; full rollouts use the exact boundary payload.

**Why:** Recording only in high-level services would miss retries, raw provider responses, hidden helper calls, and tool errors. Recording only in the HTTP route would miss worker and nested task activity.

### D5: Redact secrets, retain debug content when explicitly enabled

Apply recursive key-based redaction to headers, credentials, cookies, URLs with credential query parameters, and known secret fields. Prompt/message content, tool arguments, tool results, and model responses remain intact when full tracing is enabled because they are the subject of debugging. The recorder never writes access tokens or provider credentials.

**Why:** The feature is opt-in and intended for prompt/tool debugging, but credentials must never be copied into local traces.

### D6: Best-effort local persistence

Serialize one complete event and append it under a per-trace lock. Create directories lazily. Trace write errors go to the normal logger and do not propagate into the request. Add the default `.runtime/llm-traces/` path to `.gitignore`.

**Why:** Debugging must not change product behavior, and a local JSONL file is inspectable with standard tools without adding a runtime database or dependency.

## Risks / Trade-offs

- **[Risk] Full prompts, tool data, and responses may contain sensitive information** → Default the flag to false, redact credentials unconditionally, document local-file sensitivity, and keep traces out of Git.
- **[Risk] Large tool results or streamed output grow files quickly** → Reuse existing application payload bounds, use one file per trace, expose the directory setting, and document manual cleanup; do not silently truncate the first implementation's debugging payload.
- **[Risk] File writes add latency when enabled** → Limit writes to the explicit diagnostic mode, serialize one line at a time, and keep failures non-fatal. Disabled mode performs no payload serialization or I/O.
- **[Risk] Concurrent async tasks could reorder events** → Assign sequence numbers and append under the recorder's per-trace lock; include `parent_event_id`/`turn_id` where nested operations need stronger correlation.
- **[Risk] A new provider call can bypass tracing** → Maintain an explicit call-site inventory and add tests around all current provider adapters and direct helper calls.
- **[Risk] Existing database answer traces and rollout files diverge** → Treat rollout JSONL as a diagnostic mirror only; do not use it as authoritative product state.

## Migration Plan

1. Deploy code with `RAG_LLM_TRACE_ENABLED` unset/false; existing behavior is unchanged.
2. Add `.runtime/llm-traces/` to `.gitignore` and document local usage.
3. In development, set `RAG_LLM_TRACE_ENABLED=true` and optionally `RAG_LLM_TRACE_DIR=/absolute/path` for one debugging session.
4. Inspect rollout files and turn the flag back off after tuning.
5. Rollback requires only unsetting the flag or setting it to `false`; no database or API migration is needed.

## Open Questions

None. The flag, storage format, redaction boundary, and event coverage are intentionally fixed for this change so implementation can proceed without another product decision.
