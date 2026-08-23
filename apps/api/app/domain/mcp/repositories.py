from datetime import datetime
from typing import Protocol

from app.domain.mcp.entities import McpInvocation, McpServer, McpTool, McpToolDescriptor
from app.domain.mcp.enums import McpInvocationStatus, McpTransport


class McpServerRepository(Protocol):
    async def create(
        self,
        *,
        tenant_id: str,
        name: str,
        transport: McpTransport,
        command: str | None,
        args: list[str],
        url: str | None,
        auth_type: str | None,
        credential_ref: str | None,
        headers_json: dict[str, object],
        timeout_seconds: int,
        max_payload_bytes: int,
        allow_insecure: bool,
        enabled: bool,
    ) -> McpServer: ...
    async def find_by_id(self, *, tenant_id: str, server_id: str) -> McpServer | None: ...
    async def list(self, *, tenant_id: str) -> list[McpServer]: ...
    async def update(self, *, tenant_id: str, server_id: str, **changes: object) -> McpServer | None: ...
    async def delete(self, *, tenant_id: str, server_id: str) -> bool: ...


class McpToolRepository(Protocol):
    async def upsert_discovered(
        self,
        *,
        tenant_id: str,
        server_id: str,
        tools: list[McpToolDescriptor],
        discovered_at: datetime,
    ) -> list[McpTool]: ...
    async def list(self, *, tenant_id: str, server_id: str, include_stale: bool = False) -> list[McpTool]: ...
    async def find_by_id(self, *, tenant_id: str, tool_id: str) -> McpTool | None: ...
    async def set_allowed(self, *, tenant_id: str, tool_id: str, allowed: bool) -> McpTool | None: ...


class McpInvocationRepository(Protocol):
    async def create(
        self,
        *,
        tenant_id: str,
        server_id: str,
        tool_id: str,
        user_id: str,
        args_json: dict[str, object],
        args_hash: str,
        status: McpInvocationStatus,
        result_text: str | None,
        duration_ms: int,
    ) -> McpInvocation: ...
    async def list(
        self,
        *,
        tenant_id: str,
        server_id: str | None = None,
        status: McpInvocationStatus | None = None,
        user_id: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        limit: int = 100,
    ) -> list[McpInvocation]: ...
    async def prune(self, *, tenant_id: str, before: datetime) -> int: ...
