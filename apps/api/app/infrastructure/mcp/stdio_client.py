import asyncio
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.domain.mcp.adapter_ports import McpClientAdapter
from app.domain.mcp.entities import McpCallResult, McpToolDescriptor


class StdioMcpClient(McpClientAdapter):
    def __init__(self, command: str, args: list[str], timeout_seconds: int = 30) -> None:
        self._parameters = StdioServerParameters(command=command, args=args)
        self._timeout = timeout_seconds
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def connect(self) -> None:
        if self._session is not None:
            return
        stack = AsyncExitStack()
        try:
            read_stream, write_stream = await asyncio.wait_for(stack.enter_async_context(stdio_client(self._parameters)), self._timeout)
            session = await asyncio.wait_for(stack.enter_async_context(ClientSession(read_stream, write_stream)), self._timeout)
            await asyncio.wait_for(session.initialize(), self._timeout)
        except BaseException:
            await stack.aclose()
            raise
        self._stack = stack
        self._session = session

    async def list_tools(self) -> list[McpToolDescriptor]:
        session = self._require_session()
        result = await asyncio.wait_for(session.list_tools(), self._timeout)
        return [McpToolDescriptor(name=tool.name, description=tool.description or "", input_schema=dict(tool.inputSchema)) for tool in result.tools]

    async def call_tool(self, name: str, arguments: dict[str, object]) -> McpCallResult:
        result = await asyncio.wait_for(self._require_session().call_tool(name, arguments), self._timeout)
        return McpCallResult(result=result, is_error=result.isError)

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("MCP client is not connected")
        return self._session
