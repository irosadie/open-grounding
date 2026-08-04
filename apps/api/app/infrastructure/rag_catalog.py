"""SQLAlchemy ORM records and repositories for the RAG knowledge catalog.

All records carry a non-null ``tenant_id`` foreign key to ``tenants.id`` and
use tenant-local uniqueness constraints so catalog relationships cannot cross
tenant boundaries. Repositories map ORM records to domain entities and never
return raw records. Imports SQLAlchemy only; domain code never imports this
module's types.
"""

from datetime import datetime
from typing import cast
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Uuid,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.rag.catalog import (
    Chunk,
    ChunkType,
    Document,
    DocumentVersion,
    DocumentVersionLifecycleState,
    IndexGeneration,
    IndexGenerationStatus,
    IngestionJob,
    IngestionJobStatus,
    KnowledgeBase,
    KnowledgeBaseStatus,
    KnowledgeSource,
    KnowledgeSourceType,
    OutboxEvent,
    OutboxEventStatus,
    StageCheckpoint,
    StageCheckpointStatus,
)
from app.domain.rag.policy import Classification
from app.domain.rag.profiles import IndexProfile, ModelProfile
from app.infrastructure.database import Base, utc_now


def _tenant_fk() -> ForeignKey:
    """Return a fresh tenant FK. ForeignKey objects cannot be shared across columns."""
    return ForeignKey("tenants.id", ondelete="CASCADE")


class KnowledgeBaseRecord(Base):
    __tablename__ = "rag_knowledge_bases"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[KnowledgeBaseStatus] = mapped_column(
        Enum(KnowledgeBaseStatus, name="KnowledgeBaseStatus"),
        default=KnowledgeBaseStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)
    __table_args__ = ()


class KnowledgeSourceRecord(Base):
    __tablename__ = "rag_knowledge_sources"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column("knowledge_base_id", Uuid(as_uuid=False), ForeignKey("rag_knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[KnowledgeSourceType] = mapped_column(Enum(KnowledgeSourceType, name="KnowledgeSourceType"), default=KnowledgeSourceType.UPLOAD, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class DocumentRecord(Base):
    __tablename__ = "rag_documents"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    knowledge_base_id: Mapped[str] = mapped_column("knowledge_base_id", Uuid(as_uuid=False), ForeignKey("rag_knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[str] = mapped_column("source_id", Uuid(as_uuid=False), ForeignKey("rag_knowledge_sources.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class DocumentVersionRecord(Base):
    __tablename__ = "rag_document_versions"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    document_id: Mapped[str] = mapped_column("document_id", Uuid(as_uuid=False), ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_state: Mapped[DocumentVersionLifecycleState] = mapped_column(
        Enum(DocumentVersionLifecycleState, name="DocumentVersionLifecycleState"),
        default=DocumentVersionLifecycleState.RECEIVED,
        nullable=False,
    )
    content_checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    source_revision: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pipeline_fingerprint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    object_key_raw: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    classification: Mapped[Classification] = mapped_column(
        Enum(Classification, name="Classification"), default=Classification.INTERNAL, nullable=False
    )
    acl_principals: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class ModelProfileRecord(Base):
    __tablename__ = "rag_model_profiles"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    profile_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class IndexProfileRecord(Base):
    __tablename__ = "rag_index_profiles"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    embedding_profile_id: Mapped[str] = mapped_column("embedding_profile_id", Uuid(as_uuid=False), ForeignKey("rag_model_profiles.id", ondelete="RESTRICT"), nullable=False)
    sparse_profile_id: Mapped[str | None] = mapped_column("sparse_profile_id", Uuid(as_uuid=False), ForeignKey("rag_model_profiles.id", ondelete="RESTRICT"), nullable=True)
    collection: Mapped[str] = mapped_column(String(255), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_metric: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class IndexGenerationRecord(Base):
    __tablename__ = "rag_index_generations"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    document_version_id: Mapped[str] = mapped_column("document_version_id", Uuid(as_uuid=False), ForeignKey("rag_document_versions.id", ondelete="CASCADE"), nullable=False)
    index_profile_id: Mapped[str] = mapped_column("index_profile_id", Uuid(as_uuid=False), ForeignKey("rag_index_profiles.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[IndexGenerationStatus] = mapped_column(
        Enum(IndexGenerationStatus, name="IndexGenerationStatus"),
        default=IndexGenerationStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class IngestionJobRecord(Base):
    __tablename__ = "rag_ingestion_jobs"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    document_version_id: Mapped[str] = mapped_column("document_version_id", Uuid(as_uuid=False), ForeignKey("rag_document_versions.id", ondelete="CASCADE"), nullable=False)
    generation_id: Mapped[str | None] = mapped_column("generation_id", Uuid(as_uuid=False), ForeignKey("rag_index_generations.id", ondelete="SET NULL"), nullable=True)
    stage: Mapped[str] = mapped_column(String(120), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(512), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[IngestionJobStatus] = mapped_column(Enum(IngestionJobStatus, name="IngestionJobStatus"), default=IngestionJobStatus.PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class OutboxEventRecord(Base):
    __tablename__ = "rag_outbox_events"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    generation_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(512), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[OutboxEventStatus] = mapped_column(Enum(OutboxEventStatus, name="OutboxEventStatus"), default=OutboxEventStatus.PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column("dispatched_at", DateTime(timezone=False), nullable=True)


# --- Entity mappers ----------------------------------------------------------


def _to_knowledge_base(row: KnowledgeBaseRecord) -> KnowledgeBase:
    return KnowledgeBase(
        id=row.id,
        tenant_id=row.tenant_id,
        slug=row.slug,
        name=row.name,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_knowledge_source(row: KnowledgeSourceRecord) -> KnowledgeSource:
    return KnowledgeSource(
        id=row.id,
        tenant_id=row.tenant_id,
        knowledge_base_id=row.knowledge_base_id,
        source_type=row.source_type,
        name=row.name,
        config_ref=row.config_ref,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_document(row: DocumentRecord) -> Document:
    return Document(
        id=row.id,
        tenant_id=row.tenant_id,
        knowledge_base_id=row.knowledge_base_id,
        source_id=row.source_id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_document_version(row: DocumentVersionRecord) -> DocumentVersion:
    return DocumentVersion(
        id=row.id,
        tenant_id=row.tenant_id,
        document_id=row.document_id,
        version_number=row.version_number,
        lifecycle_state=row.lifecycle_state,
        content_checksum=row.content_checksum,
        source_revision=row.source_revision,
        pipeline_fingerprint=row.pipeline_fingerprint,
        object_key_raw=row.object_key_raw,
        size_bytes=row.size_bytes,
        mime_type=row.mime_type,
        classification=row.classification,
        acl_principals=tuple(row.acl_principals),
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_model_profile(row: ModelProfileRecord) -> ModelProfile:
    return ModelProfile(
        id=row.id,
        profile_kind=row.profile_kind,
        provider=row.provider,
        model=row.model,
        dimensions=row.dimensions,
        version=row.version,
        is_active=row.is_active,
    )


def _to_index_profile(row: IndexProfileRecord) -> IndexProfile:
    return IndexProfile(
        id=row.id,
        embedding_profile_id=row.embedding_profile_id,
        sparse_profile_id=row.sparse_profile_id,
        collection=row.collection,
        dimensions=row.dimensions,
        distance_metric=row.distance_metric,
        version=row.version,
        is_active=row.is_active,
    )


def _to_index_generation(row: IndexGenerationRecord) -> IndexGeneration:
    return IndexGeneration(
        id=row.id,
        tenant_id=row.tenant_id,
        document_version_id=row.document_version_id,
        index_profile_id=row.index_profile_id,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_ingestion_job(row: IngestionJobRecord) -> IngestionJob:
    return IngestionJob(
        id=row.id,
        tenant_id=row.tenant_id,
        document_version_id=row.document_version_id,
        generation_id=row.generation_id,
        stage=row.stage,
        attempts=row.attempts,
        idempotency_key=row.idempotency_key,
        trace_id=row.trace_id,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_outbox_event(row: OutboxEventRecord) -> OutboxEvent:
    return OutboxEvent(
        id=row.id,
        tenant_id=row.tenant_id,
        event_type=row.event_type,
        resource_id=row.resource_id,
        generation_id=row.generation_id,
        idempotency_key=row.idempotency_key,
        trace_id=row.trace_id,
        payload=row.payload,
        status=row.status,
        created_at=row.created_at,
        dispatched_at=row.dispatched_at,
    )


# --- Repositories ------------------------------------------------------------


class SqlAlchemyKnowledgeBaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, *, tenant_id: str, knowledge_base_id: str) -> KnowledgeBase | None:
        result = await self._session.execute(
            select(KnowledgeBaseRecord).where(
                KnowledgeBaseRecord.tenant_id == tenant_id,
                KnowledgeBaseRecord.id == knowledge_base_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_knowledge_base(row) if row else None

    async def create(self, *, tenant_id: str, slug: str, name: str, status: str) -> KnowledgeBase:
        row = KnowledgeBaseRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            slug=slug,
            name=name,
            status=KnowledgeBaseStatus(status),
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_knowledge_base(row)


class SqlAlchemyKnowledgeSourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        tenant_id: str,
        knowledge_base_id: str,
        source_type: str,
        name: str,
        config_ref: str | None,
    ) -> KnowledgeSource:
        row = KnowledgeSourceRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            source_type=KnowledgeSourceType(source_type),
            name=name,
            config_ref=config_ref,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_knowledge_source(row)


class SqlAlchemyDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, *, tenant_id: str, document_id: str) -> Document | None:
        result = await self._session.execute(
            select(DocumentRecord).where(
                DocumentRecord.tenant_id == tenant_id,
                DocumentRecord.id == document_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_document(row) if row else None

    async def create(self, *, tenant_id: str, knowledge_base_id: str, source_id: str, title: str | None) -> Document:
        row = DocumentRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            source_id=source_id,
            title=title,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_document(row)


class SqlAlchemyDocumentVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, *, tenant_id: str, version_id: str) -> DocumentVersion | None:
        result = await self._session.execute(
            select(DocumentVersionRecord).where(
                DocumentVersionRecord.tenant_id == tenant_id,
                DocumentVersionRecord.id == version_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_document_version(row) if row else None

    async def create(
        self,
        *,
        tenant_id: str,
        document_id: str,
        version_number: int,
        content_checksum: str,
        object_key_raw: str,
        source_revision: str | None,
        pipeline_fingerprint: str | None,
        size_bytes: int | None,
        mime_type: str | None,
        classification: str = "INTERNAL",
        acl_principals: tuple[str, ...] = (),
    ) -> DocumentVersion:
        row = DocumentVersionRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            document_id=document_id,
            version_number=version_number,
            content_checksum=content_checksum,
            object_key_raw=object_key_raw,
            source_revision=source_revision,
            pipeline_fingerprint=pipeline_fingerprint,
            size_bytes=size_bytes,
            mime_type=mime_type,
            classification=Classification(classification),
            acl_principals=list(acl_principals),
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_document_version(row)

    async def update_lifecycle_state(self, *, tenant_id: str, version_id: str, lifecycle_state: str) -> DocumentVersion | None:
        result = await self._session.execute(
            select(DocumentVersionRecord).where(
                DocumentVersionRecord.tenant_id == tenant_id,
                DocumentVersionRecord.id == version_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.lifecycle_state = DocumentVersionLifecycleState(lifecycle_state)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_document_version(row)


class SqlAlchemyModelProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, *, tenant_id: str, profile_id: str) -> ModelProfile | None:
        result = await self._session.execute(
            select(ModelProfileRecord).where(
                ModelProfileRecord.tenant_id == tenant_id,
                ModelProfileRecord.id == profile_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_model_profile(row) if row else None

    async def create(
        self,
        *,
        tenant_id: str,
        profile_kind: str,
        provider: str,
        model: str,
        dimensions: int | None,
        version: str,
    ) -> ModelProfile:
        row = ModelProfileRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            profile_kind=profile_kind,
            provider=provider,
            model=model,
            dimensions=dimensions,
            version=version,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_model_profile(row)


class SqlAlchemyIndexProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, *, tenant_id: str, profile_id: str) -> IndexProfile | None:
        result = await self._session.execute(
            select(IndexProfileRecord).where(
                IndexProfileRecord.tenant_id == tenant_id,
                IndexProfileRecord.id == profile_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_index_profile(row) if row else None

    async def create(
        self,
        *,
        tenant_id: str,
        embedding_profile_id: str,
        sparse_profile_id: str | None,
        collection: str,
        dimensions: int,
        distance_metric: str,
        version: str,
    ) -> IndexProfile:
        row = IndexProfileRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            embedding_profile_id=embedding_profile_id,
            sparse_profile_id=sparse_profile_id,
            collection=collection,
            dimensions=dimensions,
            distance_metric=distance_metric,
            version=version,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_index_profile(row)

    async def activate(self, *, tenant_id: str, profile_id: str) -> IndexProfile | None:
        result = await self._session.execute(
            select(IndexProfileRecord).where(
                IndexProfileRecord.tenant_id == tenant_id,
                IndexProfileRecord.id == profile_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.is_active = True
        await self._session.commit()
        await self._session.refresh(row)
        return _to_index_profile(row)


class SqlAlchemyIndexGenerationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, *, tenant_id: str, generation_id: str) -> IndexGeneration | None:
        result = await self._session.execute(
            select(IndexGenerationRecord).where(
                IndexGenerationRecord.tenant_id == tenant_id,
                IndexGenerationRecord.id == generation_id,
            )
        )
        row = result.scalar_one_or_none()
        return _to_index_generation(row) if row else None

    async def find_active_for_version(self, *, tenant_id: str, document_version_id: str) -> IndexGeneration | None:
        result = await self._session.execute(
            select(IndexGenerationRecord).where(
                IndexGenerationRecord.tenant_id == tenant_id,
                IndexGenerationRecord.document_version_id == document_version_id,
                IndexGenerationRecord.status == IndexGenerationStatus.ACTIVE,
            )
        )
        row = result.scalar_one_or_none()
        return _to_index_generation(row) if row else None

    async def find_active_for_knowledge_bases(
        self, *, tenant_id: str, knowledge_base_ids: tuple[str, ...]
    ) -> list[IndexGeneration]:
        if not knowledge_base_ids:
            return []
        result = await self._session.execute(
            select(IndexGenerationRecord)
            .join(DocumentVersionRecord, IndexGenerationRecord.document_version_id == DocumentVersionRecord.id)
            .join(DocumentRecord, DocumentVersionRecord.document_id == DocumentRecord.id)
            .where(
                IndexGenerationRecord.tenant_id == tenant_id,
                IndexGenerationRecord.status == IndexGenerationStatus.ACTIVE,
                DocumentVersionRecord.tenant_id == tenant_id,
                DocumentRecord.tenant_id == tenant_id,
                DocumentRecord.knowledge_base_id.in_(knowledge_base_ids),
            )
        )
        return [_to_index_generation(row) for row in result.scalars().all()]

    async def create(self, *, tenant_id: str, document_version_id: str, index_profile_id: str, status: str) -> IndexGeneration:
        row = IndexGenerationRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            document_version_id=document_version_id,
            index_profile_id=index_profile_id,
            status=IndexGenerationStatus(status),
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_index_generation(row)

    async def update_status(self, *, tenant_id: str, generation_id: str, status: str) -> IndexGeneration | None:
        result = await self._session.execute(
            select(IndexGenerationRecord).where(
                IndexGenerationRecord.tenant_id == tenant_id,
                IndexGenerationRecord.id == generation_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.status = IndexGenerationStatus(status)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_index_generation(row)


class SqlAlchemyIngestionJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_idempotency_key(self, *, tenant_id: str, idempotency_key: str) -> IngestionJob | None:
        result = await self._session.execute(
            select(IngestionJobRecord).where(
                IngestionJobRecord.tenant_id == tenant_id,
                IngestionJobRecord.idempotency_key == idempotency_key,
            )
        )
        row = result.scalar_one_or_none()
        return _to_ingestion_job(row) if row else None

    async def create(
        self,
        *,
        tenant_id: str,
        document_version_id: str,
        generation_id: str | None,
        stage: str,
        idempotency_key: str,
        trace_id: str | None,
    ) -> IngestionJob:
        row = IngestionJobRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            document_version_id=document_version_id,
            generation_id=generation_id,
            stage=stage,
            idempotency_key=idempotency_key,
            trace_id=trace_id,
            status=IngestionJobStatus.PENDING,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_ingestion_job(row)


class SqlAlchemyOutboxEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        tenant_id: str,
        event_type: str,
        resource_id: str | None,
        generation_id: str | None,
        idempotency_key: str,
        trace_id: str | None,
        payload: dict[str, object],
    ) -> OutboxEvent:
        row = OutboxEventRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            event_type=event_type,
            resource_id=resource_id,
            generation_id=generation_id,
            idempotency_key=idempotency_key,
            trace_id=trace_id,
            payload=payload,
            status=OutboxEventStatus.PENDING,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_outbox_event(row)

    async def find_pending(self, *, tenant_id: str, limit: int) -> list[OutboxEvent]:
        result = await self._session.execute(
            select(OutboxEventRecord)
            .where(
                OutboxEventRecord.tenant_id == tenant_id,
                OutboxEventRecord.status == OutboxEventStatus.PENDING,
            )
            .limit(limit)
        )
        rows = list(result.scalars().all())
        return [_to_outbox_event(row) for row in rows]

    async def mark_dispatched(self, *, tenant_id: str, event_id: str) -> None:
        result = await self._session.execute(
            select(OutboxEventRecord).where(
                OutboxEventRecord.tenant_id == tenant_id,
                OutboxEventRecord.id == event_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return
        row.status = OutboxEventStatus.DISPATCHED
        row.dispatched_at = utc_now()
        await self._session.commit()


# --- Chunk ORM ---------------------------------------------------------------


class ChunkRecord(Base):
    __tablename__ = "rag_chunks"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    document_version_id: Mapped[str] = mapped_column("document_version_id", Uuid(as_uuid=False), ForeignKey("rag_document_versions.id", ondelete="CASCADE"), nullable=False)
    generation_id: Mapped[str] = mapped_column("generation_id", Uuid(as_uuid=False), ForeignKey("rag_index_generations.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[str | None] = mapped_column("parent_id", Uuid(as_uuid=False), ForeignKey("rag_chunks.id", ondelete="SET NULL"), nullable=True)
    chunk_type: Mapped[ChunkType] = mapped_column(Enum(ChunkType, name="ChunkType"), default=ChunkType.CHILD, nullable=False)
    hierarchy_path: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str] = mapped_column(String(60), nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_offsets_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_offsets_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunker_version: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)


def _to_chunk(row: ChunkRecord) -> Chunk:
    return Chunk(
        id=row.id,
        tenant_id=row.tenant_id,
        document_version_id=row.document_version_id,
        generation_id=row.generation_id,
        parent_id=row.parent_id,
        chunk_type=row.chunk_type,
        hierarchy_path=tuple(row.hierarchy_path),
        page=row.page,
        content_type=row.content_type,
        text=row.text,
        token_count=row.token_count,
        source_offsets_start=row.source_offsets_start,
        source_offsets_end=row.source_offsets_end,
        chunker_version=row.chunker_version,
        created_at=row.created_at,
    )


class SqlAlchemyChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_generation(self, *, tenant_id: str, generation_id: str) -> list[Chunk]:
        result = await self._session.execute(
            select(ChunkRecord)
            .where(
                ChunkRecord.tenant_id == tenant_id,
                ChunkRecord.generation_id == generation_id,
            )
            .order_by(ChunkRecord.created_at)
        )
        rows = list(result.scalars().all())
        return [_to_chunk(row) for row in rows]

    async def create_many(self, *, tenant_id: str, chunks: list[dict[str, object]]) -> int:
        for chunk_data in chunks:
            row = ChunkRecord(
                id=str(chunk_data.get("id", str(uuid4()))),
                tenant_id=tenant_id,
                document_version_id=str(chunk_data["document_version_id"]),
                generation_id=str(chunk_data["generation_id"]),
                parent_id=chunk_data.get("parent_id"),
                chunk_type=ChunkType(str(chunk_data.get("chunk_type", "CHILD"))),
                hierarchy_path=list(cast(list[str], chunk_data.get("hierarchy_path", []))),
                page=chunk_data.get("page"),
                content_type=str(chunk_data.get("content_type", "narrative")),
                text=str(chunk_data.get("text", "")),
                token_count=int(cast(int, chunk_data.get("token_count", 0))),
                source_offsets_start=chunk_data.get("source_offsets_start"),
                source_offsets_end=chunk_data.get("source_offsets_end"),
                chunker_version=str(chunk_data.get("chunker_version", "1")),
            )
            self._session.add(row)
        await self._session.commit()
        return len(chunks)

    async def delete_by_generation(self, *, tenant_id: str, generation_id: str) -> None:
        await self._session.execute(
            select(ChunkRecord).where(
                ChunkRecord.tenant_id == tenant_id,
                ChunkRecord.generation_id == generation_id,
            )
        )
        from sqlalchemy import delete as sa_delete

        await self._session.execute(
            sa_delete(ChunkRecord).where(
                ChunkRecord.tenant_id == tenant_id,
                ChunkRecord.generation_id == generation_id,
            )
        )
        await self._session.commit()


# --- Stage checkpoint ORM ----------------------------------------------------


class StageCheckpointRecord(Base):
    __tablename__ = "rag_stage_checkpoints"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column("tenant_id", Uuid(as_uuid=False), _tenant_fk(), nullable=False)
    document_version_id: Mapped[str] = mapped_column("document_version_id", Uuid(as_uuid=False), ForeignKey("rag_document_versions.id", ondelete="CASCADE"), nullable=False)
    generation_id: Mapped[str | None] = mapped_column("generation_id", Uuid(as_uuid=False), ForeignKey("rag_index_generations.id", ondelete="SET NULL"), nullable=True)
    stage: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[StageCheckpointStatus] = mapped_column(
        Enum(StageCheckpointStatus, name="StageCheckpointStatus"),
        default=StageCheckpointStatus.PENDING,
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(512), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    checkpoint_data: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("updated_at", DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)
    __table_args__ = ()


def _to_stage_checkpoint(row: StageCheckpointRecord) -> StageCheckpoint:
    return StageCheckpoint(
        id=row.id,
        tenant_id=row.tenant_id,
        document_version_id=row.document_version_id,
        generation_id=row.generation_id,
        stage=row.stage,
        status=row.status,
        attempts=row.attempts,
        idempotency_key=row.idempotency_key,
        trace_id=row.trace_id,
        checkpoint_data=row.checkpoint_data,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyStageCheckpointRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_stage(self, *, tenant_id: str, document_version_id: str, stage: str) -> StageCheckpoint | None:
        result = await self._session.execute(
            select(StageCheckpointRecord).where(
                StageCheckpointRecord.tenant_id == tenant_id,
                StageCheckpointRecord.document_version_id == document_version_id,
                StageCheckpointRecord.stage == stage,
            )
        )
        row = result.scalar_one_or_none()
        return _to_stage_checkpoint(row) if row else None

    async def upsert(
        self,
        *,
        tenant_id: str,
        document_version_id: str,
        generation_id: str | None,
        stage: str,
        status: str,
        attempts: int,
        idempotency_key: str,
        trace_id: str | None,
        checkpoint_data: dict[str, object],
    ) -> StageCheckpoint:
        existing = await self.find_by_stage(tenant_id=tenant_id, document_version_id=document_version_id, stage=stage)
        if existing is not None:
            result = await self._session.execute(select(StageCheckpointRecord).where(StageCheckpointRecord.id == existing.id))
            row = result.scalar_one()
            row.status = StageCheckpointStatus(status)
            row.attempts = attempts
            row.generation_id = generation_id
            row.trace_id = trace_id
            row.checkpoint_data = checkpoint_data
        else:
            row = StageCheckpointRecord(
                id=str(uuid4()),
                tenant_id=tenant_id,
                document_version_id=document_version_id,
                generation_id=generation_id,
                stage=stage,
                status=StageCheckpointStatus(status),
                attempts=attempts,
                idempotency_key=idempotency_key,
                trace_id=trace_id,
                checkpoint_data=checkpoint_data,
            )
            self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_stage_checkpoint(row)
