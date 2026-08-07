import asyncio
from contextlib import AsyncExitStack
from urllib.parse import urlparse

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.domain.mcp.adapter_ports import McpClientAdapter
from app.domain.mcp.entities import McpCallResult, McpToolDescriptor


class HttpMcpClient(McpClientAdapter):
    def __init__(self, url: str, headers: dict[str, str] | None = None, timeout_seconds: int = 30, allow_insecure: bool = False) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("MCP URL must include an HTTP(S) scheme and host")
        if parsed.scheme != "https" and not allow_insecure:
            raise ValueError("MCP URL must use HTTPS unless insecure transport is explicitly enabled")
        self._url = url
        self._headers = headers or {}
        self._timeout = timeout_seconds
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def connect(self) -> None:
        if self._session is not None:
            return
        stack = AsyncExitStack()
        try:
            streams = await asyncio.wait_for(stack.enter_async_context(streamablehttp_client(self._url, headers=self._headers, timeout=self._timeout, sse_read_timeout=self._timeout)), self._timeout)
            read_stream, write_stream, _ = streams
            session = await asyncio.wait_for(stack.enter_async_context(ClientSession(read_stream, write_stream)), self._timeout)
            await asyncio.wait_for(session.initialize(), self._timeout)
        except BaseException:
            await stack.aclose()
            raise
        self._stack = stack
        self._session = session

    async def list_tools(self) -> list[McpToolDescriptor]:
        if self._session is None:
            raise RuntimeError("MCP client is not connected")
        result = await asyncio.wait_for(self._session.list_tools(), self._timeout)
        return [McpToolDescriptor(name=tool.name, description=tool.description or "", input_schema=dict(tool.inputSchema)) for tool in result.tools]

    async def call_tool(self, name: str, arguments: dict[str, object]) -> McpCallResult:
        if self._session is None:
            raise RuntimeError("MCP client is not connected")
        result = await asyncio.wait_for(self._session.call_tool(name, arguments), self._timeout)
        return McpCallResult(result=result, is_error=result.isError)

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None
