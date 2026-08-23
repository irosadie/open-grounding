## 1. Database — Schema

- [x] 1.1 Buat ORM models `McpServerRecord`, `McpToolRecord`, `McpInvocationRecord` di `apps/api/app/infrastructure/rag_catalog.py`
- [x] 1.2 Alembic migration: tabel `mcp_servers`, `mcp_tools`, `mcp_invocations` dengan FK + index
- [x] 1.3 Unique constraint `mcp_tools (tenant_id, server_id, name)` dan `mcp_invocations (tenant_id, created_at)`

## 2. API — Domain

- [x] 2.1 Buat domain entities `McpServer`, `McpTool`, `McpInvocation`, `McpToolDescriptor`, `McpCallResult` di `apps/api/app/domain/mcp/`
- [x] 2.2 Buat enums: `McpTransport` (stdio/http/sse), `McpServerStatus`, `McpInvocationStatus` di `apps/api/app/domain/mcp/`
- [x] 2.3 Buat repository interfaces `McpServerRepository`, `McpToolRepository`, `McpInvocationRepository` di `apps/api/app/domain/mcp/`
- [x] 2.4 Implementasi SQLAlchemy repositories — methods: CRUD servers, upsert/list tools, log/list invocations, prune

## 3. API — MCP Client Layer

- [x] 3.1 Tambah dependency `mcp` SDK ke `pyproject.toml` (uv)
- [x] 3.2 Buat `McpClientAdapter` protocol di `apps/api/app/domain/mcp/adapter_ports.py`
- [x] 3.3 Implementasi `StdioMcpClient` di `apps/api/app/infrastructure/mcp/stdio_client.py` — spawn via `asyncio.create_subprocess_exec`, pakai SDK `mcp.client.stdio`
- [x] 3.4 Implementasi `HttpMcpClient` di `apps/api/app/infrastructure/mcp/http_client.py` — streamable HTTP + SSE, bearer/header auth
- [x] 3.5 Implementasi `McpConnectionManager` di `apps/api/app/infrastructure/mcp/connection_manager.py` — cache koneksi, reconnect backoff, guard concurrent calls

## 4. API — Runtime Service

- [x] 4.1 Buat `apps/api/app/application/mcp_runtime_service.py` — `McpRuntimeService`
- [x] 4.2 Implementasi `register_server` — validasi transport/target, encrypt credential, simpan config
- [x] 4.3 Implementasi `discover_tools` — connect, list tools, upsert ke registry, default allowed=false
- [x] 4.4 Implementasi `test_connection` — connect + list, return latency + tool count
- [x] 4.5 Implementasi `invoke_tool` — permission check → args validation → call → audit → return
- [x] 4.6 Implementasi `list_servers`, `get_server`, `update_server`, `delete_server`
- [x] 4.7 Implementasi `list_invocations` + `prune_invocations`

## 5. API — Routes & DI

- [x] 5.1 Tambah DTOs ke `apps/api/app/interfaces/http/schemas.py`: `CreateMcpServerRequest`, `McpServerResponse`, `McpToolResponse`, `McpInvocationResponse`, `InvokeToolRequest`
- [x] 5.2 Buat routes `mcp_router` di `apps/api/app/interfaces/http/routes.py` (REQ-7.1 – REQ-7.11)
- [x] 5.3 Tambah DI ke `apps/api/app/interfaces/http/dependencies.py`
- [x] 5.4 Register router di `apps/api/app/main.py`

## 6. Shared Contracts

- [x] 6.1 Tambah Zod schemas `mcpServerSchema`, `invokeToolSchema` di `packages/schemas/mcp.ts`
- [x] 6.2 Tambah response types `McpServerResponse`, `McpToolResponse`, `McpInvocationResponse` di `packages/types/mcp-response.ts`

## 7. Frontend — Hooks

- [x] 7.1 Tambah API route constants + query keys untuk MCP
- [x] 7.2 Buat hooks di `apps/web/hooks/transactions/use-mcp/`:
  - `useMcpServers`, `useCreateMcpServer`, `useUpdateMcpServer`, `useDeleteMcpServer`
  - `useMcpServerTest`, `useMcpServerDiscover`, `useMcpTools`, `useUpdateMcpTool`
  - `useMcpToolInvoke`, `useMcpInvocations`

## 8. Frontend — UI

- [x] 8.1 Buat halaman `/console/settings/mcp` — list servers + status badges + create/edit/delete dialog
- [x] 8.2 Buat `mcp-servers-content.tsx` — form create/edit (transport selector, conditional fields, credential password input)
- [x] 8.3 Buat tool browser per server — list tools, `allowed` toggle, "Try it" invoke form (JSON editor dari input_schema)
- [x] 8.4 Buat halaman `/console/settings/mcp/audit` — list invocations + filters + detail (args hash, truncated result)
- [x] 8.5 Tambah nav item MCP di `apps/web/configs/console.ts` (di bawah Settings)

## 9. OpenAPI & Verification

- [x] 9.1 Regenerate `docs/openapi.json`
- [x] 9.2 Run `bun run typecheck` (web) — no errors
- [x] 9.3 Run `bun run lint` (web) — no errors
- [x] 9.4 Run `bun run test` (api) — all pass
- [x] 9.5 Test end-to-end: register stdio MCP server → discover tools → allow tool → invoke → audit tercatat
- [x] 9.6 Test end-to-end: register remote HTTP MCP server → test connection → invoke
- [x] 9.7 Test denied tool → audit status=denied
