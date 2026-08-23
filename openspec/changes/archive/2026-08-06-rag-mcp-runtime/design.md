# Design: RAG MCP Runtime

## Context

The platform runs a FastAPI backend (`apps/api`) and a Python worker (`apps/worker`).
MCP runtime lives in the API process for now (single-deployment mode). Worker may
consume the same runtime later for background tool calls.

The existing `rag_provider_credentials` table already stores provider secrets encrypted
via `crypto.py` (AES-256-GCM). MCP server credentials reuse that mechanism.

## Architecture

### New Entities

```python
@dataclass(frozen=True)
class McpServer:
    id: str
    tenant_id: str
    name: str                    # display name
    transport: str               # "stdio" | "http" | "sse"
    command: str | None          # stdio: executable path
    args: list[str]              # stdio: argv
    url: str | None              # http/sse: endpoint URL
    auth_type: str | None        # "none" | "bearer" | "header"
    credential_ref: str | None   # key name in provider_credentials (encrypted)
    headers_json: dict           # extra static headers
    timeout_seconds: int         # default 30
    max_payload_bytes: int       # default 1 MiB
    enabled: bool
    status: str                  # "unknown" | "connected" | "error"
    last_error: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class McpTool:
    id: str
    tenant_id: str
    server_id: str
    name: str                    # tool name as exposed by server
    description: str
    input_schema: dict           # JSON Schema for tool arguments
    allowed: bool                # permission gate for this tenant
    last_discovered_at: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class McpInvocation:
    id: str
    tenant_id: str
    server_id: str
    tool_id: str
    user_id: str                 # caller
    args_json: dict
    args_hash: str               # sha256 of canonical args (for audit, not raw secrets)
    status: str                  # "success" | "error" | "timeout" | "denied"
    result_text: str | None      # truncated result/error message
    duration_ms: int
    created_at: datetime
```

### Tables

- `mcp_servers` — server config + transport + status
- `mcp_tools` — discovered tools (unique per `(tenant_id, server_id, name)`)
- `mcp_invocations` — audit log

### MCP Client Layer

Two client adapters behind one interface:

```python
class McpClientAdapter(Protocol):
    async def connect(self) -> None: ...
    async def list_tools(self) -> list[McpToolDescriptor]: ...
    async def call_tool(self, name: str, arguments: dict) -> McpCallResult: ...
    async def close(self) -> None: ...
```

**stdio adapter**: spawns `command args...` via `asyncio.create_subprocess_exec`,
speaks MCP over JSON-RPC on stdin/stdout. Uses `mcp` python SDK
(`mcp.client.stdio`) which handles the protocol framing.

**HTTP adapter**: connects to `url` via MCP streamable HTTP transport (`mcp.client.streamable_http`).
Supports bearer/header auth.

Both adapters run inside an `asyncio.timeout` equal to `timeout_seconds`.

### McpConnectionManager

- Maintains a process-lifetime cache of live connections keyed by `(server_id, transport, target)`
- Handles reconnect with exponential backoff
- Guards against concurrent calls to the same stdio process (MCP stdio is one client per process; calls serialize)

### McpRuntimeService

Application service coordinating:

1. **register_server** — validate transport + target, store config, encrypt credential
2. **discover_tools** — connect, list tools, upsert into `mcp_tools`, mark `allowed=True` by default for the creating tenant
3. **list_tools** — read from DB (fast path, no connection)
4. **test_connection** — connect + list tools, return latency + tool count
5. **invoke_tool** — permission check → connect → call → audit → return result
6. **delete_server** — close connection, cascade delete tools

### Permission Enforcement

Before any invocation:
1. Server must be `enabled`
2. Tool must exist and `allowed=True` for the tenant
3. Request user must have active tenant membership (already guaranteed by tenant context)
4. Denied → record `McpInvocation(status="denied")`, return error

### Audit

Every invocation (success, error, timeout, denied) writes an `McpInvocation` row.
Result text is truncated to a configurable max (default 4 KB) to bound storage.
Raw secrets are never stored — only `args_hash`.

## Security Considerations

- stdio servers execute arbitrary binaries — operator-controlled only. Registration
  SHALL require tenant ADMIN role.
- Remote HTTP servers: `https` enforced unless `allow_insecure` flag set for dev.
- Credentials encrypted at rest; never returned by API (masked).
- Response size bounded by `max_payload_bytes`.

## Decisions

### Python `mcp` SDK over raw JSON-RPC

The `mcp` official SDK (MIT) handles protocol negotiation, JSON-RPC framing, and both
stdio + streamable HTTP transports. Building this by hand is error-prone and unnecessary.
The SDK is a `uv` dependency.

### DB-cached tool registry over live discovery every call

Discovery requires a connection round-trip per server. Caching tool descriptors in DB
makes the query planner (next change) fast and offline-capable. Discovery is re-run
manually via UI or on a schedule.

### Reuse encrypted credentials table

`rag_provider_credentials` already encrypts values. MCP server credentials use the same
table with `provider="mcp"` and `key_name=<server_id>:auth_token`. No new crypto.

## Risks / Trade-offs

- [stdio subprocess lifecycle] — zombie processes on crash. Mitigated by `async with`
  context managers from the SDK + `process.terminate()` on close + server shutdown hook.
- [SDK version drift] — MCP spec moves fast. Pin the SDK version and update deliberately.
- [Tool explosion] — many servers × many tools. Mitigated by per-tenant `allowed` gate,
  search/filter in UI, and disabled-by-default onboarding.
- [Long-running calls] — timeout enforced; callers get `timeout` status + partial result if any.

## Open Questions

- Should tool invocation support streaming responses (e.g., SSE from a tool)? Defer to later.
- Should server connections be per-tenant or shared singleton? Currently per-tenant
  isolation via credentials + tools; connection process can be shared for stdio with a
  single active client.
