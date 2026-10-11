"""Application service for per-KB ingestion configuration.

Handles get (with defaults fallback) and upsert of ingestion quality gate
thresholds and auto-review toggle. Validates threshold ranges before persisting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DomainError
from app.domain.rag.catalog import INGESTION_CONFIG_DEFAULTS, IngestionConfig
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag_catalog import SqlAlchemyIngestionConfigRepository, SqlAlchemyKnowledgeBaseRepository

# Sentinel for "not provided" — distinguishes from explicit None (clear key)
_UNSET: Any = object()

_ALLOWED_PARSERS = frozenset({"auto", "docling_serve", "docling_inprocess", "pdfminer"})


@dataclass(frozen=True)
class IngestionConfigResult:
    id: str | None
    knowledge_base_id: str
    min_text_coverage: float
    max_invalid_char_ratio: float
    min_aggregate_confidence: float
    min_page_coverage: float
    auto_review: bool
    parser: str
    docling_serve_url: str | None
    docling_serve_api_key_set: bool
    created_at: str | None
    updated_at: str | None
    is_default: bool


def _to_result(config: IngestionConfig, *, is_default: bool = False) -> IngestionConfigResult:
    return IngestionConfigResult(
        id=config.id or None,
        knowledge_base_id=config.knowledge_base_id,
        min_text_coverage=config.min_text_coverage,
        max_invalid_char_ratio=config.max_invalid_char_ratio,
        min_aggregate_confidence=config.min_aggregate_confidence,
        min_page_coverage=config.min_page_coverage,
        auto_review=config.auto_review,
        parser=config.parser,
        docling_serve_url=config.docling_serve_url,
        docling_serve_api_key_set=config.docling_serve_api_key_enc is not None,
        created_at=config.created_at.isoformat() if config.id else None,
        updated_at=config.updated_at.isoformat() if config.id else None,
        is_default=is_default,
    )


def _validate_parser(parser: str, docling_serve_url: str | None) -> str | None:
    if parser not in _ALLOWED_PARSERS:
        raise DomainError.validation(f"parser must be one of {sorted(_ALLOWED_PARSERS)}, got: {parser!r}")

    normalized_url = docling_serve_url.strip() if docling_serve_url is not None else None
    normalized_url = normalized_url or None
    if normalized_url is not None and len(normalized_url) > 2048:
        raise DomainError.validation("docling_serve_url must be at most 2048 characters")
    if parser == "docling_serve":
        if normalized_url is None:
            raise DomainError.validation("docling_serve_url is required when parser='docling_serve'")
        try:
            import httpx
            parsed = httpx.URL(normalized_url)
        except Exception as exc:
            raise DomainError.validation(f"docling_serve_url must be a valid URL, got: {normalized_url!r}") from exc
        if parsed.scheme not in ("http", "https"):
            raise DomainError.validation(f"docling_serve_url must use http or https, got: {parsed.scheme!r}")
        if not parsed.host:
            raise DomainError.validation(f"docling_serve_url must include a host, got: {normalized_url!r}")

    return normalized_url


def _validate_thresholds(
    min_text_coverage: float,
    max_invalid_char_ratio: float,
    min_aggregate_confidence: float,
    min_page_coverage: float,
) -> None:
    fields = {
        "min_text_coverage": min_text_coverage,
        "max_invalid_char_ratio": max_invalid_char_ratio,
        "min_aggregate_confidence": min_aggregate_confidence,
        "min_page_coverage": min_page_coverage,
    }
    for name, value in fields.items():
        if not 0.0 <= value <= 1.0:
            raise DomainError("VALIDATION_ERROR", f"{name} must be between 0.0 and 1.0", 422)


class IngestionConfigService:
    """CRUD operations for per-KB ingestion configuration."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = SqlAlchemyIngestionConfigRepository(session)
        self._kb_repo = SqlAlchemyKnowledgeBaseRepository(session)

    async def get_config(self, *, tenant: TenantContext, knowledge_base_id: str) -> IngestionConfigResult:
        kb = await self._kb_repo.find_by_id(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)
        if kb is None:
            raise DomainError.not_found("Knowledge base not found")

        config = await self._repo.get_by_kb(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)
        if config is None:
            defaults = INGESTION_CONFIG_DEFAULTS
            return _to_result(
                IngestionConfig(
                    id="",
                    tenant_id=tenant.tenant_id,
                    knowledge_base_id=knowledge_base_id,
                    min_text_coverage=defaults.min_text_coverage,
                    max_invalid_char_ratio=defaults.max_invalid_char_ratio,
                    min_aggregate_confidence=defaults.min_aggregate_confidence,
                    min_page_coverage=defaults.min_page_coverage,
                    auto_review=defaults.auto_review,
                    parser=defaults.parser,
                    docling_serve_url=defaults.docling_serve_url,
                    docling_serve_api_key_enc=defaults.docling_serve_api_key_enc,
                    created_at=defaults.created_at,
                    updated_at=defaults.updated_at,
                ),
                is_default=True,
            )
        return _to_result(config, is_default=False)

    async def upsert_config(
        self,
        *,
        tenant: TenantContext,
        knowledge_base_id: str,
        min_text_coverage: float,
        max_invalid_char_ratio: float,
        min_aggregate_confidence: float,
        min_page_coverage: float,
        auto_review: bool,
        parser: str = "auto",
        docling_serve_url: str | None = None,
        docling_serve_api_key: Any = _UNSET,
        settings: object | None = None,
    ) -> IngestionConfigResult:
        kb = await self._kb_repo.find_by_id(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)
        if kb is None:
            raise DomainError.not_found("Knowledge base not found")

        _validate_thresholds(min_text_coverage, max_invalid_char_ratio, min_aggregate_confidence, min_page_coverage)
        docling_serve_url = _validate_parser(parser, docling_serve_url)

        # Resolve encrypted API key
        if docling_serve_api_key is _UNSET:
            # Not provided — keep existing encrypted value
            existing = await self._repo.get_by_kb(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)
            api_key_enc = existing.docling_serve_api_key_enc if existing else None
        elif docling_serve_api_key is None:
            # Explicitly cleared
            api_key_enc = None
        else:
            # New key provided — encrypt it
            from app.infrastructure.crypto import encrypt, get_encryption_key

            normalized_api_key = str(docling_serve_api_key).strip()
            if not normalized_api_key:
                raise DomainError.validation("docling_serve_api_key must not be empty")
            enc_key = get_encryption_key(settings)
            api_key_enc = encrypt(normalized_api_key, enc_key)

        config = await self._repo.upsert(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
            min_text_coverage=min_text_coverage,
            max_invalid_char_ratio=max_invalid_char_ratio,
            min_aggregate_confidence=min_aggregate_confidence,
            min_page_coverage=min_page_coverage,
            auto_review=auto_review,
            parser=parser,
            docling_serve_url=docling_serve_url,
            docling_serve_api_key_enc=api_key_enc,
        )
        return _to_result(config, is_default=False)

    async def get_api_key_decrypted(
        self,
        *,
        tenant: TenantContext,
        knowledge_base_id: str,
        settings: object,
    ) -> str | None:
        """Decrypt and return the docling-serve API key for worker use only.

        MUST NOT be called from HTTP route handlers.
        """
        config = await self._repo.get_by_kb(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)
        if config is None or config.docling_serve_api_key_enc is None:
            return None
        from app.infrastructure.crypto import decrypt, get_encryption_key
        enc_key = get_encryption_key(settings)
        return decrypt(config.docling_serve_api_key_enc, enc_key)
