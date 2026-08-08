"""Application service for per-KB ingestion configuration.

Handles get (with defaults fallback) and upsert of ingestion quality gate
thresholds and auto-review toggle. Validates threshold ranges before persisting.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DomainError
from app.domain.rag.catalog import INGESTION_CONFIG_DEFAULTS, IngestionConfig
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag_catalog import SqlAlchemyIngestionConfigRepository, SqlAlchemyKnowledgeBaseRepository


@dataclass(frozen=True)
class IngestionConfigResult:
    id: str | None
    knowledge_base_id: str
    min_text_coverage: float
    max_invalid_char_ratio: float
    min_aggregate_confidence: float
    min_page_coverage: float
    auto_review: bool
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
        created_at=config.created_at.isoformat() if config.id else None,
        updated_at=config.updated_at.isoformat() if config.id else None,
        is_default=is_default,
    )


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
    ) -> IngestionConfigResult:
        kb = await self._kb_repo.find_by_id(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)
        if kb is None:
            raise DomainError.not_found("Knowledge base not found")

        _validate_thresholds(min_text_coverage, max_invalid_char_ratio, min_aggregate_confidence, min_page_coverage)

        config = await self._repo.upsert(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
            min_text_coverage=min_text_coverage,
            max_invalid_char_ratio=max_invalid_char_ratio,
            min_aggregate_confidence=min_aggregate_confidence,
            min_page_coverage=min_page_coverage,
            auto_review=auto_review,
        )
        return _to_result(config, is_default=False)
