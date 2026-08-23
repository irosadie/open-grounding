from dataclasses import dataclass
from datetime import datetime

from app.domain.mcp.enums import McpInvocationStatus, McpServerStatus, McpTransport


@dataclass(frozen=True)
class McpServer:
    id: str
    tenant_id: str
    name: str
    transport: McpTransport
    command: str | None
    args: list[str]
    url: str | None
    auth_type: str | None
    credential_ref: str | None
    headers_json: dict[str, object]
    timeout_seconds: int
    max_payload_bytes: int
    allow_insecure: bool
    enabled: bool
    status: McpServerStatus
    last_error: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class McpTool:
    id: str
    tenant_id: str
    server_id: str
    name: str
    description: str
    input_schema: dict[str, object]
    allowed: bool
    is_stale: bool
    last_discovered_at: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class McpInvocation:
    id: str
    tenant_id: str
    server_id: str
    tool_id: str
    user_id: str
    args_json: dict[str, object]
    args_hash: str
    status: McpInvocationStatus
    result_text: str | None
    duration_ms: int
    created_at: datetime


@dataclass(frozen=True)
class McpToolDescriptor:
    name: str
    description: str
    input_schema: dict[str, object]


@dataclass(frozen=True)
class McpCallResult:
    result: object
    is_error: bool = False
