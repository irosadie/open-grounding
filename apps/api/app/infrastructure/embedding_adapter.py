"""Concrete embedding + sparse-encoding adapters.

Resolve the model profile via ``provider_resolver`` and delegate to
``ProviderRegistry`` for the actual provider call with resolved credentials.
Both implement the domain ports in ``adapter_ports.py``.
"""

from __future__ import annotations

import asyncio
import random
from typing import cast

from app.core.settings import Settings
from app.domain.rag.adapter_ports import EmbeddingAdapter, SparseEncoderAdapter
from app.domain.tenant_context import TenantContext

_EMBED_TIMEOUT_S = 10.0
_RETRY_JITTER_S = 0.25


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
    status = getattr(exc, "status_code", None)
    if status in (408, 409, 425, 429):
        return True
    if isinstance(status, int) and 500 <= status <= 599:
        return True
    name = type(exc).__name__
    return name in {"APITimeoutError", "APIConnectionError", "RateLimitError", "InternalServerError"}


class ProviderEmbeddingAdapter(EmbeddingAdapter):
    """Embeds texts via the active model profile using ProviderRegistry."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def embed(self, *, tenant: TenantContext, texts: list[str], model_profile_id: str) -> list[list[float]]:
        from app.application.provider_resolver import resolve_model_profile
        from app.infrastructure.providers.registry import build_embedding_provider

        resolved = await resolve_model_profile(
            tenant_id=tenant.tenant_id, profile_id=model_profile_id, settings=self._settings
        )
        provider = build_embedding_provider(
            resolved.provider_name,
            resolved.model,
            self._settings,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
        )
        try:
            return cast(
                list[list[float]],
                await asyncio.wait_for(provider.embed(texts), timeout=_EMBED_TIMEOUT_S),
            )
        except Exception as exc:
            if not _is_retryable(exc):
                raise
            await asyncio.sleep(random.uniform(0, _RETRY_JITTER_S))
            return cast(
                list[list[float]],
                await asyncio.wait_for(provider.embed(texts), timeout=_EMBED_TIMEOUT_S),
            )


class ProfileSparseEncoderAdapter(SparseEncoderAdapter):
    """Encodes texts into sparse representations via a sparse model profile."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def encode(self, *, tenant: TenantContext, texts: list[str], sparse_profile_id: str) -> list[dict[str, object]]:
        from app.application.provider_resolver import resolve_model_profile
        from app.infrastructure.providers.registry import build_embedding_provider

        resolved = await resolve_model_profile(
            tenant_id=tenant.tenant_id, profile_id=sparse_profile_id, settings=self._settings
        )
        provider = build_embedding_provider(
            resolved.provider_name,
            resolved.model,
            self._settings,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
        )
        encode_sparse = getattr(provider, "encode_sparse", None)
        if encode_sparse is None:
            raise ValueError(f"Provider {resolved.provider_name} does not support sparse encoding")
        try:
            return cast(
                list[dict[str, object]],
                await asyncio.wait_for(encode_sparse(texts), timeout=_EMBED_TIMEOUT_S),
            )
        except Exception as exc:
            if not _is_retryable(exc):
                raise
            await asyncio.sleep(random.uniform(0, _RETRY_JITTER_S))
            return cast(
                list[dict[str, object]],
                await asyncio.wait_for(encode_sparse(texts), timeout=_EMBED_TIMEOUT_S),
            )
