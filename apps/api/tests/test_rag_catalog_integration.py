"""PostgreSQL integration tests for the RAG knowledge catalog.

Covers tenant isolation, catalog lineage, incompatible-profile rejection,
atomic outbox creation, and failed-generation recovery state. Skipped unless
``RUN_DATABASE_TESTS=1`` is set and the DATABASE_URL ends in ``_test``.
"""

import os
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.settings import Settings
from app.domain.rag.catalog import IndexGenerationStatus
from app.domain.rag.profiles import (
    IndexProfile,
    ModelProfile,
    validate_index_profile_compatibility,
)
from app.infrastructure.database import TenantRecord, create_session_factory
from app.infrastructure.rag_catalog import (
    DocumentRecord,
    DocumentVersionRecord,
    IndexGenerationRecord,
    KnowledgeBaseRecord,
    KnowledgeSourceRecord,
    OutboxEventRecord,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DATABASE_TESTS") != "1",
    reason="Set RUN_DATABASE_TESTS=1 to run PostgreSQL integration tests.",
)

TENANT_A_ID = str(uuid4())
TENANT_B_ID = str(uuid4())


@pytest.fixture
async def session() -> AsyncSession:
    settings = Settings()
    database_name = urlparse(settings.database_url).path.removeprefix("/")
    if not database_name.endswith("_test"):
        raise RuntimeError("Integration tests require a DATABASE_URL ending in _test.")
    session_factory: async_sessionmaker[AsyncSession] = create_session_factory(settings)
    async with session_factory() as s:
        await s.execute(delete(OutboxEventRecord))
        await s.execute(delete(IndexGenerationRecord))
        await s.execute(delete(DocumentVersionRecord))
        await s.execute(delete(DocumentRecord))
        await s.execute(delete(KnowledgeSourceRecord))
        await s.execute(delete(KnowledgeBaseRecord))
        await s.execute(delete(TenantRecord))
        await s.commit()
        yield s
    bind = session_factory.kw.get("bind")
    if bind is not None:
        await bind.dispose()


async def _seed_tenant(s: AsyncSession, tenant_id: str, slug: str) -> None:
    s.add(TenantRecord(id=tenant_id, slug=slug, name=f"Tenant {slug}", status="ACTIVE"))
    await s.commit()


async def _seed_kb(s: AsyncSession, tenant_id: str, slug: str) -> KnowledgeBaseRecord:
    kb = KnowledgeBaseRecord(id=str(uuid4()), tenant_id=tenant_id, slug=slug, name=f"KB {slug}", status="ACTIVE")
    s.add(kb)
    await s.commit()
    await s.refresh(kb)
    return kb


async def _seed_catalog_chain(s: AsyncSession, tenant_id: str, slug: str) -> tuple[str, str]:
    """Seed KB → source → document → version + model profile → index profile.

    Returns (document_version_id, index_profile_id) so a generation can be
    created with valid foreign keys.
    """
    from app.infrastructure.rag_catalog import (
        DocumentRecord,
        DocumentVersionRecord,
        IndexProfileRecord,
        ModelProfileRecord,
    )

    kb = await _seed_kb(s, tenant_id, slug)
    src = KnowledgeSourceRecord(
        id=str(uuid4()), tenant_id=tenant_id, knowledge_base_id=kb.id,
        source_type="UPLOAD", name=f"Source {slug}", config_ref=None,
    )
    s.add(src)
    await s.flush()
    doc = DocumentRecord(
        id=str(uuid4()), tenant_id=tenant_id, knowledge_base_id=kb.id,
        source_id=src.id, title=f"Doc {slug}",
    )
    s.add(doc)
    await s.flush()
    version = DocumentVersionRecord(
        id=str(uuid4()), tenant_id=tenant_id, document_id=doc.id, version_number=1,
        content_checksum=f"sha256:{slug}", object_key_raw=f"tenants/{tenant_id}/docs/{doc.id}/raw",
        size_bytes=1024, mime_type="application/pdf",
    )
    s.add(version)
    emb = ModelProfileRecord(
        id=str(uuid4()), tenant_id=tenant_id, profile_kind="embedding",
        provider="local", model="bge", dimensions=768, version="1", is_active=True,
    )
    s.add(emb)
    await s.flush()
    idx = IndexProfileRecord(
        id=str(uuid4()), tenant_id=tenant_id, embedding_profile_id=emb.id,
        sparse_profile_id=None, collection="rag", dimensions=768,
        distance_metric="cosine", version="1", is_active=True,
    )
    s.add(idx)
    await s.commit()
    await s.refresh(version)
    await s.refresh(idx)
    return version.id, idx.id


async def test_cross_tenant_knowledge_base_isolation(session: AsyncSession) -> None:
    from app.infrastructure.rag_catalog import SqlAlchemyKnowledgeBaseRepository

    await _seed_tenant(session, TENANT_A_ID, "iso-a")
    await _seed_tenant(session, TENANT_B_ID, "iso-b")
    repo = SqlAlchemyKnowledgeBaseRepository(session)
    kb_a = await repo.create(tenant_id=TENANT_A_ID, slug="kb-a", name="KB A", status="ACTIVE")
    assert await repo.find_by_id(tenant_id=TENANT_A_ID, knowledge_base_id=kb_a.id) is not None
    assert await repo.find_by_id(tenant_id=TENANT_B_ID, knowledge_base_id=kb_a.id) is None


async def test_index_generation_lineage_and_failed_recovery(session: AsyncSession) -> None:
    from app.infrastructure.rag_catalog import SqlAlchemyIndexGenerationRepository

    await _seed_tenant(session, TENANT_A_ID, "lin-a")
    version_id, profile_id = await _seed_catalog_chain(session, TENANT_A_ID, "lin")
    repo = SqlAlchemyIndexGenerationRepository(session)
    gen = await repo.create(
        tenant_id=TENANT_A_ID, document_version_id=version_id,
        index_profile_id=profile_id, status="PENDING",
    )
    assert gen.status is IndexGenerationStatus.PENDING
    failed = await repo.update_status(tenant_id=TENANT_A_ID, generation_id=gen.id, status="FAILED")
    assert failed is not None and failed.status is IndexGenerationStatus.FAILED
    assert await repo.find_active_for_version(tenant_id=TENANT_A_ID, document_version_id=version_id) is None
    active = await repo.update_status(tenant_id=TENANT_A_ID, generation_id=gen.id, status="ACTIVE")
    assert active is not None and active.status is IndexGenerationStatus.ACTIVE


async def test_atomic_outbox_creation_with_generation(session: AsyncSession) -> None:
    from app.application.rag_outbox_service import RagPublicationService

    await _seed_tenant(session, TENANT_A_ID, "outbox-a")
    version_id, profile_id = await _seed_catalog_chain(session, TENANT_A_ID, "outbox")
    service = RagPublicationService(session)
    result = await service.create_pending_publication(
        tenant_id=TENANT_A_ID, document_version_id=version_id,
        index_profile_id=profile_id, trace_id="trace-1",
    )
    assert result.generation.status is IndexGenerationStatus.PENDING
    assert result.outbox_event.event_type == "GENERATION_PUBLISHED"
    assert result.outbox_event.generation_id == result.generation.id
    assert result.outbox_event.payload["generationId"] == result.generation.id


async def test_incompatible_profile_rejection_is_pure() -> None:
    emb = ModelProfile(id="emb-1", profile_kind="embedding", provider="local", model="bge", dimensions=768, version="1")
    idx = IndexProfile(id="idx-1", embedding_profile_id="emb-1", sparse_profile_id=None, collection="rag", dimensions=1024, distance_metric="cosine", version="1")
    result = validate_index_profile_compatibility(index=idx, embedding=emb)
    assert not result.is_compatible
