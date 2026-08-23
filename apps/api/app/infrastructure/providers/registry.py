"""Provider registry — builds and caches embedding providers from settings.

Supports DB-first credential lookup with env var fallback.
Supports fallback chain: if primary provider fails, tries next in chain.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.settings import Settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def get_provider_api_key(
    provider: str,
    key_name: str,
    tenant_id: str,
    session: "AsyncSession | None",
    settings: Settings,
) -> str | None:
    """Get credential: DB-first, env fallback."""
    # 1. Try DB
    if session is not None and tenant_id:
        try:
            from app.application.provider_credential_service import ProviderCredentialService
            svc = ProviderCredentialService(session, settings)
            value = await svc.get_decrypted(
                tenant_id=tenant_id,
                provider=provider,
                key_name=key_name,
            )
            if value:
                return value
        except Exception as e:
            logger.warning("DB credential lookup failed for %s/%s: %s", provider, key_name, e)

    # 2. Env fallback
    if provider == "openai" and key_name == "api_key":
        return getattr(settings, "openai_api_key", None) or None
    if provider == "ollama" and key_name == "base_url":
        return getattr(settings, "ollama_base_url", None) or "http://localhost:11434"
    if provider == "huggingface" and key_name == "token":
        return None  # no env fallback for HF token

    return None


def build_embedding_provider(
    provider: str,
    model: str,
    settings: Settings,
    api_key: str | None = None,
    base_url: str | None = None,
):  # type: ignore[return]
    """Build an embedding provider instance."""
    if provider == "fastembed":
        from app.infrastructure.providers.fastembed_provider import FastEmbedProvider
        return FastEmbedProvider(model_name=model)
    elif provider == "openai":
        from app.infrastructure.providers.openai_provider import OpenAIEmbeddingProvider
        return OpenAIEmbeddingProvider(
            model_name=model,
            api_key=api_key or getattr(settings, "openai_api_key", None),
        )
    elif provider == "ollama":
        from app.infrastructure.providers.ollama_provider import OllamaEmbeddingProvider
        url = base_url or getattr(settings, "ollama_base_url", "http://localhost:11434") or "http://localhost:11434"
        return OllamaEmbeddingProvider(model_name=model, base_url=url)
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")


class ProviderRegistry:
    """Registry of embedding providers with DB-first credentials and fallback chain."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: dict[str, object] = {}

    def get_embedding_provider(self, provider: str, model: str, api_key: str | None = None):  # type: ignore[return]
        """Get or build a cached embedding provider (sync, uses env only)."""
        key = f"{provider}:{model}"
        if key not in self._cache:
            self._cache[key] = build_embedding_provider(provider, model, self._settings, api_key=api_key)
        return self._cache[key]

    async def get_embedding_provider_async(
        self,
        provider: str,
        model: str,
        tenant_id: str,
        session: "AsyncSession | None" = None,
    ):  # type: ignore[return]
        """Build provider with DB-first credential lookup."""
        key_name = "api_key" if provider == "openai" else "base_url" if provider == "ollama" else None
        api_key = None
        base_url = None

        if key_name:
            value = await get_provider_api_key(
                provider=provider,
                key_name=key_name,
                tenant_id=tenant_id,
                session=session,
                settings=self._settings,
            )
            if provider == "openai":
                api_key = value
            elif provider == "ollama":
                base_url = value

        return build_embedding_provider(provider, model, self._settings, api_key=api_key, base_url=base_url)

    async def embed_with_fallback(
        self,
        texts: list[str],
        primary_provider: str,
        primary_model: str,
        tenant_id: str = "",
        session: "AsyncSession | None" = None,
        fallback_providers: list[tuple[str, str]] | None = None,
    ) -> list[list[float]]:
        """Embed texts with DB-first credentials and automatic fallback chain."""
        chain = [(primary_provider, primary_model)] + (fallback_providers or [])
        last_error: Exception | None = None

        for provider_name, model_name in chain:
            try:
                provider = await self.get_embedding_provider_async(
                    provider_name, model_name, tenant_id=tenant_id, session=session
                )
                return await provider.embed(texts)  # type: ignore[union-attr]
            except Exception as e:
                logger.warning("Embedding provider %s/%s failed: %s — trying fallback", provider_name, model_name, e)
                last_error = e

        raise RuntimeError(f"All embedding providers failed. Last error: {last_error}")
