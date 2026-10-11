"""Ollama embedding provider — self-hosted local LLM endpoint."""

from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

_EMBED_CONCURRENCY = 4


class OllamaEmbeddingProvider:
    """Ollama embedding provider. Requires OLLAMA_BASE_URL env var."""

    def __init__(self, model_name: str = "nomic-embed-text", base_url: str = "http://localhost:11434") -> None:
        self._model_name = model_name
        self._base_url = base_url.rstrip("/")
        self._dims = 768  # default for nomic-embed-text

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Bounded parallel batch: latency ~= slowest item, not sum.
        # One shared client. Failure semantics preserved: any item error
        # still fails the batch (same as the old serial loop).
        semaphore = asyncio.Semaphore(_EMBED_CONCURRENCY)

        async def _embed_one(client: httpx.AsyncClient, text: str) -> list[float]:
            async with semaphore:
                response = await client.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": self._model_name, "prompt": text},
                )
                response.raise_for_status()
                data = response.json()
                embedding = data["embedding"]
                return [float(v) for v in embedding]

        async with httpx.AsyncClient(timeout=30) as client:
            return list(await asyncio.gather(*(_embed_one(client, text) for text in texts)))

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    @property
    def dimensions(self) -> int:
        return self._dims

    @property
    def model(self) -> str:
        return self._model_name
