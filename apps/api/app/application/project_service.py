"""Application service for tenant-scoped Project workspaces."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DomainError
from app.domain.models import Project, ProjectStatus, UserRole
from app.domain.rag.catalog import KnowledgeBase
from app.domain.tenant_context import TenantContext
from app.infrastructure.rag_catalog import SqlAlchemyKnowledgeBaseRepository
from app.infrastructure.rag_metrics import record_project_metric
from app.infrastructure.rag_projects import SqlAlchemyProjectAuditRepository, SqlAlchemyProjectRepository

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class ProjectKnowledgeBaseResult:
    id: str
    slug: str
    name: str
    status: str
    project_id: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ProjectMigrationReviewResult:
    id: str
    knowledge_base_id: str | None
    config_kind: str
    status: str
    legacy_count: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ProjectResult:
    id: str
    tenant_id: str
    slug: str
    name: str
    status: str
    is_default: bool
    knowledge_bases: tuple[ProjectKnowledgeBaseResult, ...]
    migration_reviews: tuple[ProjectMigrationReviewResult, ...]
    created_at: str
    updated_at: str


def _kb_result(kb: KnowledgeBase) -> ProjectKnowledgeBaseResult:
    return ProjectKnowledgeBaseResult(
        id=kb.id,
        slug=kb.slug,
        name=kb.name,
        status=str(kb.status),
        project_id=kb.project_id,
        created_at=kb.created_at.isoformat(),
        updated_at=kb.updated_at.isoformat(),
    )


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self._project_repo = SqlAlchemyProjectRepository(session)
        self._kb_repo = SqlAlchemyKnowledgeBaseRepository(session)
        self._audit_repo = SqlAlchemyProjectAuditRepository(session)

    async def list_all(self, *, tenant: TenantContext) -> list[ProjectResult]:
        projects = await self._project_repo.list_by_tenant(tenant_id=tenant.tenant_id)
        results: list[ProjectResult] = []
        for project in projects:
            results.append(await self._to_result(tenant_id=tenant.tenant_id, project=project))
        return results

    async def get(self, *, tenant: TenantContext, project_id: str) -> ProjectResult:
        project = await self._project_repo.find_by_id(tenant_id=tenant.tenant_id, project_id=project_id)
        if project is None:
            raise DomainError.not_found("Project not found")
        return await self._to_result(tenant_id=tenant.tenant_id, project=project)

    async def create(
        self,
        *,
        tenant: TenantContext,
        name: str,
        slug: str,
        knowledge_base_ids: tuple[str, ...] = (),
    ) -> ProjectResult:
        self._require_admin(tenant)
        self._validate_slug(slug)
        if await self._project_repo.find_by_slug(tenant_id=tenant.tenant_id, slug=slug) is not None:
            raise DomainError("CONFLICT", f"A project with slug '{slug}' already exists", 409)
        unique_kb_ids = tuple(dict.fromkeys(knowledge_base_ids))
        for knowledge_base_id in unique_kb_ids:
            kb = await self._kb_repo.find_by_id(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)
            if kb is None:
                raise DomainError.not_found("Knowledge base not found")
        project = await self._project_repo.create(tenant_id=tenant.tenant_id, slug=slug, name=name)
        if not await self._project_repo.move_knowledge_bases(
            tenant_id=tenant.tenant_id,
            project_id=project.id,
            knowledge_base_ids=unique_kb_ids,
        ):
            raise DomainError("PROJECT_MEMBERSHIP_CONFLICT", "Knowledge base could not be assigned", 409)
        await self._audit(
            tenant=tenant,
            project_id=project.id,
            action="PROJECT_CREATED",
            reason_code="PROJECT_CREATE",
            metadata={"slug": project.slug},
        )
        return await self.get(tenant=tenant, project_id=project.id)

    async def update(self, *, tenant: TenantContext, project_id: str, name: str, slug: str) -> ProjectResult:
        self._require_admin(tenant)
        self._validate_slug(slug)
        existing = await self._project_repo.find_by_slug(tenant_id=tenant.tenant_id, slug=slug)
        if existing is not None and existing.id != project_id:
            raise DomainError("CONFLICT", f"A project with slug '{slug}' already exists", 409)
        project = await self._project_repo.update(tenant_id=tenant.tenant_id, project_id=project_id, name=name, slug=slug)
        if project is None:
            raise DomainError.not_found("Project not found")
        await self._audit(
            tenant=tenant,
            project_id=project.id,
            action="PROJECT_UPDATED",
            reason_code="PROJECT_UPDATE",
            metadata={"slug": project.slug},
        )
        return await self.get(tenant=tenant, project_id=project.id)

    async def archive(self, *, tenant: TenantContext, project_id: str) -> ProjectResult:
        self._require_admin(tenant)
        project = await self._project_repo.find_by_id(tenant_id=tenant.tenant_id, project_id=project_id)
        if project is None:
            raise DomainError.not_found("Project not found")
        if project.is_default:
            raise DomainError("DEFAULT_PROJECT_IMMUTABLE", "The tenant default project cannot be archived", 422)
        members = await self._project_repo.list_knowledge_bases(
            tenant_id=tenant.tenant_id,
            project_id=project_id,
        )
        if members:
            raise DomainError(
                "PROJECT_HAS_KNOWLEDGE_BASES",
                "Move all Knowledge Bases out of the Project before archiving it",
                409,
            )
        archived = await self._project_repo.archive(tenant_id=tenant.tenant_id, project_id=project_id)
        if archived is None:
            raise DomainError.not_found("Project not found")
        await self._audit(
            tenant=tenant,
            project_id=project_id,
            action="PROJECT_ARCHIVED",
            reason_code="PROJECT_ARCHIVE",
        )
        return await self.get(tenant=tenant, project_id=project_id)

    async def move_knowledge_base(self, *, tenant: TenantContext, project_id: str, knowledge_base_id: str) -> ProjectResult:
        self._require_admin(tenant)
        project = await self._project_repo.find_by_id(tenant_id=tenant.tenant_id, project_id=project_id)
        if project is None or project.status is not ProjectStatus.ACTIVE:
            raise DomainError.not_found("Project not found")
        existing = await self._kb_repo.find_by_id(tenant_id=tenant.tenant_id, knowledge_base_id=knowledge_base_id)
        if existing is None:
            raise DomainError.not_found("Knowledge base not found")
        if await self._project_repo.move_knowledge_base(tenant_id=tenant.tenant_id, project_id=project_id, knowledge_base_id=knowledge_base_id) is None:
            raise DomainError("PROJECT_MEMBERSHIP_CONFLICT", "Knowledge base or destination project is invalid", 409)
        await self._audit(
            tenant=tenant,
            project_id=project_id,
            knowledge_base_id=knowledge_base_id,
            action="KNOWLEDGE_BASE_MOVED",
            reason_code="PROJECT_MEMBERSHIP_MOVE",
            metadata={"previousProjectId": existing.project_id},
        )
        record_project_metric(
            tenant_id=tenant.tenant_id,
            metric="membership_move",
            outcome="success",
            project_id=project_id,
            knowledge_base_count=1,
            reason_code="PROJECT_MEMBERSHIP_MOVE",
        )
        return await self.get(tenant=tenant, project_id=project_id)

    async def _audit(
        self,
        *,
        tenant: TenantContext,
        project_id: str | None,
        action: str,
        reason_code: str,
        knowledge_base_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        await self._audit_repo.record(
            tenant_id=tenant.tenant_id,
            project_id=project_id,
            knowledge_base_id=knowledge_base_id,
            user_id=tenant.user_id,
            action=action,
            reason_code=reason_code,
            metadata=metadata,
        )

    async def _to_result(self, *, tenant_id: str, project: Project) -> ProjectResult:
        knowledge_bases = await self._project_repo.list_knowledge_bases(tenant_id=tenant_id, project_id=project.id)
        migration_reviews = await self._project_repo.list_migration_reviews(
            tenant_id=tenant_id, project_id=project.id
        )
        open_reviews = [review for review in migration_reviews if review.status == "OPEN"]
        if open_reviews:
            record_project_metric(
                tenant_id=tenant_id,
                metric="migration_conflict",
                outcome="open",
                project_id=project.id,
                knowledge_base_count=sum(review.legacy_count for review in open_reviews),
                reason_code="MIGRATION_REVIEW_REQUIRED",
            )
        return ProjectResult(
            id=project.id,
            tenant_id=project.tenant_id,
            slug=project.slug,
            name=project.name,
            status=str(project.status),
            is_default=project.is_default,
            knowledge_bases=tuple(_kb_result(kb) for kb in knowledge_bases),
            migration_reviews=tuple(
                ProjectMigrationReviewResult(
                    id=review.id,
                    knowledge_base_id=review.knowledge_base_id,
                    config_kind=review.config_kind,
                    status=review.status,
                    legacy_count=review.legacy_count,
                    created_at=review.created_at.isoformat(),
                    updated_at=review.updated_at.isoformat(),
                )
                for review in migration_reviews
            ),
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
        )

    @staticmethod
    def _validate_slug(slug: str) -> None:
        if not _SLUG_RE.match(slug):
            raise DomainError.validation("Slug must be lowercase kebab-case (e.g. chatbot-a)")

    @staticmethod
    def _require_admin(tenant: TenantContext) -> None:
        if tenant.role is not UserRole.ADMIN:
            raise DomainError.forbidden("Project administration requires ADMIN access")
