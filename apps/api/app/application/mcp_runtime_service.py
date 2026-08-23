"""Application orchestration for tenant-scoped MCP server runtime operations."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

from app.application.provider_credential_service import ProviderCredentialService
from app.core.settings import Settings
from app.domain.audit import AuditAction
from app.domain.errors import DomainError
from app.domain.mcp.adapter_ports import McpClientAdapter
from app.domain.mcp.entities import McpInvocation, McpServer, McpTool
from app.domain.mcp.enums import McpInvocationStatus, McpServerStatus, McpTransport
from app.domain.mcp.repositories import McpInvocationRepository, McpServerRepository, McpToolRepository
from app.domain.models import UserRole
from app.domain.tenant_context import TenantContext
from app.infrastructure.audit import record_audit_event
from app.infrastructure.mcp.connection_manager import McpConnectionManager
from app.infrastructure.mcp.http_client import HttpMcpClient
from app.infrastructure.mcp.stdio_client import StdioMcpClient


class McpRuntimeService:
    def __init__(
        self,
        settings: Settings,
        servers: McpServerRepository,
        tools: McpToolRepository,
        invocations: McpInvocationRepository,
        credentials: ProviderCredentialService,
        connections: McpConnectionManager,
    ) -> None:
        self._settings = settings
        self._servers = servers
        self._tools = tools
        self._invocations = invocations
        self._credentials = credentials
        self._connections = connections

    async def register_server(self, *, tenant: TenantContext, **values: object) -> dict[str, object]:
        self._require_admin(tenant)
        self._validate_config(values)
        headers = dict(values.get("headers", {}))
        if values.get("credential_header"):
            headers["__credential_header__"] = str(values["credential_header"])
        server = await self._servers.create(
            tenant_id=tenant.tenant_id,
            name=str(values["name"]).strip(),
            transport=McpTransport(str(values["transport"])),
            command=values.get("command"),
            args=list(values.get("args", [])),
            url=values.get("url"),
            auth_type=str(values.get("auth_type", "none")),
            credential_ref=None,
            headers_json=headers,
            timeout_seconds=int(values.get("timeout_seconds", 30)),
            max_payload_bytes=int(values.get("max_payload_bytes", 1_048_576)),
            allow_insecure=bool(values.get("allow_insecure", False)),
            enabled=bool(values.get("enabled", True)),
        )
        credential = values.get("credential")
        if isinstance(credential, str) and credential.strip():
            key_name = self._credential_key(server, values.get("credential_header"))
            await self._credentials.set_credential(tenant=tenant, provider="mcp", key_name=key_name, value=credential)
            server = await self._servers.update(tenant_id=tenant.tenant_id, server_id=server.id, credential_ref=key_name) or server
        record_audit_event(
            tenant_id=tenant.tenant_id,
            actor_id=tenant.user_id,
            action=AuditAction.CREATE,
            resource_type="mcp_server",
            resource_id=server.id,
            details={"transport": server.transport.value},
        )
        return _server_dto(server, has_credential=credential is not None and bool(str(credential).strip()))

    async def update_server(self, *, tenant: TenantContext, server_id: str, **changes: object) -> dict[str, object]:
        self._require_admin(tenant)
        current = await self._get_server(tenant.tenant_id, server_id)
        merged = {"name": current.name, "transport": current.transport.value, "command": current.command, "args": current.args, "url": current.url, "allow_insecure": current.allow_insecure}
        merged.update({key: value for key, value in changes.items() if value is not None and key != "credential"})
        self._validate_config(merged)
        update_values = {key: value for key, value in changes.items() if key not in {"credential", "credential_header"} and value is not None}
        if "transport" in update_values:
            update_values["transport"] = McpTransport(str(update_values["transport"]))
        if "headers" in update_values:
            update_values["headers_json"] = update_values.pop("headers")
        if changes.get("credential_header"):
            headers = dict(update_values.get("headers_json", current.headers_json))
            headers["__credential_header__"] = str(changes["credential_header"])
            update_values["headers_json"] = headers
        credential = changes.get("credential")
        if isinstance(credential, str) and credential.strip():
            key_name = self._credential_key(current, changes.get("credential_header"))
            await self._credentials.set_credential(tenant=tenant, provider="mcp", key_name=key_name, value=credential)
            update_values["credential_ref"] = key_name
        updated = await self._servers.update(tenant_id=tenant.tenant_id, server_id=server_id, **update_values)
        if updated is None:
            raise DomainError("MCP_SERVER_NOT_FOUND", "MCP server not found", 404)
        await self._connections.close(self._connection_key(current))
        if self._connection_key(updated) != self._connection_key(current):
            await self._connections.close(self._connection_key(updated))
        return _server_dto(updated, has_credential=updated.credential_ref is not None)

    async def list_servers(self, *, tenant: TenantContext) -> list[dict[str, object]]:
        return [_server_dto(server, has_credential=server.credential_ref is not None) for server in await self._servers.list(tenant_id=tenant.tenant_id)]

    async def get_server(self, *, tenant: TenantContext, server_id: str) -> dict[str, object]:
        server = await self._get_server(tenant.tenant_id, server_id)
        return _server_dto(server, has_credential=server.credential_ref is not None)

    async def delete_server(self, *, tenant: TenantContext, server_id: str) -> None:
        self._require_admin(tenant)
        server = await self._get_server(tenant.tenant_id, server_id)
        await self._connections.close(self._connection_key(server))
        if not await self._servers.delete(tenant_id=tenant.tenant_id, server_id=server_id):
            raise DomainError("MCP_SERVER_NOT_FOUND", "MCP server not found", 404)
        if server.credential_ref:
            await self._credentials.revoke(tenant=tenant, provider="mcp", key_name=server.credential_ref)

    async def discover_tools(self, *, tenant: TenantContext, server_id: str) -> list[dict[str, object]]:
        self._require_admin(tenant)
        server = await self._get_server(tenant.tenant_id, server_id)
        client = await self._connect(server, tenant.tenant_id)
        try:
            descriptors = await asyncio.wait_for(client.list_tools(), timeout=server.timeout_seconds)
            tools = await self._tools.upsert_discovered(tenant_id=tenant.tenant_id, server_id=server.id, tools=descriptors, discovered_at=datetime.now(UTC).replace(tzinfo=None))
            await self._servers.update(tenant_id=tenant.tenant_id, server_id=server.id, status=McpServerStatus.CONNECTED, last_error=None)
            return [_tool_dto(tool) for tool in tools]
        except Exception as error:
            await self._mark_error(server, error)
            raise DomainError("MCP_DISCOVERY_ERROR", _safe_error(error), 502) from error

    async def test_connection(self, *, tenant: TenantContext, server_id: str) -> dict[str, object]:
        server = await self._get_server(tenant.tenant_id, server_id)
        started = time.perf_counter()
        try:
            client = await self._connect(server, tenant.tenant_id)
            tools = await asyncio.wait_for(client.list_tools(), timeout=server.timeout_seconds)
            await self._servers.update(tenant_id=tenant.tenant_id, server_id=server.id, status=McpServerStatus.CONNECTED, last_error=None)
            return {"status": "connected", "latencyMs": int((time.perf_counter() - started) * 1000), "toolCount": len(tools)}
        except Exception as error:
            await self._mark_error(server, error)
            return {"status": "error", "latencyMs": int((time.perf_counter() - started) * 1000), "toolCount": 0, "error": _safe_error(error)}

    async def list_tools(self, *, tenant: TenantContext, server_id: str, include_stale: bool = False) -> list[dict[str, object]]:
        await self._get_server(tenant.tenant_id, server_id)
        return [_tool_dto(tool) for tool in await self._tools.list(tenant_id=tenant.tenant_id, server_id=server_id, include_stale=include_stale)]

    async def list_allowed_tools(self, *, tenant: TenantContext) -> list[McpTool]:
        """Return all allowed, non-stale tools across all enabled servers for a tenant."""
        servers = await self._servers.list(tenant_id=tenant.tenant_id)
        result: list[McpTool] = []
        for server in servers:
            if not server.enabled:
                continue
            tools = await self._tools.list(tenant_id=tenant.tenant_id, server_id=server.id)
            result.extend(tool for tool in tools if tool.allowed and not tool.is_stale)
        return result

    async def set_tool_allowed(self, *, tenant: TenantContext, tool_id: str, allowed: bool) -> dict[str, object]:
        self._require_admin(tenant)
        tool = await self._tools.set_allowed(tenant_id=tenant.tenant_id, tool_id=tool_id, allowed=allowed)
        if tool is None:
            raise DomainError("MCP_TOOL_NOT_FOUND", "MCP tool not found", 404)
        return _tool_dto(tool)

    async def invoke_tool(self, *, tenant: TenantContext, tool_id: str, arguments: dict[str, object]) -> dict[str, object]:
        tool = await self._tools.find_by_id(tenant_id=tenant.tenant_id, tool_id=tool_id)
        if tool is None:
            raise DomainError("MCP_TOOL_NOT_FOUND", "MCP tool not found", 404)
        args_hash = _args_hash(arguments)
        server = await self._get_server(tenant.tenant_id, tool.server_id)
        if not server.enabled or not tool.allowed or tool.is_stale:
            await self._audit(tenant, tool, args_hash, McpInvocationStatus.DENIED, "Tool is not allowed", 0)
            raise DomainError("TOOL_DENIED", "MCP tool is not allowed", 403)
        try:
            validate(instance=arguments, schema=tool.input_schema)
        except JsonSchemaValidationError as error:
            await self._audit(tenant, tool, args_hash, McpInvocationStatus.ERROR, "Invalid tool arguments", 0)
            raise DomainError("INVALID_TOOL_ARGS", "Tool arguments do not match the input schema", 422) from error
        started = time.perf_counter()
        try:
            client = await self._connect(server, tenant.tenant_id)
            result = await asyncio.wait_for(client.call_tool(tool.name, arguments), timeout=server.timeout_seconds)
            text = _bounded_text(result.result, server.max_payload_bytes)
            status_value = McpInvocationStatus.ERROR if result.is_error else McpInvocationStatus.SUCCESS
            await self._audit(tenant, tool, args_hash, status_value, text, _duration_ms(started))
            if result.is_error:
                raise DomainError("TOOL_ERROR", _safe_error_text(text), 502)
            return {"result": _bounded_result(result.result, server.max_payload_bytes)}
        except TimeoutError as error:
            await self._audit(tenant, tool, args_hash, McpInvocationStatus.TIMEOUT, "MCP tool invocation timed out", _duration_ms(started))
            raise DomainError("TOOL_TIMEOUT", "MCP tool invocation timed out", 504) from error
        except DomainError:
            raise
        except Exception as error:
            message = _safe_error(error)
            await self._audit(tenant, tool, args_hash, McpInvocationStatus.ERROR, message, _duration_ms(started))
            raise DomainError("TOOL_ERROR", message, 502) from error

    async def list_invocations(self, *, tenant: TenantContext, **filters: object) -> list[dict[str, object]]:
        if tenant.role is not UserRole.ADMIN:
            filters["user_id"] = tenant.user_id
        if isinstance(filters.get("status"), str):
            try:
                filters["status"] = McpInvocationStatus(str(filters["status"]))
            except ValueError as error:
                raise DomainError("VALIDATION_ERROR", "Unsupported invocation status", 422) from error
        rows = await self._invocations.list(tenant_id=tenant.tenant_id, **filters)
        return [_invocation_dto(row) for row in rows]

    async def prune_invocations(self, *, tenant: TenantContext, retention_days: int = 30) -> int:
        self._require_admin(tenant)
        before = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=retention_days)
        return await self._invocations.prune(tenant_id=tenant.tenant_id, before=before)

    async def _connect(self, server: McpServer, tenant_id: str) -> McpClientAdapter:
        key = self._connection_key(server)
        credential = None
        if server.credential_ref:
            credential = await self._credentials.get_decrypted(tenant_id=tenant_id, provider="mcp", key_name=server.credential_ref)
        return await asyncio.wait_for(self._connections.get_or_connect(key, lambda: self._client(server, credential)), server.timeout_seconds)

    def _client(self, server: McpServer, credential: str | None) -> McpClientAdapter:
        if server.transport is McpTransport.STDIO:
            if server.command is None:
                raise DomainError("VALIDATION_ERROR", "Command is required for stdio", 422)
            return StdioMcpClient(server.command, server.args, server.timeout_seconds)
        headers = {key: str(value) for key, value in server.headers_json.items() if not key.startswith("__")}
        if credential:
            header_name = str(server.headers_json.get("__credential_header__", "Authorization" if server.auth_type == "bearer" else "X-MCP-Credential"))
            headers[header_name] = f"Bearer {credential}" if server.auth_type == "bearer" else credential
        if not server.url:
            raise DomainError("VALIDATION_ERROR", "URL is required for remote MCP transports", 422)
        return HttpMcpClient(server.url, headers, server.timeout_seconds, server.allow_insecure)

    async def _get_server(self, tenant_id: str, server_id: str) -> McpServer:
        server = await self._servers.find_by_id(tenant_id=tenant_id, server_id=server_id)
        if server is None:
            raise DomainError("MCP_SERVER_NOT_FOUND", "MCP server not found", 404)
        return server

    async def _mark_error(self, server: McpServer, error: Exception) -> None:
        await self._servers.update(tenant_id=server.tenant_id, server_id=server.id, status=McpServerStatus.ERROR, last_error=_safe_error(error))

    async def _audit(self, tenant: TenantContext, tool: McpTool, args_hash: str, status_value: McpInvocationStatus, result: str, duration_ms: int) -> McpInvocation:
        return await self._invocations.create(
            tenant_id=tenant.tenant_id, server_id=tool.server_id, tool_id=tool.id, user_id=tenant.user_id, args_json={}, args_hash=args_hash, status=status_value, result_text=result[:4096], duration_ms=duration_ms
        )

    @staticmethod
    def _require_admin(tenant: TenantContext) -> None:
        if tenant.role is not UserRole.ADMIN:
            raise DomainError.forbidden("Administrator access is required for MCP configuration")

    @staticmethod
    def _validate_config(values: dict[str, object]) -> None:
        try:
            transport = McpTransport(str(values["transport"]))
        except (KeyError, ValueError) as error:
            raise DomainError("VALIDATION_ERROR", "Unsupported MCP transport", 422) from error
        if transport is McpTransport.STDIO and not str(values.get("command", "")).strip():
            raise DomainError("VALIDATION_ERROR", "Command is required for stdio", 422)
        if transport is not McpTransport.STDIO:
            url = str(values.get("url", ""))
            parsed = urlparse(url)
            if not parsed.netloc or parsed.scheme not in {"http", "https"} or (parsed.scheme == "http" and not bool(values.get("allow_insecure", False))):
                raise DomainError("VALIDATION_ERROR", "Remote MCP URL must be HTTPS unless insecure transport is enabled", 422)

    @staticmethod
    def _credential_key(server: McpServer, header: object) -> str:
        return f"{server.id}:{str(header or 'auth_token')}"

    @staticmethod
    def _connection_key(server: McpServer) -> tuple[str, str, str]:
        return (server.id, server.transport.value, server.command or server.url or "")


def _args_hash(arguments: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _duration_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _bounded_text(value: object, limit: int) -> str:
    return json.dumps(value, default=str, ensure_ascii=True)[:limit]


def _bounded_result(value: object, limit: int) -> object:
    text = _bounded_text(value, limit)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _safe_error(error: Exception) -> str:
    return str(error).replace("Bearer ", "Bearer [REDACTED]")[:2048] or error.__class__.__name__


def _safe_error_text(text: str) -> str:
    return text[:2048]


def _server_dto(server: McpServer, *, has_credential: bool) -> dict[str, object]:
    return {
        "id": server.id,
        "name": server.name,
        "transport": server.transport.value,
        "command": server.command,
        "args": server.args,
        "url": server.url,
        "authType": server.auth_type,
        "hasCredential": has_credential,
        "headers": {key: value for key, value in server.headers_json.items() if not key.startswith("__")},
        "timeoutSeconds": server.timeout_seconds,
        "maxPayloadBytes": server.max_payload_bytes,
        "allowInsecure": server.allow_insecure,
        "enabled": server.enabled,
        "status": server.status.value,
        "lastError": server.last_error,
        "createdAt": server.created_at.isoformat(),
        "updatedAt": server.updated_at.isoformat(),
    }


def _tool_dto(tool: McpTool) -> dict[str, object]:
    return {
        "id": tool.id,
        "serverId": tool.server_id,
        "name": tool.name,
        "description": tool.description,
        "inputSchema": tool.input_schema,
        "allowed": tool.allowed,
        "isStale": tool.is_stale,
        "lastDiscoveredAt": tool.last_discovered_at.isoformat(),
    }


def _invocation_dto(row: McpInvocation) -> dict[str, object]:
    return {
        "id": row.id,
        "serverId": row.server_id,
        "toolId": row.tool_id,
        "userId": row.user_id,
        "argsHash": row.args_hash,
        "status": row.status.value,
        "resultText": row.result_text,
        "durationMs": row.duration_ms,
        "createdAt": row.created_at.isoformat(),
    }
