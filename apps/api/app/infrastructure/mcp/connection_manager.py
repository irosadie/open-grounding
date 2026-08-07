import asyncio
from collections.abc import Callable

from app.domain.mcp.adapter_ports import McpClientAdapter

ClientFactory = Callable[[], McpClientAdapter]


class McpConnectionManager:
    def __init__(self, *, max_retries: int = 3, base_backoff_seconds: float = 0.25) -> None:
        self._connections: dict[tuple[str, str, str], McpClientAdapter] = {}
        self._locks: dict[tuple[str, str, str], asyncio.Lock] = {}
        self._max_retries = max_retries
        self._base_backoff = base_backoff_seconds

    async def get_or_connect(self, key: tuple[str, str, str], factory: ClientFactory) -> McpClientAdapter:
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            existing = self._connections.get(key)
            if existing is not None:
                return existing
            last_error: BaseException | None = None
            for attempt in range(self._max_retries + 1):
                client = factory()
                try:
                    await client.connect()
                    self._connections[key] = client
                    return client
                except BaseException as error:
                    last_error = error
                    await client.close()
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._base_backoff * (2**attempt))
            assert last_error is not None
            raise last_error

    async def close(self, key: tuple[str, str, str]) -> None:
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            client = self._connections.pop(key, None)
            if client is not None:
                await client.close()

    async def close_all(self) -> None:
        for key in list(self._connections):
            await self.close(key)

    def lock_for(self, key: tuple[str, str, str]) -> asyncio.Lock:
        return self._locks.setdefault(key, asyncio.Lock())
