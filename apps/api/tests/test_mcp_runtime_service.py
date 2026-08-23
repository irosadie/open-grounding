import asyncio
import socket
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.application.mcp_runtime_service import McpRuntimeService
from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.mcp.entities import McpInvocation, McpServer, McpTool, McpToolDescriptor
from app.domain.mcp.enums import McpInvocationStatus, McpServerStatus
from app.domain.models import UserRole
from app.domain.tenant_context import TenantContext
from app.infrastructure.mcp.connection_manager import McpConnectionManager

SERVER_SCRIPT = Path(__file__).with_name("mcp_test_server.py")


class InMemoryServers:
    def __init__(self) -> None:
        self.rows: dict[str, McpServer] = {}

    async def create(self, **values: object) -> McpServer:
        now = datetime.now(UTC).replace(tzinfo=None)
        server = McpServer(
            id=str(uuid4()),
            status=McpServerStatus.UNKNOWN,
            last_error=None,
            created_at=now,
            updated_at=now,
            **values,  # type: ignore[arg-type]
        )
        self.rows[server.id] = server
        return server

    async def find_by_id(self, *, tenant_id: str, server_id: str) -> McpServer | None:
        server = self.rows.get(server_id)
        return server if server and server.tenant_id == tenant_id else None

    async def list(self, *, tenant_id: str) -> list[McpServer]:
        return [server for server in self.rows.values() if server.tenant_id == tenant_id]

    async def update(self, *, tenant_id: str, server_id: str, **changes: object) -> McpServer | None:
        server = await self.find_by_id(tenant_id=tenant_id, server_id=server_id)
        if server is None:
            return None
        updated = replace(server, updated_at=datetime.now(UTC).replace(tzinfo=None), **changes)
        self.rows[server_id] = updated
        return updated

    async def delete(self, *, tenant_id: str, server_id: str) -> bool:
        if await self.find_by_id(tenant_id=tenant_id, server_id=server_id) is None:
            return False
        del self.rows[server_id]
        return True


class InMemoryTools:
    def __init__(self) -> None:
        self.rows: dict[str, McpTool] = {}

    async def upsert_discovered(self, *, tenant_id: str, server_id: str, tools: list[McpToolDescriptor], discovered_at: datetime) -> list[McpTool]:
        discovered: list[McpTool] = []
        names = {tool.name for tool in tools}
        for tool_id, tool in list(self.rows.items()):
            if tool.tenant_id == tenant_id and tool.server_id == server_id:
                self.rows[tool_id] = replace(tool, is_stale=tool.name not in names, updated_at=discovered_at)
        for descriptor in tools:
            existing = next((tool for tool in self.rows.values() if tool.tenant_id == tenant_id and tool.server_id == server_id and tool.name == descriptor.name), None)
            if existing:
                tool = replace(existing, description=descriptor.description, input_schema=descriptor.input_schema, is_stale=False, last_discovered_at=discovered_at, updated_at=discovered_at)
            else:
                tool = McpTool(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    server_id=server_id,
                    name=descriptor.name,
                    description=descriptor.description,
                    input_schema=descriptor.input_schema,
                    allowed=False,
                    is_stale=False,
                    last_discovered_at=discovered_at,
                    created_at=discovered_at,
                    updated_at=discovered_at,
                )
            self.rows[tool.id] = tool
            discovered.append(tool)
        return discovered

    async def list(self, *, tenant_id: str, server_id: str, include_stale: bool = False) -> list[McpTool]:
        return [tool for tool in self.rows.values() if tool.tenant_id == tenant_id and tool.server_id == server_id and (include_stale or not tool.is_stale)]

    async def find_by_id(self, *, tenant_id: str, tool_id: str) -> McpTool | None:
        tool = self.rows.get(tool_id)
        return tool if tool and tool.tenant_id == tenant_id else None

    async def set_allowed(self, *, tenant_id: str, tool_id: str, allowed: bool) -> McpTool | None:
        tool = await self.find_by_id(tenant_id=tenant_id, tool_id=tool_id)
        if tool is None:
            return None
        updated = replace(tool, allowed=allowed, updated_at=datetime.now(UTC).replace(tzinfo=None))
        self.rows[tool_id] = updated
        return updated


class InMemoryInvocations:
    def __init__(self) -> None:
        self.rows: list[McpInvocation] = []

    async def create(self, **values: object) -> McpInvocation:
        invocation = McpInvocation(id=str(uuid4()), created_at=datetime.now(UTC).replace(tzinfo=None), **values)  # type: ignore[arg-type]
        self.rows.append(invocation)
        return invocation

    async def list(self, *, tenant_id: str, **filters: object) -> list[McpInvocation]:
        return [row for row in self.rows if row.tenant_id == tenant_id]

    async def prune(self, *, tenant_id: str, before: datetime) -> int:
        return 0


class CredentialsStub:
    async def set_credential(self, **_: object) -> None:
        return None

    async def get_decrypted(self, **_: object) -> str | None:
        return None

    async def revoke(self, **_: object) -> None:
        return None


def _tenant() -> TenantContext:
    return TenantContext(tenant_id="tenant-1", membership_id="membership-1", user_id="user-1", role=UserRole.ADMIN)


def _service() -> tuple[McpRuntimeService, InMemoryTools, InMemoryInvocations, McpConnectionManager]:
    connections = McpConnectionManager(max_retries=0)
    tools = InMemoryTools()
    invocations = InMemoryInvocations()
    return McpRuntimeService(Settings(_env_file=None), InMemoryServers(), tools, invocations, CredentialsStub(), connections), tools, invocations, connections  # type: ignore[arg-type]


async def _wait_for_port(port: int) -> None:
    for _ in range(50):
        try:
            _, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.close()
            await writer.wait_closed()
            return
        except OSError:
            await asyncio.sleep(0.1)
    raise TimeoutError(f"FastMCP test server did not open port {port}")


async def _stop(process: asyncio.subprocess.Process | None) -> None:
    if process is not None and process.returncode is None:
        process.terminate()
        await process.wait()


@pytest.mark.asyncio
async def test_stdio_register_discover_allow_invoke_and_audit() -> None:
    service, tools, invocations, connections = _service()
    try:
        registered = await service.register_server(tenant=_tenant(), name="stdio", transport="stdio", command=sys.executable, args=[str(SERVER_SCRIPT)])
        discovered = await service.discover_tools(tenant=_tenant(), server_id=registered["id"])
        assert discovered[0]["name"] == "echo"
        allowed = await service.set_tool_allowed(tenant=_tenant(), tool_id=discovered[0]["id"], allowed=True)
        assert allowed["allowed"] is True
        result = await service.invoke_tool(tenant=_tenant(), tool_id=discovered[0]["id"], arguments={"message": "hello"})
        assert "echo:hello" in str(result["result"])
        assert invocations.rows[-1].status is McpInvocationStatus.SUCCESS
        assert invocations.rows[-1].args_json == {}
        assert len(tools.rows) == 1
    finally:
        await connections.close_all()


@pytest.mark.asyncio
async def test_http_register_test_connection_and_invoke() -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = await asyncio.create_subprocess_exec(sys.executable, str(SERVER_SCRIPT), "http", str(port))
    service, _, invocations, connections = _service()
    try:
        await _wait_for_port(port)
        registered = await service.register_server(tenant=_tenant(), name="http", transport="http", url=f"http://127.0.0.1:{port}/mcp", allow_insecure=True)
        connection = await service.test_connection(tenant=_tenant(), server_id=registered["id"])
        assert connection["status"] == "connected"
        assert connection["toolCount"] == 1
        discovered = await service.discover_tools(tenant=_tenant(), server_id=registered["id"])
        await service.set_tool_allowed(tenant=_tenant(), tool_id=discovered[0]["id"], allowed=True)
        result = await service.invoke_tool(tenant=_tenant(), tool_id=discovered[0]["id"], arguments={"message": "local"})
        assert "echo:local" in str(result["result"])
        assert invocations.rows[-1].status is McpInvocationStatus.SUCCESS
    finally:
        await connections.close_all()
        await _stop(process)


@pytest.mark.asyncio
async def test_denied_tool_is_audited() -> None:
    service, _, invocations, connections = _service()
    try:
        registered = await service.register_server(tenant=_tenant(), name="stdio", transport="stdio", command=sys.executable, args=[str(SERVER_SCRIPT)])
        discovered = await service.discover_tools(tenant=_tenant(), server_id=registered["id"])
        with pytest.raises(DomainError, match="MCP tool is not allowed") as error:
            await service.invoke_tool(tenant=_tenant(), tool_id=discovered[0]["id"], arguments={"message": "secret"})
        assert error.value.code == "TOOL_DENIED"
        assert invocations.rows[-1].status is McpInvocationStatus.DENIED
        assert invocations.rows[-1].args_json == {}
    finally:
        await connections.close_all()
