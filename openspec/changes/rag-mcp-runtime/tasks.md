## 1. Database — Schema

- [ ] 1.1 Buat ORM models `McpServerRecord`, `McpToolRecord`, `McpInvocationRecord` di `apps/api/app/infrastructure/rag_catalog.py`
- [ ] 1.2 Alembic migration: tabel `mcp_servers`, `mcp_tools`, `mcp_invocations` dengan FK + index
- [ ] 1.3 Unique constraint `mcp_tools (tenant_id, server_id, name)` dan `mcp_invocations (tenant_id, created_at)`

## 2. API — Domain

- [ ] 2.1 Buat domain entities `McpServer`, `McpTool`, `McpInvocation`, `McpToolDescriptor`, `McpCallResult` di `apps/api/app/domain/mcp/`
- [ ] 2.2 Buat enums: `McpTransport` (stdio/http/sse), `McpServerStatus`, `McpInvocationStatus` di `apps/api/app/domain/mcp/`
- [ ] 2.3 Buat repository interfaces `McpServerRepository`, `McpToolRepository`, `McpInvocationRepository` di `apps/api/app/domain/mcp/`
- [ ] 2.4 Implementasi SQLAlchemy repositories — methods: CRUD servers, upsert/list tools, log/list invocations, prune

## 3. API — MCP Client Layer

- [ ] 3.1 Tambah dependency `mcp` SDK ke `pyproject.toml` (uv)
- [ ] 3.2 Buat `McpClientAdapter` protocol di `apps/api/app/domain/mcp/adapter_ports.py`
- [ ] 3.3 Implementasi `StdioMcpClient` di `apps/api/app/infrastructure/mcp/stdio_client.py` — spawn via `asyncio.create_subprocess_exec`, pakai SDK `mcp.client.stdio`
- [ ] 3.4 Implementasi `HttpMcpClient` di `apps/api/app/infrastructure/mcp/http_client.py` — streamable HTTP + SSE, bearer/header auth
- [ ] 3.5 Implementasi `McpConnectionManager` di `apps/api/app/infrastructure/mcp/connection_manager.py` — cache koneksi, reconnect backoff, guard concurrent calls

## 4. API — Runtime Service

- [ ] 4.1 Buat `apps/api/app/application/mcp_runtime_service.py` — `McpRuntimeService`
- [ ] 4.2 Implementasi `register_server` — validasi transport/target, encrypt credential, simpan config
- [ ] 4.3 Implementasi `discover_tools` — connect, list tools, upsert ke registry, default allowed=false
- [ ] 4.4 Implementasi `test_connection` — connect + list, return latency + tool count
- [ ] 4.5 Implementasi `invoke_tool` — permission check → args validation → call → audit → return
- [ ] 4.6 Implementasi `list_servers`, `get_server`, `update_server`, `delete_server`
- [ ] 4.7 Implementasi `list_invocations` + `prune_invocations`

## 5. API — Routes & DI

- [ ] 5.1 Tambah DTOs ke `apps/api/app/interfaces/http/schemas.py`: `CreateMcpServerRequest`, `McpServerResponse`, `McpToolResponse`, `McpInvocationResponse`, `InvokeToolRequest`
- [ ] 5.2 Buat routes `mcp_router` di `apps/api/app/interfaces/http/routes.py` (REQ-7.1 – REQ-7.11)
- [ ] 5.3 Tambah DI ke `apps/api/app/interfaces/http/dependencies.py`
- [ ] 5.4 Register router di `apps/api/app/main.py`

## 6. Shared Contracts

- [ ] 6.1 Tambah Zod schemas `mcpServerSchema`, `invokeToolSchema` di `packages/schemas/mcp.ts`
- [ ] 6.2 Tambah response types `McpServerResponse`, `McpToolResponse`, `McpInvocationResponse` di `packages/types/mcp-response.ts`

## 7. Frontend — Hooks

- [ ] 7.1 Tambah API route constants + query keys untuk MCP
- [ ] 7.2 Buat hooks di `apps/web/hooks/transactions/use-mcp/`:
  - `useMcpServers`, `useCreateMcpServer`, `useUpdateMcpServer`, `useDeleteMcpServer`
  - `useMcpServerTest`, `useMcpServerDiscover`, `useMcpTools`, `useUpdateMcpTool`
  - `useMcpToolInvoke`, `useMcpInvocations`

## 8. Frontend — UI

- [ ] 8.1 Buat halaman `/console/settings/mcp` — list servers + status badges + create/edit/delete dialog
- [ ] 8.2 Buat `mcp-servers-content.tsx` — form create/edit (transport selector, conditional fields, credential password input)
- [ ] 8.3 Buat tool browser per server — list tools, `allowed` toggle, "Try it" invoke form (JSON editor dari input_schema)
- [ ] 8.4 Buat halaman `/console/settings/mcp/audit` — list invocations + filters + detail (args hash, truncated result)
- [ ] 8.5 Tambah nav item MCP di `apps/web/configs/console.ts` (di bawah Settings)

## 9. OpenAPI & Verification

- [ ] 9.1 Regenerate `docs/openapi.json`
- [ ] 9.2 Run `bun run typecheck` (web) — no errors
- [ ] 9.3 Run `bun run lint` (web) — no errors
- [ ] 9.4 Run `bun run test` (api) — all pass
- [ ] 9.5 Test end-to-end: register stdio MCP server → discover tools → allow tool → invoke → audit tercatat
- [ ] 9.6 Test end-to-end: register remote HTTP MCP server → test connection → invoke
- [ ] 9.7 Test denied tool → audit status=denied
