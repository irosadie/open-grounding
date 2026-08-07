from enum import StrEnum


class McpTransport(StrEnum):
    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


class McpServerStatus(StrEnum):
    UNKNOWN = "unknown"
    CONNECTED = "connected"
    ERROR = "error"


class McpInvocationStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    DENIED = "denied"
