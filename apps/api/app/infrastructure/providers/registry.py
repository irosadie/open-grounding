"""Provider registry — builds and caches embedding providers from settings.

Supports fallback chain: if primary provider fails, tries next in chain.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from app.core.settings import Settings

logger = logging.getLogger(__name__)


def build_embedding_provider(provider: str, model: str, settings: Settings):  # type: ignore[return]
    """Build an embedding provider instance from provider name + model."""
    if provider == "fastembed":
        from app.infrastructure.providers.fastembed_provider import FastEmbedProvider
        return FastEmbedProvider(model_name=model)
    elif provider == "openai":
        from app.infrastructure.providers.openai_provider import OpenAIEmbeddingProvider
        return OpenAIEmbeddingProvider(
            model_name=model,
            api_key=getattr(settings, "openai_api_key", None),
        )
    elif provider == "ollama":
        from app.infrastructure.providers.ollama_provider import OllamaEmbeddingProvider
        base_url = getattr(settings, "ollama_base_url", "http://localhost:11434") or "http://localhost:11434"
        return OllamaEmbeddingProvider(model_name=model, base_url=base_url)
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")


class ProviderRegistry:
    """Registry of embedding providers with fallback chain support."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: dict[str, object] = {}

    def get_embedding_provider(self, provider: str, model: str):  # type: ignore[return]
        """Get or build a cached embedding provider."""
        key = f"{provider}:{model}"
        if key not in self._cache:
            self._cache[key] = build_embedding_provider(provider, model, self._settings)
        return self._cache[key]

    async def embed_with_fallback(
        self,
        texts: list[str],
        primary_provider: str,
        primary_model: str,
        fallback_providers: list[tuple[str, str]] | None = None,
    ) -> list[list[float]]:
        """Embed texts with automatic fallback chain on failure."""
        chain = [(primary_provider, primary_model)] + (fallback_providers or [])
        last_error: Exception | None = None

        for provider_name, model_name in chain:
            try:
                provider = self.get_embedding_provider(provider_name, model_name)
                return await provider.embed(texts)  # type: ignore[union-attr]
            except Exception as e:
                logger.warning("Embedding provider %s/%s failed: %s — trying fallback", provider_name, model_name, e)
                last_error = e

        raise RuntimeError(f"All embedding providers failed. Last error: {last_error}")
