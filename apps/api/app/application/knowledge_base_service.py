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
from app.infrastructure.rag_projects import SqlAlchemyProjectRepository

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class KnowledgeBaseResult:
    id: str
    tenant_id: str
    slug: str
    name: str
    status: str
    project_id: str | None
    created_at: str
    updated_at: str


def _to_result(kb: KnowledgeBase) -> KnowledgeBaseResult:
    return KnowledgeBaseResult(
        id=kb.id,
        tenant_id=kb.tenant_id,
        slug=kb.slug,
        name=kb.name,
        status=str(kb.status),
        project_id=kb.project_id,
        created_at=kb.created_at.isoformat(),
        updated_at=kb.updated_at.isoformat(),
    )


class KnowledgeBaseService:
    """CRUD operations for tenant-scoped knowledge bases."""

    def __init__(self, session: AsyncSession) -> None:
        self._kb_repo = SqlAlchemyKnowledgeBaseRepository(session)
        self._project_repo = SqlAlchemyProjectRepository(session)

    async def create(
        self,
        *,
        tenant: TenantContext,
        name: str,
        slug: str,
        project_id: str | None = None,
    ) -> KnowledgeBaseResult:
        if not _SLUG_RE.match(slug):
            raise DomainError(
                "VALIDATION_ERROR",
                "Slug must be lowercase kebab-case (e.g. my-knowledge-base)",
                422,
            )
        existing = await self._kb_repo.find_by_slug(tenant_id=tenant.tenant_id, slug=slug)
        if existing is not None:
            raise DomainError(
                "CONFLICT",
                f"A knowledge base with slug '{slug}' already exists",
                409,
            )
        project = await self._project_repo.find_by_id(tenant_id=tenant.tenant_id, project_id=project_id) if project_id else await self._project_repo.find_default(tenant_id=tenant.tenant_id)
        if project is None:
            raise DomainError("PROJECT_NOT_FOUND", "An active Project is required to create a knowledge base", 422)
        if str(project.status) != "ACTIVE":
            raise DomainError("PROJECT_NOT_ACTIVE", "Knowledge base can only be created in an active Project", 422)
        kb = await self._kb_repo.create(
            tenant_id=tenant.tenant_id,
            slug=slug,
            name=name,
            status="ACTIVE",
            project_id=project.id,
        )
        return _to_result(kb)

    async def list_all(self, *, tenant: TenantContext) -> list[KnowledgeBaseResult]:
        kbs = await self._kb_repo.list_by_tenant(tenant_id=tenant.tenant_id)
        return [_to_result(kb) for kb in kbs]

    async def archive(self, *, tenant: TenantContext, knowledge_base_id: str) -> KnowledgeBaseResult:
        kb = await self._kb_repo.archive(
            tenant_id=tenant.tenant_id,
            knowledge_base_id=knowledge_base_id,
        )
        if kb is None:
            raise DomainError("NOT_FOUND", "Knowledge base not found", 404)
        return _to_result(kb)
