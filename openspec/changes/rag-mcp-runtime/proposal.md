# Proposal: RAG MCP Runtime

## Problem

The RAG platform currently has no way to integrate external tools and data sources
beyond the document-embedding pipeline. To make grounded answers truly useful, the
system needs the ability to call external tools — search repositories, query databases,
invoke APIs, run code — from within a query.

This change builds the **MCP (Model Context Protocol) runtime engine** that lets the
platform connect to arbitrary MCP servers, discover their tools, and invoke them
server-side with full security controls and auditability.

## Proposed Solution

A server-side MCP runtime that:

1. **Manages MCP server connections** — stdio (local process) and streamable HTTP/SSE (remote)
2. **Discovers tools** — lists all tools exposed by each connected MCP server
3. **Invokes tools** — calls MCP tools server-side with typed input and timeout
4. **Stores everything in DB** — server registry, tool registry, credentials (encrypted), audit log
5. **Exposes management API + UI** — add/edit/test/delete servers, view tools, test connections

## Key Design Decisions

- **Server-side execution**: MCP clients run in the API/worker process, not the browser.
  This allows stdio subprocess spawning, credential security, and complete audit.
- **Transport support**: `stdio` (spawn local binary/server) and `streamable HTTP`/`SSE` (remote URL with optional auth).
- **Tool registry**: discovered tools are cached in DB so the query planner can list available tools without a connection round-trip each time.
- **Encrypted credentials**: MCP server tokens/credentials stored encrypted (reuse existing `crypto.py` AES-GCM).
- **Permissions model**: per-server callable status, per-tool allow/deny, per-tenant isolation.
- **Audit**: every tool invocation logged (server, tool, args hash, caller, timestamp, success/failure).
- **UI**: full management page under Settings.

## What This Is Not

- Not the query planner — this is the runtime only; planner consumes this in a separate change.
- Not RAG retrieval — this is external tool execution, complementary to retrieval.
- Not a sandbox — tool execution is the MCP server's responsibility; the runtime enforces
  timeout, payload limits, and permissions, but isolation is delegated to the server.

## Success Criteria

- Register, connect, and test a stdio MCP server and a remote HTTP MCP server
- List all tools from a connected server in UI
- Invoke a tool server-side with typed arguments and get the result
- Per-tool permission enforcement (allow/deny per tenant)
- Every invocation audited in DB
- Credentials encrypted at rest
- Existing tests pass

## Scope

**In scope:**
- `McpServer` entity + DB (server config, transport, credentials, status)
- `McpTool` registry (discovered tools per server)
- `McpConnectionManager` (stdio + HTTP/SSE clients)
- `McpRuntimeService` (invoke, discover, health)
- API: CRUD servers, discover/list tools, test connection, invoke tool
- Audit log table
- Encrypted credential storage (reuse `crypto.py`)
- UI: MCP servers page + tool browser + invoke/test
- Shared Zod schemas + types

**Out of scope:**
- Query planner integration (`rag-query-task-planner`)
- Retrieval/BM25 (uses tool results only as evidence source)
- OAuth credential flows (stored static keys first)