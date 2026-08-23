"""Application service for knowledge base management.

Handles create, list, and soft-delete (archive) of tenant-scoped knowledge
bases. Does not touch document ingestion or retrieval pipeline.
"""

import re
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DomainError
from app.domain.rag.catalog import KnowledgeBase
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag_catalog import SqlAlchemyKnowledgeBaseRepository

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class KnowledgeBaseResult:
    id: str
    tenant_id: str
    slug: str
    name: str
    status: str
    created_at: str
    updated_at: str


def _to_result(kb: KnowledgeBase) -> KnowledgeBaseResult:
    return KnowledgeBaseResult(
        id=kb.id,
        tenant_id=kb.tenant_id,
        slug=kb.slug,
        name=kb.name,
        status=str(kb.status),
        created_at=kb.created_at.isoformat(),
        updated_at=kb.updated_at.isoformat(),
    )


class KnowledgeBaseService:
    """CRUD operations for tenant-scoped knowledge bases."""

    def __init__(self, session: AsyncSession) -> None:
        self._kb_repo = SqlAlchemyKnowledgeBaseRepository(session)

    async def create(
        self,
        *,
        tenant: TenantContext,
        name: str,
        slug: str,
    ) -> KnowledgeBaseResult:
        if not _SLUG_RE.match(slug):
            raise DomainError(
                "VALIDATION_ERROR",
                "Slug must be lowercase kebab-case (e.g. my-knowledge-base)",
                422,
            )
        existing = await self._kb_repo.find_by_slug(
            tenant_id=tenant.tenant_id, slug=slug
        )
        if existing is not None:
            raise DomainError(
                "CONFLICT",
                f"A knowledge base with slug '{slug}' already exists",
                409,
            )
        kb = await self._kb_repo.create(
            tenant_id=tenant.tenant_id,
            slug=slug,
            name=name,
            status="ACTIVE",
        )
        return _to_result(kb)

    async def list_all(self, *, tenant: TenantContext) -> list[KnowledgeBaseResult]:
        kbs = await self._kb_repo.list_by_tenant(tenant_id=tenant.tenant_id)
        return [_to_result(kb) for kb in kbs]

    async def archive(
        self, *, tenant: TenantContext, knowledge_base_id: str
    ) -> KnowledgeBaseResult:
        kb = await self._kb_repo.archive(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
        )
        if kb is None:
            raise DomainError("NOT_FOUND", "Knowledge base not found", 404)
        return _to_result(kb)
