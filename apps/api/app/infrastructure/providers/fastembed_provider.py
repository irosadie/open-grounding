"""FastEmbed provider — local CPU-based embedding, no API key required."""

from __future__ import annotations

import logging
from functools import lru_cache

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
        self._model = None
        self._dims = _SUPPORTED_MODELS.get(model_name, 384)

    def _get_model(self):  # type: ignore[return]
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
        model = self._get_model()
        embeddings = list(model.embed(texts))
        return [list(map(float, e)) for e in embeddings]

    async def encode_sparse(self, texts: list[str]) -> list[dict[str, object]]:
        """Return sparse representations (SPLADE-style indices/values)."""
        try:
            from fastembed import SparseTextEmbedding
        except ImportError as e:
            raise ValueError("fastembed sparse support unavailable") from e
        model = SparseTextEmbedding(model_name="prithivida/Splade_PP_COO_1")
        results = []
        for sparse in list(model.embed(texts)):
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
