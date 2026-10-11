"""OpenAI embedding provider."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

logger = logging.getLogger(__name__)

_MODEL_DIMS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

_EMBED_TIMEOUT_S = 10.0
_RETRY_JITTER_S = 0.25

# Shared AsyncOpenAI clients keyed by api_key. Clients hold no tenant data
# or embedding results — only HTTP pool + credentials — so reuse is safe.
# Keyed per api_key to avoid leaking credentials across different keys.
# Entry is (client, client_cls) so patched test doubles are not reused.
_shared_clients: dict[str, tuple[Any, Any]] = {}


def _get_shared_client(api_key: str) -> Any:
    from openai import AsyncOpenAI as current_cls

    entry = _shared_clients.get(api_key)
    if entry is not None:
        client, cls = entry
        if cls is current_cls:
            return client
    client = current_cls(api_key=api_key, timeout=_EMBED_TIMEOUT_S, max_retries=0)
    _shared_clients[api_key] = (client, current_cls)
    return client


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, ValueError):
        return False
    if isinstance(exc, asyncio.CancelledError):
        return False
    try:
        import httpx

        if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)):
            return True
    except ImportError:
        pass
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    name = type(exc).__name__
    if name in {
        "APITimeoutError",
        "APIConnectionError",
        "RateLimitError",
        "InternalServerError",
        "ServiceUnavailableError",
    }:
        return True
    status = getattr(exc, "status_code", None)
    if status in (408, 409, 425, 429):
        return True
    if isinstance(status, int) and 500 <= status <= 599:
        return True
    return False


class OpenAIEmbeddingProvider:
    """OpenAI embedding provider. Requires OPENAI_API_KEY env var."""

    def __init__(self, model_name: str = "text-embedding-3-small", api_key: str | None = None) -> None:
        self._model_name = model_name
        self._api_key = api_key
        self._dims = _MODEL_DIMS.get(model_name, 1536)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self._api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        client = _get_shared_client(self._api_key)
        try:
            response = await asyncio.wait_for(
                client.embeddings.create(model=self._model_name, input=texts),
                timeout=_EMBED_TIMEOUT_S,
            )
        except Exception as exc:
            if not _is_retryable(exc):
                raise
            logger.debug("OpenAI embed transient failure (%s); retrying once", type(exc).__name__)
            await asyncio.sleep(random.uniform(0, _RETRY_JITTER_S))
            response = await asyncio.wait_for(
                client.embeddings.create(model=self._model_name, input=texts),
                timeout=_EMBED_TIMEOUT_S,
            )
        return [item.embedding for item in response.data]

    async def health(self) -> bool:
        if not self._api_key:
            return False
        try:
            await self.embed(["health check"])
            return True
        except Exception:
            return False

    @property
    def dimensions(self) -> int:
        return self._dims

    @property
    def model(self) -> str:
        return self._model_name
