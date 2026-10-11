"""FastEmbed provider — local CPU-based embedding, no API key required."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

_SUPPORTED_MODELS: dict[str, int] = {
    "BAAI/bge-small-en-v1.5": 384,
    "BAAI/bge-base-en-v1.5": 768,
    "BAAI/bge-large-en-v1.5": 1024,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
}


class FastEmbedProvider:
    """Local CPU embedding via FastEmbed (by Qdrant). No API key required."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        self._model_name = model_name
        self._model: Any = None
        self._sparse_model: Any = None
        self._dims = _SUPPORTED_MODELS.get(model_name, 384)

    def _get_model(self) -> Any:
        if self._model is None:
            try:
                from fastembed import TextEmbedding
                self._model = TextEmbedding(model_name=self._model_name)
                logger.info("FastEmbed model loaded: %s", self._model_name)
            except Exception as e:
                logger.error("FastEmbed model load failed: %s", e)
                raise
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # CPU-bound ONNX inference must not block the event loop.
        model = self._get_model()
        embeddings = await asyncio.to_thread(lambda: list(model.embed(texts)))
        return [list(map(float, e)) for e in embeddings]

    def _get_sparse_model(self) -> Any:
        if self._sparse_model is None:
            try:
                from fastembed import SparseTextEmbedding
            except ImportError as e:
                raise ValueError("fastembed sparse support unavailable") from e
            self._sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_COO_1")
            logger.info("FastEmbed sparse model loaded")
        return self._sparse_model

    async def encode_sparse(self, texts: list[str]) -> list[dict[str, object]]:
        """Return sparse representations (SPLADE-style indices/values)."""
        model = self._get_sparse_model()
        sparse_list = await asyncio.to_thread(lambda: list(model.embed(texts)))
        results = []
        for sparse in sparse_list:
            results.append(
                {
                    "indices": [int(i) for i in sparse.indices],
                    "values": [float(v) for v in sparse.values],
                }
            )
        return results

    async def health(self) -> bool:
        try:
            self._get_model()
            return True
        except Exception:
            return False

    @property
    def dimensions(self) -> int:
        return self._dims

    @property
    def model(self) -> str:
        return self._model_name
