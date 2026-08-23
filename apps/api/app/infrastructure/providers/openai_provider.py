"""OpenAI embedding provider."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_MODEL_DIMS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class OpenAIEmbeddingProvider:
    """OpenAI embedding provider. Requires OPENAI_API_KEY env var."""

    def __init__(self, model_name: str = "text-embedding-3-small", api_key: str | None = None) -> None:
        self._model_name = model_name
        self._api_key = api_key
        self._dims = _MODEL_DIMS.get(model_name, 1536)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self._api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self._api_key)
        response = await client.embeddings.create(model=self._model_name, input=texts)
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
