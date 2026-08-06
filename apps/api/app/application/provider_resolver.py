"""Resolve model profiles and provider credentials for runtime adapters.

Opens a short-lived DB session to load the profile and its credential, then
returns a plain descriptor so the caller can embed/generate without holding
the session open. This avoids leaking session lifecycle across the adapter.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.settings import Settings


@dataclass(frozen=True)
class ResolvedProvider:
    provider_name: str
    model: str
    api_key: str | None
    base_url: str | None


async def resolve_model_profile(
    *,
    tenant_id: str,
    profile_id: str,
    settings: Settings,
) -> ResolvedProvider:
    from app.infrastructure.database import create_session_factory
    from app.infrastructure.providers.registry import get_provider_api_key
    from app.infrastructure.rag_catalog import SqlAlchemyModelProfileRepository

    session_factory = create_session_factory(settings)
    async with session_factory() as session:
        repo = SqlAlchemyModelProfileRepository(session)
        profile = await repo.find_by_id(tenant_id=tenant_id, profile_id=profile_id)
        if profile is None:
            raise ValueError(f"Model profile {profile_id} not found")

        api_key: str | None = None
        base_url: str | None = None
        key_name = "api_key" if profile.provider == "openai" else "base_url" if profile.provider == "ollama" else None
        if key_name is not None:
            value = await get_provider_api_key(
                provider=profile.provider, key_name=key_name, tenant_id=tenant_id, session=session, settings=settings
            )
            if profile.provider == "openai":
                api_key = value
            elif profile.provider == "ollama":
                base_url = value or getattr(settings, "ollama_base_url", "http://localhost:11434")

        return ResolvedProvider(provider_name=profile.provider, model=profile.model, api_key=api_key, base_url=base_url)
