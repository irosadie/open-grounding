# rag-tool-execution-sandbox Specification (delta)

## Purpose
Define the execution sandbox that isolates every tool call from the FastAPI web
process, enforces per-call timeout and output size caps, and ensures tool failures
cannot crash or block the query pipeline.

## ADDED Requirements

### Requirement: Tool calls execute outside the FastAPI request process
The system SHALL dispatch tool calls as BullMQ worker tasks. The FastAPI web process
MUST NOT execute tool adapter code directly. The dispatcher enqueues a job and awaits
the result within a configured deadline.

#### Scenario: Tool call is dispatched during a query
- **WHEN** the query planner routes to the `tool` path and a permitted tool is selected
- **THEN** the dispatcher enqueues a BullMQ job with tool slug, input, tenant ID,
  trace ID, timeout_ms, and max_output_bytes, then awaits the result

### Requirement: Each tool call is bounded by timeout and output size
The system SHALL enforce a per-call `timeout_ms` via `asyncio.wait_for` inside the
worker and a `max_output_bytes` cap on the raw output before it is returned. A tool
that exceeds either limit MUST be terminated and its result treated as a TIMEOUT or
ERROR status in the audit log.

#### Scenario: Tool adapter exceeds the configured timeout
- **WHEN** a tool adapter does not return within `timeout_ms`
- **THEN** the worker cancels the adapter coroutine, writes a TIMEOUT audit entry,
  and returns a terminal error result to the dispatcher

#### Scenario: Tool output exceeds the output size cap
- **WHEN** the raw output of a tool adapter exceeds `max_output_bytes`
- **THEN** the worker truncates or discards the output, writes an ERROR audit entry
  with a size-exceeded reason, and returns a terminal error result

### Requirement: Tool adapter errors are isolated and do not crash the worker
The system SHALL catch all exceptions from tool adapters within the worker task.
An unhandled exception in a tool adapter MUST NOT terminate the worker process. The
error MUST be recorded in the audit log and the job marked as failed with a retryable
or terminal status based on error type.

#### Scenario: Tool adapter raises an unhandled exception
- **WHEN** a tool adapter raises any exception during execution
- **THEN** the worker catches it, writes an ERROR audit entry, marks the BullMQ job
  as failed, and continues processing subsequent jobs

### Requirement: Tool adapters do not receive tenant credentials
The system SHALL load provider credentials for tool adapters from runtime environment
configuration only. Tenant context passed to the worker MUST contain only tenant ID,
trace ID, and tool input. No secret, token, or credential value MAY appear in the
BullMQ job payload.

#### Scenario: Worker processes a tool job
- **WHEN** the ToolExecutionProcessor loads and runs a tool adapter
- **THEN** the job payload contains no secret values; the adapter reads credentials
  from its own environment configuration
