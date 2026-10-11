"""Project persistence for tenant-scoped RAG workspaces."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, String, UniqueConstraint, Uuid, distinct, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.models import Project, ProjectMigrationReview, ProjectStatus
from app.domain.rag.catalog import KnowledgeBase, KnowledgeBaseStatus
from app.infrastructure.database import Base, utc_now
from app.infrastructure.rag_catalog import KnowledgeBaseRecord, _to_knowledge_base


class ProjectRecord(Base):
    __tablename__ = "rag_projects"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus, name="ProjectStatus"), default=ProjectStatus.ACTIVE, nullable=False)
    is_default: Mapped[bool] = mapped_column("is_default", nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_rag_projects_tenant_slug"),
        Index("ix_rag_projects_tenant_status", "tenant_id", "status"),
    )


class ProjectMigrationReviewRecord(Base):
    __tablename__ = "rag_project_migration_reviews"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("rag_projects.id", ondelete="CASCADE"), nullable=False)
    knowledge_base_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("rag_knowledge_bases.id", ondelete="SET NULL"), nullable=True
    )
    config_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    legacy_count: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "config_kind", name="uq_project_migration_review_kind"),
        Index("ix_project_migration_reviews_tenant_status", "tenant_id", "status"),
    )


class ProjectAuditEventRecord(Base):
    __tablename__ = "rag_project_audit_events"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("rag_projects.id", ondelete="SET NULL"), nullable=True
    )
    knowledge_base_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("rag_knowledge_bases.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(96), nullable=False)
    event_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


def _to_project(row: ProjectRecord) -> Project:
    return Project(
        id=row.id,
        tenant_id=row.tenant_id,
        slug=row.slug,
        name=row.name,
        status=row.status,
        is_default=row.is_default,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_migration_review(row: ProjectMigrationReviewRecord) -> ProjectMigrationReview:
    return ProjectMigrationReview(
        id=row.id,
        tenant_id=row.tenant_id,
        project_id=row.project_id,
        knowledge_base_id=row.knowledge_base_id,
        config_kind=row.config_kind,
        status=row.status,
        legacy_count=row.legacy_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, *, tenant_id: str, project_id: str) -> Project | None:
        result = await self._session.execute(select(ProjectRecord).where(ProjectRecord.tenant_id == tenant_id, ProjectRecord.id == project_id))
        row = result.scalar_one_or_none()
        return _to_project(row) if row else None


    async def find_by_slug(self, *, tenant_id: str, slug: str) -> Project | None:
        result = await self._session.execute(select(ProjectRecord).where(ProjectRecord.tenant_id == tenant_id, ProjectRecord.slug == slug))
        row = result.scalar_one_or_none()
        return _to_project(row) if row else None

    async def find_default(self, *, tenant_id: str) -> Project | None:
        result = await self._session.execute(
            select(ProjectRecord).where(
                ProjectRecord.tenant_id == tenant_id,
                ProjectRecord.is_default.is_(True),
                ProjectRecord.status == ProjectStatus.ACTIVE,
            )
        )
        row = result.scalar_one_or_none()
        return _to_project(row) if row else None

    async def create(self, *, tenant_id: str, slug: str, name: str, is_default: bool = False) -> Project:
        row = ProjectRecord(id=str(uuid4()), tenant_id=tenant_id, slug=slug, name=name, is_default=is_default, status=ProjectStatus.ACTIVE)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_project(row)

    async def list_by_tenant(self, *, tenant_id: str) -> list[Project]:
        result = await self._session.execute(select(ProjectRecord).where(ProjectRecord.tenant_id == tenant_id).order_by(ProjectRecord.is_default.desc(), ProjectRecord.created_at.desc()))
        return [_to_project(row) for row in result.scalars().all()]

    async def list_migration_reviews(self, *, tenant_id: str, project_id: str) -> list[ProjectMigrationReview]:
        result = await self._session.execute(
            select(ProjectMigrationReviewRecord)
            .where(
                ProjectMigrationReviewRecord.tenant_id == tenant_id,
                ProjectMigrationReviewRecord.project_id == project_id,
            )
            .order_by(ProjectMigrationReviewRecord.config_kind.asc())
        )
        return [_to_migration_review(row) for row in result.scalars().all()]

    async def archive(self, *, tenant_id: str, project_id: str) -> Project | None:
        project = await self.find_by_id(tenant_id=tenant_id, project_id=project_id)
        if project is None:
            return None
        if project.is_default:
            return project
        result = await self._session.execute(
            update(ProjectRecord).where(ProjectRecord.tenant_id == tenant_id, ProjectRecord.id == project_id).values(status=ProjectStatus.ARCHIVED, updated_at=utc_now()).returning(ProjectRecord)
        )
        row = result.scalar_one_or_none()
        await self._session.commit()
        return _to_project(row) if row else None

    async def update(self, *, tenant_id: str, project_id: str, name: str, slug: str) -> Project | None:
        result = await self._session.execute(update(ProjectRecord).where(ProjectRecord.tenant_id == tenant_id, ProjectRecord.id == project_id).values(name=name, slug=slug, updated_at=utc_now()).returning(ProjectRecord))
        row = result.scalar_one_or_none()
        await self._session.commit()
        return _to_project(row) if row else None

    async def list_knowledge_bases(self, *, tenant_id: str, project_id: str) -> list[KnowledgeBase]:
        result = await self._session.execute(
            select(KnowledgeBaseRecord)
            .where(
                KnowledgeBaseRecord.tenant_id == tenant_id,
                KnowledgeBaseRecord.project_id == project_id,
                KnowledgeBaseRecord.status != KnowledgeBaseStatus.DELETED,
            )
            .order_by(KnowledgeBaseRecord.created_at.desc())
        )
        return [_to_knowledge_base(row) for row in result.scalars().all()]

    async def move_knowledge_base(self, *, tenant_id: str, project_id: str, knowledge_base_id: str) -> KnowledgeBase | None:
        destination = await self.find_by_id(tenant_id=tenant_id, project_id=project_id)
        if destination is None or destination.status is not ProjectStatus.ACTIVE:
            return None
        result = await self._session.execute(
            select(KnowledgeBaseRecord).where(
                KnowledgeBaseRecord.tenant_id == tenant_id,
                KnowledgeBaseRecord.id == knowledge_base_id,
                KnowledgeBaseRecord.status == KnowledgeBaseStatus.ACTIVE,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.project_id = project_id
        row.updated_at = utc_now()
        await self._session.commit()
        await self._session.refresh(row)
        return _to_knowledge_base(row)

    async def move_knowledge_bases(
        self, *, tenant_id: str, project_id: str, knowledge_base_ids: tuple[str, ...]
    ) -> bool:
        unique_ids = tuple(dict.fromkeys(knowledge_base_ids))
        if not unique_ids:
            return True
        destination = await self.find_by_id(tenant_id=tenant_id, project_id=project_id)
        if destination is None or destination.status is not ProjectStatus.ACTIVE:
            return False
        result = await self._session.execute(
            select(KnowledgeBaseRecord)
            .where(
                KnowledgeBaseRecord.tenant_id == tenant_id,
                KnowledgeBaseRecord.id.in_(unique_ids),
                KnowledgeBaseRecord.status == KnowledgeBaseStatus.ACTIVE,
            )
            .with_for_update()
        )
        rows = list(result.scalars().all())
        if len(rows) != len(unique_ids):
            await self._session.rollback()
            return False
        for row in rows:
            row.project_id = project_id
            row.updated_at = utc_now()
        await self._session.commit()
        return True

    async def resolve_project_for_knowledge_bases(self, *, tenant_id: str, knowledge_base_ids: tuple[str, ...]) -> Project | None:
        if not knowledge_base_ids:
            return None
        unique_ids = tuple(dict.fromkeys(knowledge_base_ids))
        result = await self._session.execute(
            select(ProjectRecord)
            .join(KnowledgeBaseRecord, KnowledgeBaseRecord.project_id == ProjectRecord.id)
            .where(
                ProjectRecord.tenant_id == tenant_id,
                ProjectRecord.status == ProjectStatus.ACTIVE,
                KnowledgeBaseRecord.tenant_id == tenant_id,
                KnowledgeBaseRecord.id.in_(unique_ids),
                KnowledgeBaseRecord.status == KnowledgeBaseStatus.ACTIVE,
            )
            .group_by(ProjectRecord.id)
            .having(func.count(distinct(KnowledgeBaseRecord.id)) == len(unique_ids))
        )
        row = result.scalar_one_or_none()
        return _to_project(row) if row else None


class SqlAlchemyProjectAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        knowledge_base_id: str | None,
        user_id: str | None,
        action: str,
        reason_code: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        bounded = {
            str(key)[:64]: _bound_audit_value(value)
            for key, value in list((metadata or {}).items())[:16]
        }
        self._session.add(
            ProjectAuditEventRecord(
                id=str(uuid4()),
                tenant_id=tenant_id,
                project_id=project_id,
                knowledge_base_id=knowledge_base_id,
                user_id=user_id,
                action=action,
                reason_code=reason_code[:96],
                event_metadata=bounded,
            )
        )
        await self._session.commit()


def _bound_audit_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:256]
    return str(value)[:256]
