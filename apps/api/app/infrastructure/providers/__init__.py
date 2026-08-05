"""Provider abstraction for embedding models.

Defines the protocol all embedding providers must implement,
plus a registry with fallback chain support.
"""

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Protocol for dense embedding providers."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts. Returns list of float vectors."""
        ...

    async def health(self) -> bool:
        """Check if provider is reachable and ready."""
        ...

    @property
    def dimensions(self) -> int:
        """Return vector dimensions for this provider/model."""
        ...

    @property
    def model(self) -> str:
        """Return model identifier."""
        ...
