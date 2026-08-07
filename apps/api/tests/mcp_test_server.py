"""Local FastMCP server used by MCP runtime integration tests."""

from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

server = FastMCP("runtime-e2e")


@server.tool()
def echo(message: str) -> str:
    """Return the supplied message."""
    return f"echo:{message}"


if __name__ == "__main__":
    transport = "streamable-http" if len(sys.argv) > 1 and sys.argv[1] == "http" else "stdio"
    if transport == "streamable-http":
        server.settings.port = int(sys.argv[2])
    server.run(transport=transport)
