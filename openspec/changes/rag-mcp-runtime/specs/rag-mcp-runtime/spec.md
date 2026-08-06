# Spec: RAG MCP Runtime

## Overview

Server-side MCP runtime that connects to external MCP servers (stdio and remote HTTP/SSE),
discovers and caches their tools, and invokes tools with permission enforcement and full
audit. All configuration is tenant-scoped and exposed via management UI.

---

## Requirements

### REQ-1: McpServer Entity

**REQ-1.1** The system SHALL provide an `McpServer` entity with fields:
- `name` (string, 1–120)
- `transport` — one of `"stdio"`, `"http"`, `"sse"`
- For `stdio`: `command` (string) and `args` (array of strings)
- For `http`/`sse`: `url` (string, must be `https` unless `allow_insecure` true)
- `auth_type` — `"none"`, `"bearer"`, or `"header"`
- `timeout_seconds` (int, 1–120, default 30)
- `max_payload_bytes` (int, 64 KiB – 10 MiB, default 1 MiB)
- `enabled` (bool, default true)
- `status` (`"unknown"`, `"connected"`, `"error"`) — last known connection status
- `last_error` (string, nullable)

**REQ-1.2** Creating an `McpServer` with `transport="stdio"` SHALL require non-empty `command`.

**REQ-1.3** Creating an `McpServer` with `transport="http"` or `"sse"` SHALL require non-empty `url`.

**REQ-1.4** Registering, updating, or deleting an `McpServer` SHALL require tenant ADMIN role. Non-admin SHALL get `FORBIDDEN`.

**REQ-1.5** A deleted `McpServer` SHALL cascade-delete its cached `McpTool` rows and close any live connection.

---

### REQ-2: Credentials

**REQ-2.1** MCP server credentials SHALL be stored encrypted using the existing AES-256-GCM `crypto.py` mechanism.

**REQ-2.2** Credentials SHALL be stored in `rag_provider_credentials` with `provider="mcp"` and `key_name="<server_id>:<kind>"` where kind is `auth_token` or a named header.

**REQ-2.3** The API SHALL never return stored credential values — only a boolean `has_credential` flag.

**REQ-2.4** Updating credentials SHALL require the existing credential to be replaced; the API SHALL NOT return the old value.

---

### REQ-3: Tool Discovery and Registry

**REQ-3.1** The system SHALL provide a discovery operation that connects to a server and lists its tools.

**REQ-3.2** Discovered tools SHALL be upserted into `mcp_tools` keyed by `(tenant_id, server_id, name)`.

**REQ-3.3** Each `McpTool` SHALL store: `name`, `description`, `input_schema` (JSON Schema), and `allowed` (bool).

**REQ-3.4** Newly discovered tools SHALL default to `allowed=false` for safety. A dedicated UI action or API SHALL flip `allowed` to true per tool.

**REQ-3.5** Tools removed by the server on a later discovery SHALL be marked stale (soft) rather than hard-deleted.

**REQ-3.6** Listing tools SHALL read from `mcp_tools` (no connection round-trip).

---

### REQ-4: Connection Management

**REQ-4.1** The runtime SHALL maintain live connections keyed by `(server_id, transport, target)`.

**REQ-4.2** stdio connections SHALL be created via `asyncio.create_subprocess_exec` and closed via the MCP SDK context manager + process termination on close.

**REQ-4.3** HTTP/SSE connections SHALL use the MCP streamable HTTP client with bearer/header auth.

**REQ-4.4** All connection and invocation operations SHALL be bounded by `timeout_seconds` via `asyncio.timeout`.

**REQ-4.5** Connection failures SHALL set `server.status="error"` and record `last_error` (sanitized, no credentials).

---

### REQ-5: Tool Invocation

**REQ-5.1** `invoke_tool` SHALL:
1. Verify server is `enabled`
2. Verify tool exists and `allowed=true` for the tenant
3. Connect (or reuse cached connection)
4. Call the tool with typed `arguments`
5. Write an `McpInvocation` audit row
6. Return the tool result

**REQ-5.2** A denied invocation SHALL record `McpInvocation(status="denied")` and return error `TOOL_DENIED` (403).

**REQ-5.3** A timed-out invocation SHALL record `status="timeout"` and return error `TOOL_TIMEOUT` (504).

**REQ-5.4** A failed invocation SHALL record `status="error"` and return error `TOOL_ERROR` (502) with sanitized message.

**REQ-5.5** Arguments passed to a tool SHALL be validated against `input_schema` before invocation. Invalid args SHALL return `INVALID_TOOL_ARGS` (422).

**REQ-5.6** The result text SHALL be truncated to `max_payload_bytes` before storing in audit.

**REQ-5.7** The raw result SHALL be returned to the caller (bounded to `max_payload_bytes`).

---

### REQ-6: Audit Log

**REQ-6.1** Every invocation SHALL append an `McpInvocation` row with: server, tool, user, status, `args_hash`, truncated result, duration, timestamp.

**REQ-6.2** `args_hash` SHALL be a SHA-256 of canonicalized arguments — never raw secret values.

**REQ-6.3** Audit rows SHALL be queryable via API filtered by `(tenant_id, server_id, status, user_id, time range)`.

**REQ-6.4** Audit rows older than a configurable retention period (default 30 days) SHALL be prunable.

---

### REQ-7: MCP Runtime API

**REQ-7.1** `POST /rag/mcp/servers` — register a server (ADMIN only)

**REQ-7.2** `GET /rag/mcp/servers` — list servers (masked credentials)

**REQ-7.3** `GET /rag/mcp/servers/{id}` — get one server

**REQ-7.4** `PUT /rag/mcp/servers/{id}` — update config (ADMIN only)

**REQ-7.5** `DELETE /rag/mcp/servers/{id}` — delete + cascade (ADMIN only)

**REQ-7.6** `POST /rag/mcp/servers/{id}/test` — test connection, return latency + tool count

**REQ-7.7** `POST /rag/mcp/servers/{id}/discover` — refresh tool registry (ADMIN only)

**REQ-7.8** `GET /rag/mcp/servers/{id}/tools` — list cached tools for a server

**REQ-7.9** `PUT /rag/mcp/tools/{tool_id}` — update `allowed` permission

**REQ-7.10** `POST /rag/mcp/tools/{tool_id}/invoke` — invoke a tool

**REQ-7.11** `GET /rag/mcp/invocations` — query audit log (ADMIN or owner)

All endpoints MUST be tenant-scoped.

---

### REQ-8: Frontend — MCP Servers UI

**REQ-8.1** A page `/console/settings/mcp` SHALL list MCP servers with status badges.

**REQ-8.2** The page SHALL allow:
- Create server (transport type selector: stdio/HTTP/SSE, conditional fields)
- Edit server config
- Delete server
- Test connection (shows latency + tool count or sanitized error)
- Discover tools button

**REQ-8.3** Credential fields SHALL be password-type and never prefilled with the stored value.

**REQ-8.4** Server status SHALL be shown (unknown/connected/error) with `last_error` tooltip.

---

### REQ-9: Frontend — Tool Browser

**REQ-9.1** A per-server tool list SHALL show: name, description, `allowed` toggle, schema summary.

**REQ-9.2** The UI SHALL allow toggling `allowed` per tool.

**REQ-9.3** The UI SHALL provide a "Try it" invoke form that renders arguments from `input_schema` (JSON editor with validation) and shows the result.

---

### REQ-10: Frontend — Invocation Audit View

**REQ-10.1** A view `/console/settings/mcp/audit` SHALL list recent invocations (server, tool, status, user, duration, time) with filters.

**REQ-10.2** A detail view SHALL show `args_hash` and truncated result; raw args SHALL NOT be shown (only hash).

---

### REQ-11: Security

**REQ-11.1** stdio server registration SHALL require ADMIN and SHALL be recorded in audit.

**REQ-11.2** `allow_insecure` (http://) SHALL default false and SHALL be an explicit opt-in per server.

**REQ-11.3** The runtime SHALL NOT log raw arguments, credentials, or result bodies containing sensitive content beyond `max_payload_bytes`.
