## Purpose

Provides a Codex-like, opt-in rollout record so developers can inspect the exact LLM and tool execution sequence that produced an application response.

## ADDED Requirements

### Requirement: Rollout tracing is disabled by default and controlled by environment
The system SHALL expose a boolean environment setting `RAG_LLM_TRACE_ENABLED` that defaults to `false`. When the setting is false or absent, the system MUST NOT create rollout directories, write rollout files, serialize trace payloads, or alter the application response flow.

#### Scenario: Trace is disabled by default
- **WHEN** `RAG_LLM_TRACE_ENABLED` is absent or set to `false`
- **THEN** no rollout file is created and the request behaves exactly as it did without rollout tracing

#### Scenario: Trace is enabled explicitly
- **WHEN** `RAG_LLM_TRACE_ENABLED=true`
- **THEN** eligible HTTP and worker execution flows create a rollout context and persist trace events

### Requirement: Rollout events are persisted as an ordered JSONL timeline
When tracing is enabled, the system SHALL persist one JSON object per line in a per-trace rollout file below the configured trace directory. Every event MUST contain a schema version, trace identity, UTC timestamp, monotonically increasing sequence number, event name, and event payload. Concurrent events belonging to one trace MUST remain parseable and have unique ordered sequence numbers.

#### Scenario: A trace contains an ordered timeline
- **WHEN** a traced request performs an LLM call followed by a tool call and a follow-up LLM call
- **THEN** its rollout file contains parseable JSONL events whose sequence numbers describe the execution order

#### Scenario: Separate traces do not share files
- **WHEN** two requests execute concurrently with different trace identities
- **THEN** each request's events are written to its own rollout file and no event is assigned to the other trace

### Requirement: LLM boundary payloads are recorded exactly enough for debugging
For every outbound chat, generation, planning, decomposition, summarization, or equivalent LLM request made while tracing is enabled, the system SHALL record the provider, model, request attempt, endpoint or operation, model parameters, complete message/input structure, tool definitions supplied to the provider, and the corresponding provider response or error. The recorded request MUST represent the payload immediately before transport serialization.

#### Scenario: Prompt assembly can be inspected
- **WHEN** a query sends system instructions, conversation history, retrieved context, and a user message to an LLM
- **THEN** the rollout contains those ordered message/input components and their source metadata without replacing them with a preview

#### Scenario: A provider call fails
- **WHEN** an LLM request times out, returns an error, or is retried
- **THEN** the rollout contains the failed attempt, sanitized error details, retry number, and the final outcome

### Requirement: Tool and agent-loop events are recorded
When tracing is enabled, the system SHALL record tool availability supplied to the model, every tool call request, tool name and arguments, authorization/validation decisions, execution start and completion, result or error payload, timeout status, duration, and any follow-up LLM request that consumes the result. Tool tracing MUST not bypass existing tenant permission, schema validation, timeout, or audit rules.

#### Scenario: A permitted MCP tool succeeds
- **WHEN** the planner selects an allowed MCP tool and the tool returns a result
- **THEN** the rollout contains the tool request, execution metadata, result, status, duration, and the next LLM request context

#### Scenario: A tool is denied or times out
- **WHEN** a tool fails authorization, input validation, or execution timeout
- **THEN** the rollout records the decision and failure status, while the existing safe application behavior remains unchanged

### Requirement: Stream, compaction, and lifecycle events are observable
When tracing is enabled, the system SHALL record streamed LLM deltas when streaming is used, context assembly and compaction boundaries, turn start/end, final response or safe abstention, and uncaught request errors. Event recording MUST preserve the event order needed to reconstruct the agent loop.

#### Scenario: A streamed response completes
- **WHEN** the provider emits streamed response chunks and the application releases a final answer
- **THEN** the rollout contains ordered stream events and a completion event whose final content can be correlated to the released answer

#### Scenario: Context is compacted
- **WHEN** the application summarizes or trims prior context before another LLM call
- **THEN** the rollout records the compaction boundary, reason, and the relationship between the prior and next request

### Requirement: Trace output is safe and non-authoritative
The system SHALL remove API keys, authorization headers, cookies, credentials, and equivalent secret material from trace metadata and transport headers. Trace write failures MUST be reported through normal diagnostics without failing, retrying, or changing the user request. Rollout files SHALL be treated as sensitive local artifacts and MUST NOT be exposed through public API responses.

#### Scenario: A request includes credentials
- **WHEN** a traced provider request contains an API key or authorization header
- **THEN** the rollout omits or masks the credential while preserving the non-secret request body needed for debugging

#### Scenario: Trace storage is unavailable
- **WHEN** the trace directory cannot be created or a rollout append fails
- **THEN** the application continues its normal request flow and emits a diagnostic about the trace failure

### Requirement: Existing diagnostic modes remain independent
The persistent rollout setting SHALL be independent from `RAG_DEV_TRACE`. Enabling or disabling persistent rollouts MUST NOT change existing summary/verbose stdout behavior, and existing `RAG_DEV_TRACE=off|summary|verbose` semantics MUST remain compatible.

#### Scenario: Persistent trace is enabled without console trace
- **WHEN** `RAG_LLM_TRACE_ENABLED=true` and `RAG_DEV_TRACE=off`
- **THEN** full rollout files are written while no existing `[DEV]` stdout trace lines are emitted
