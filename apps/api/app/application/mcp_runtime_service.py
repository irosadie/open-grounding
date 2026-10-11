"""Application orchestration for tenant-scoped MCP server runtime operations."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import cast
from urllib.parse import urlparse
from uuid import uuid4

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

from app.application.provider_credential_service import ProviderCredentialService
from app.core.llm_rollout_trace import get_rollout_trace
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

logger = logging.getLogger(__name__)

# TASK 2.5 budgets / cache / circuit-breaker (single owner: runtime).
_CONNECT_BUDGET_SECONDS = 5.0
_CALL_BUDGET_SECONDS = 10.0
_LIST_TOTAL_BUDGET_SECONDS = 15.0
_LIST_CONCURRENCY = 4
_TOOLS_CACHE_TTL_SECONDS = 60.0
_CIRCUIT_FAILURE_THRESHOLD = 3
_CIRCUIT_COOLDOWN_SECONDS = 30.0


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
        # list_tools cache: (tenant_id, server_id) -> (tools, cached_at_monotonic)
        self._tools_cache: dict[tuple[str, str], tuple[list[McpTool], float]] = {}
        # circuit-breaker: server_id -> {"failures": int, "opened_until": float monotonic}
        self._circuit: dict[str, dict[str, float]] = {}
        self._audit_tasks: set[asyncio.Task[object]] = set()

    async def register_server(self, *, tenant: TenantContext, **values: object) -> dict[str, object]:
        self._require_admin(tenant)
        self._validate_config(values)
        headers = _object_dict(values.get("headers"))
        if values.get("credential_header"):
            headers["__credential_header__"] = str(values["credential_header"])
        server = await self._servers.create(
            tenant_id=tenant.tenant_id,
            name=str(values["name"]).strip(),
            transport=McpTransport(str(values["transport"])),
            command=_optional_str(values.get("command")),
            args=_string_list(values.get("args")),
            url=_optional_str(values.get("url")),
            auth_type=str(values.get("auth_type", "none")),
            credential_ref=None,
            headers_json=headers,
            timeout_seconds=_int_value(values.get("timeout_seconds"), 30),
            max_payload_bytes=_int_value(values.get("max_payload_bytes"), 1_048_576),
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
        merged: dict[str, object] = {"name": current.name, "transport": current.transport.value, "command": current.command, "args": current.args, "url": current.url, "allow_insecure": current.allow_insecure}
        merged.update({key: value for key, value in changes.items() if value is not None and key != "credential"})
        self._validate_config(merged)
        update_values: dict[str, object] = {key: value for key, value in changes.items() if key not in {"credential", "credential_header"} and value is not None}
        if "transport" in update_values:
            update_values["transport"] = McpTransport(str(update_values["transport"]))
        if "headers" in update_values:
            update_values["headers_json"] = update_values.pop("headers")
        if changes.get("credential_header"):
            headers = _object_dict(update_values.get("headers_json", current.headers_json))
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
        self._invalidate_tools_cache(tenant.tenant_id, server_id)
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
        self._invalidate_tools_cache(tenant.tenant_id, server_id)
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
            self._invalidate_tools_cache(tenant.tenant_id, server.id)
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

    async def list_allowed_tools(self, *, tenant: TenantContext, freshness_seconds: int | None = None) -> list[McpTool]:
        """Return all allowed, non-stale tools across all enabled servers for a tenant."""
        servers = await self._servers.list(tenant_id=tenant.tenant_id)
        enabled = [server for server in servers if server.enabled]
        if not enabled:
            return []
        semaphore = asyncio.Semaphore(_LIST_CONCURRENCY)

        async def _fetch_one(server: McpServer) -> list[McpTool]:
            async with semaphore:
                cached = self._get_cached_tools(tenant.tenant_id, server.id, freshness_seconds)
                if cached is not None:
                    return [tool for tool in cached if tool.allowed and not tool.is_stale]
                try:
                    tools = await asyncio.wait_for(
                        self._tools.list(tenant_id=tenant.tenant_id, server_id=server.id),
                        timeout=_CONNECT_BUDGET_SECONDS,
                    )
                except Exception as error:
                    logger.warning(
                        "MCP list tools skipped tenant_id=%s server_id=%s error=%s",
                        tenant.tenant_id,
                        server.id,
                        _safe_error(error),
                    )
                    return []
                self._set_cached_tools(tenant.tenant_id, server.id, tools, freshness_seconds)
                return [tool for tool in tools if tool.allowed and not tool.is_stale]

        try:
            nested = await asyncio.wait_for(asyncio.gather(*[_fetch_one(server) for server in enabled]), timeout=_LIST_TOTAL_BUDGET_SECONDS)
        except TimeoutError as error:
            logger.warning("MCP list_allowed_tools total budget exceeded tenant_id=%s error=%s", tenant.tenant_id, error)
            return []
        return [tool for group in nested for tool in group]

    async def set_tool_allowed(self, *, tenant: TenantContext, tool_id: str, allowed: bool) -> dict[str, object]:
        self._require_admin(tenant)
        tool = await self._tools.set_allowed(tenant_id=tenant.tenant_id, tool_id=tool_id, allowed=allowed)
        if tool is None:
            raise DomainError("MCP_TOOL_NOT_FOUND", "MCP tool not found", 404)
        self._invalidate_tools_cache(tenant.tenant_id, tool.server_id)
        return _tool_dto(tool)

    async def invoke_tool(
        self,
        *,
        tenant: TenantContext,
        tool_id: str,
        arguments: dict[str, object],
        max_payload_bytes: int | None = None,
        timeout_seconds: int | None = None,
        freshness_seconds: int | None = None,
    ) -> dict[str, object]:
        trace = get_rollout_trace()
        tool = await self._tools.find_by_id(tenant_id=tenant.tenant_id, tool_id=tool_id)
        if tool is None:
            trace.record("tool_error", {"tool_id": tool_id, "status": "not_found", "arguments": arguments})
            raise DomainError("MCP_TOOL_NOT_FOUND", "MCP tool not found", 404)
        requested_seq = trace.record(
            "tool_call_requested",
            {"tool_id": tool.id, "tool_name": tool.name, "arguments": arguments, "server_id": tool.server_id},
        )
        args_hash = _args_hash(arguments)
        server = await self._get_server(tenant.tenant_id, tool.server_id)
        if not server.enabled or not tool.allowed or tool.is_stale:
            trace.record(
                "policy_decision",
                {"decision": "denied", "reason": "tool_not_allowed", "tool_id": tool.id, "tool_name": tool.name, "requested_seq": requested_seq},
                parent_seq=requested_seq,
            )
            trace.record(
                "tool_error",
                {"tool_id": tool.id, "tool_name": tool.name, "status": "denied", "requested_seq": requested_seq},
                parent_seq=requested_seq,
            )
            await self._audit(tenant, tool, args_hash, McpInvocationStatus.DENIED, "Tool is not allowed", 0)
            raise DomainError("TOOL_DENIED", "MCP tool is not allowed", 403)
        try:
            validate(instance=arguments, schema=tool.input_schema)
        except JsonSchemaValidationError as error:
            trace.record(
                "tool_error",
                {"tool_id": tool.id, "tool_name": tool.name, "status": "invalid_arguments", "requested_seq": requested_seq, "error": str(error)},
                parent_seq=requested_seq,
            )
            await self._audit(tenant, tool, args_hash, McpInvocationStatus.ERROR, "Invalid tool arguments", 0)
            raise DomainError("INVALID_TOOL_ARGS", "Tool arguments do not match the input schema", 422) from error
        started = time.perf_counter()
        payload_limit = min(server.max_payload_bytes, max_payload_bytes) if max_payload_bytes is not None else server.max_payload_bytes
        timeout_limit = min(server.timeout_seconds, timeout_seconds) if timeout_seconds is not None else server.timeout_seconds
        trace.record(
            "tool_execution_started",
            {"tool_id": tool.id, "tool_name": tool.name, "requested_seq": requested_seq},
            parent_seq=requested_seq,
        )
        call_timeout = min(float(timeout_limit), _CALL_BUDGET_SECONDS)
        client_obtained = False
        try:
            client = await self._connect(server, tenant.tenant_id)
            client_obtained = True
            result = await asyncio.wait_for(client.call_tool(tool.name, arguments), timeout=call_timeout)
            text = _bounded_text(result.result, payload_limit)
            duration_ms = _duration_ms(started)
            if result.is_error:
                status_value = McpInvocationStatus.ERROR
                await self._audit(tenant, tool, args_hash, status_value, text, duration_ms)
                trace.record(
                    "tool_error",
                    {
                        "tool_id": tool.id,
                        "tool_name": tool.name,
                        "status": "provider_error",
                        "requested_seq": requested_seq,
                        "result": _bounded_result(result.result, min(payload_limit, 512)),
                        "duration_ms": duration_ms,
                    },
                    parent_seq=requested_seq,
                )
                raise DomainError("TOOL_ERROR", _safe_error_text(text), 502)
            # TASK 1.3: success audit is fire-and-forget — return without awaiting DB.
            invocation_id = str(uuid4())
            produced_at = datetime.now(UTC)
            expires_at = produced_at + timedelta(seconds=freshness_seconds) if freshness_seconds is not None else None
            self._schedule_audit(tenant, tool, args_hash, McpInvocationStatus.SUCCESS, text, duration_ms, invocation_id, trace.trace_id)
            self._record_circuit_success(server.id)
            bounded_result = _bounded_result(result.result, payload_limit)
            trace.record(
                "tool_result",
                {
                    "tool_id": tool.id,
                    "tool_name": tool.name,
                    "status": "success",
                    "requested_seq": requested_seq,
                    "result": _bounded_result(result.result, min(payload_limit, 512)),
                    "duration_ms": duration_ms,
                },
                parent_seq=requested_seq,
            )
            return {
                "result": bounded_result,
                "provenance": {
                    "sourceKind": "MCP",
                    "tenantId": tenant.tenant_id,
                    "serverId": server.id,
                    "toolId": tool.id,
                    "invocationId": invocation_id,
                    "traceId": trace.trace_id,
                    "producedAt": produced_at.isoformat(),
                    "expiresAt": expires_at.isoformat() if expires_at else None,
                    "snippet": text[:400],
                },
            }
        except TimeoutError as error:
            if client_obtained:
                self._record_circuit_failure(server.id)
            trace.record(
                "tool_error",
                {"tool_id": tool.id, "tool_name": tool.name, "status": "timeout", "requested_seq": requested_seq, "duration_ms": _duration_ms(started), "error": str(error)},
                parent_seq=requested_seq,
            )
            await self._audit(tenant, tool, args_hash, McpInvocationStatus.TIMEOUT, "MCP tool invocation timed out", _duration_ms(started))
            raise DomainError("TOOL_TIMEOUT", "MCP tool invocation timed out", 504) from error
        except DomainError:
            raise
        except Exception as error:
            if client_obtained:
                self._record_circuit_failure(server.id)
            message = _safe_error(error)
            trace.record(
                "tool_error",
                {"tool_id": tool.id, "tool_name": tool.name, "status": "error", "requested_seq": requested_seq, "duration_ms": _duration_ms(started), "error": message},
                parent_seq=requested_seq,
            )
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
        status = filters.get("status")
        created_after = filters.get("created_after")
        created_before = filters.get("created_before")
        rows = await self._invocations.list(
            tenant_id=tenant.tenant_id,
            server_id=_optional_str(filters.get("server_id")),
            status=status if isinstance(status, McpInvocationStatus) else None,
            user_id=_optional_str(filters.get("user_id")),
            created_after=created_after if isinstance(created_after, datetime) else None,
            created_before=created_before if isinstance(created_before, datetime) else None,
            limit=_int_value(filters.get("limit"), 100),
        )
        return [_invocation_dto(row) for row in rows]

    async def prune_invocations(self, *, tenant: TenantContext, retention_days: int = 30) -> int:
        self._require_admin(tenant)
        before = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=retention_days)
        return await self._invocations.prune(tenant_id=tenant.tenant_id, before=before)

    async def _connect(self, server: McpServer, tenant_id: str) -> McpClientAdapter:
        if self._is_circuit_open(server.id):
            logger.warning("MCP circuit open, skipping connect tenant_id=%s server_id=%s", tenant_id, server.id)
            raise TimeoutError(f"MCP circuit open for server {server.id}")
        key = self._connection_key(server)
        credential = None
        if server.credential_ref:
            credential = await self._credentials.get_decrypted(tenant_id=tenant_id, provider="mcp", key_name=server.credential_ref)
        connect_timeout = min(float(server.timeout_seconds), _CONNECT_BUDGET_SECONDS)
        try:
            client = await asyncio.wait_for(self._connections.get_or_connect(key, lambda: self._client(server, credential)), connect_timeout)
        except Exception:
            self._record_circuit_failure(server.id)
            raise
        self._record_circuit_success(server.id)
        return client

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

    def _schedule_audit(
        self,
        tenant: TenantContext,
        tool: McpTool,
        args_hash: str,
        status_value: McpInvocationStatus,
        result: str,
        duration_ms: int,
        invocation_id: str,
        trace_id: str,
    ) -> None:
        async def _runner() -> None:
            try:
                await self._audit(tenant, tool, args_hash, status_value, result, duration_ms)
            except Exception as error:
                logger.warning(
                    "MCP audit write failed invocation_id=%s trace_id=%s tenant_id=%s server_id=%s tool_id=%s error=%s",
                    invocation_id,
                    trace_id,
                    tenant.tenant_id,
                    tool.server_id,
                    tool.id,
                    _safe_error(error),
                )

        task = asyncio.create_task(_runner())
        self._audit_tasks.add(task)
        task.add_done_callback(self._audit_tasks.discard)

    def _cache_ttl(self, freshness_seconds: int | None) -> float:
        if freshness_seconds is not None and freshness_seconds > 0:
            return min(_TOOLS_CACHE_TTL_SECONDS, float(freshness_seconds))
        return _TOOLS_CACHE_TTL_SECONDS

    def _get_cached_tools(self, tenant_id: str, server_id: str, freshness_seconds: int | None) -> list[McpTool] | None:
        entry = self._tools_cache.get((tenant_id, server_id))
        if entry is None:
            return None
        tools, cached_at = entry
        if time.monotonic() - cached_at >= self._cache_ttl(freshness_seconds):
            self._tools_cache.pop((tenant_id, server_id), None)
            return None
        return tools

    def _set_cached_tools(self, tenant_id: str, server_id: str, tools: list[McpTool], freshness_seconds: int | None) -> None:
        _ = freshness_seconds
        self._tools_cache[(tenant_id, server_id)] = (tools, time.monotonic())

    def _invalidate_tools_cache(self, tenant_id: str, server_id: str) -> None:
        self._tools_cache.pop((tenant_id, server_id), None)

    def _is_circuit_open(self, server_id: str) -> bool:
        entry = self._circuit.get(server_id)
        if entry is None:
            return False
        return time.monotonic() < entry["opened_until"]

    def _record_circuit_success(self, server_id: str) -> None:
        self._circuit[server_id] = {"failures": 0.0, "opened_until": 0.0}

    def _record_circuit_failure(self, server_id: str) -> None:
        entry = self._circuit.get(server_id)
        failures = int(entry["failures"]) + 1 if entry else 1
        opened_until = entry["opened_until"] if entry else 0.0
        if failures >= _CIRCUIT_FAILURE_THRESHOLD:
            opened_until = time.monotonic() + _CIRCUIT_COOLDOWN_SECONDS
            logger.warning("MCP circuit opened server_id=%s failures=%s cooldown_s=%s", server_id, failures, _CIRCUIT_COOLDOWN_SECONDS)
        self._circuit[server_id] = {"failures": float(failures), "opened_until": opened_until}

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


def _object_dict(value: object) -> dict[str, object]:
    return dict(cast(dict[str, object], value)) if isinstance(value, dict) else {}


def _string_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _int_value(value: object, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass
    return default


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
