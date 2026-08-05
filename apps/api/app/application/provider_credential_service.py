"""Application service for provider credential management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.tenant_context import TenantContext
from app.infrastructure.crypto import decrypt, encrypt, get_encryption_key
from app.infrastructure.rag_catalog import SqlAlchemyProviderCredentialRepository

SUPPORTED_PROVIDERS = {
    "openai": ["api_key"],
    "ollama": ["base_url"],
    "huggingface": ["token"],
    "fastembed": [],  # no credentials needed
}


@dataclass(frozen=True)
class ProviderCredentialStatus:
    provider: str
    key_name: str
    is_configured: bool
    updated_at: str | None


class ProviderCredentialService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._repo = SqlAlchemyProviderCredentialRepository(session)
        self._settings = settings

    async def set_credential(
        self,
        *,
        tenant: TenantContext,
        provider: str,
        key_name: str,
        value: str,
    ) -> ProviderCredentialStatus:
        if not value.strip():
            raise DomainError("VALIDATION_ERROR", "Credential value cannot be empty.", 422)
        if provider not in SUPPORTED_PROVIDERS:
            raise DomainError("VALIDATION_ERROR", f"Unsupported provider: {provider}", 422)
        enc_key = get_encryption_key(self._settings)
        value_enc = encrypt(value.strip(), enc_key)
        row = await self._repo.set_credential(
            tenant_id=tenant.tenant_id,
            provider=provider,
            key_name=key_name,
            value_enc=value_enc,
        )
        return ProviderCredentialStatus(
            provider=provider,
            key_name=key_name,
            is_configured=True,
            updated_at=row.updated_at.isoformat(),
        )

    async def list_status(self, *, tenant: TenantContext) -> list[ProviderCredentialStatus]:
        rows = await self._repo.list_by_tenant(tenant_id=tenant.tenant_id)
        configured = {(r.provider, r.key_name): r for r in rows if r.is_active and r.value_enc}

        statuses = []
        for provider, keys in SUPPORTED_PROVIDERS.items():
            for key_name in keys:
                row = configured.get((provider, key_name))
                statuses.append(ProviderCredentialStatus(
                    provider=provider,
                    key_name=key_name,
                    is_configured=row is not None,
                    updated_at=row.updated_at.isoformat() if row else None,
                ))
        return statuses

    async def get_decrypted(
        self,
        *,
        tenant_id: str,
        provider: str,
        key_name: str,
    ) -> str | None:
        """Get decrypted credential value. For internal use only — never expose to client."""
        row = await self._repo.find_credential(
            tenant_id=tenant_id,
            provider=provider,
            key_name=key_name,
        )
        if row is None or not row.value_enc:
            return None
        enc_key = get_encryption_key(self._settings)
        try:
            return decrypt(row.value_enc, enc_key)
        except Exception:
            return None

    async def revoke(
        self,
        *,
        tenant: TenantContext,
        provider: str,
        key_name: str,
    ) -> ProviderCredentialStatus:
        revoked = await self._repo.revoke(
            tenant_id=tenant.tenant_id,
            provider=provider,
            key_name=key_name,
        )
        if not revoked:
            raise DomainError("NOT_FOUND", "Credential not found.", 404)
        return ProviderCredentialStatus(
            provider=provider,
            key_name=key_name,
            is_configured=False,
            updated_at=None,
        )
