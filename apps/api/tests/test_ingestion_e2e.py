"""End-to-end ingestion pipeline tests for PDF, Markdown, and TXT.

Tests the full lifecycle: parse → normalize → quality gate → chunk → status.
Uses mock docling output (heavy ML dependency may not be installed). Skipped
unless RUN_DATABASE_TESTS=1 and DB ends in _test.
"""

import os
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.settings import Settings
from app.domain.rag.chunker import chunk_document
from app.domain.rag.elements import DocumentElement, ElementType, ParsedDocument, ParserQualitySummary
from app.domain.rag.normalizer import QualityGate, compute_quality, normalize_document
from app.infrastructure.database import TenantRecord, create_session_factory
from app.infrastructure.rag_catalog import IndexGenerationRecord, KnowledgeBaseRecord, OutboxEventRecord

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DATABASE_TESTS") != "1",
    reason="Set RUN_DATABASE_TESTS=1 to run ingestion E2E tests.",
)

TENANT_ID = str(uuid4())


@pytest.fixture
async def session() -> AsyncSession:
    settings = Settings()
    database_name = urlparse(settings.database_url).path.removeprefix("/")
    if not database_name.endswith("_test"):
        raise RuntimeError("E2E tests require a DATABASE_URL ending in _test.")
    session_factory: async_sessionmaker[AsyncSession] = create_session_factory(settings)
    async with session_factory() as s:
        await s.execute(delete(OutboxEventRecord))
        await s.execute(delete(IndexGenerationRecord))
        await s.execute(delete(KnowledgeBaseRecord))
        await s.execute(delete(TenantRecord))
        await s.commit()
        s.add(TenantRecord(id=TENANT_ID, slug="e2e", name="E2E Tenant", status="ACTIVE"))
        await s.commit()
        yield s
    bind = session_factory.kw.get("bind")
    if bind is not None:
        await bind.dispose()


def _mock_parsed_doc(text: str, mime_type: str) -> ParsedDocument:
    """Create a mock ParsedDocument simulating docling output."""
    if "markdown" in mime_type:
        elements = [
            DocumentElement(id="e1", type=ElementType.TITLE, text="Heading", page=1),
            DocumentElement(id="e2", type=ElementType.CODE, text="print('hello')"),
            DocumentElement(id="e3", type=ElementType.NARRATIVE, text=text, page=1, extraction_confidence=0.9),
        ]
    elif mime_type == "application/pdf":
        elements = [
            DocumentElement(id="e1", type=ElementType.TITLE, text="Title", page=1, extraction_confidence=0.9),
            DocumentElement(id="e2", type=ElementType.NARRATIVE, text=text, page=1, extraction_confidence=0.9),
            DocumentElement(id="e3", type=ElementType.NARRATIVE, text=text, page=2, extraction_confidence=0.85),
        ]
    else:
        elements = [DocumentElement(id="e1", type=ElementType.NARRATIVE, text=text, extraction_confidence=0.9)]
    q = compute_quality(elements, is_pdf=mime_type == "application/pdf", pages_expected=2 if "pdf" in mime_type else 0)
    return ParsedDocument(elements=elements, quality=q)


def test_pdf_pipeline_parse_normalize_chunk() -> None:
    """PDF: parse → normalize → quality gate → chunk produces valid output."""
    doc = _mock_parsed_doc("paragraph text " * 200, "application/pdf")
    normalized = normalize_document(doc)
    gate = QualityGate()
    verdict = gate.evaluate(normalized.quality, is_pdf=True, pages_expected=2)
    assert verdict in ("READY", "NEEDS_REVIEW")
    manifest = chunk_document(normalized)
    parents = [c for c in manifest.chunks if c.chunk_type == "PARENT"]
    children = [c for c in manifest.chunks if c.chunk_type == "CHILD"]
    assert len(parents) >= 1
    assert len(children) >= 1


def test_markdown_pipeline_preserves_code_boundary() -> None:
    """Markdown: heading and code block boundaries are preserved through chunking."""
    doc = _mock_parsed_doc("body " * 200, "text/markdown")
    manifest = chunk_document(doc)
    parents = [c for c in manifest.chunks if c.chunk_type == "PARENT"]
    assert len(parents) >= 2


def test_txt_pipeline_produces_narrative_chunks() -> None:
    """TXT: becomes ordered narrative elements that chunk into parent-child."""
    doc = _mock_parsed_doc("word " * 400, "text/plain")
    manifest = chunk_document(doc)
    assert all(c.content_type == ElementType.NARRATIVE for c in manifest.chunks)
    assert any(c.chunk_type == "PARENT" for c in manifest.chunks)


def test_retry_produces_identical_chunks() -> None:
    """Same source + same chunker version produces identical chunk IDs."""
    doc = _mock_parsed_doc("word " * 300, "text/plain")
    m1 = chunk_document(doc)
    m2 = chunk_document(doc)
    assert [c.id for c in m1.chunks] == [c.id for c in m2.chunks]


def test_empty_extraction_never_becomes_ready() -> None:
    """Empty extraction quality must FAIL, never READY."""
    empty_doc = ParsedDocument(
        elements=[],
        quality=ParserQualitySummary(element_count=0, text_coverage=0.0, empty_element_ratio=1.0, page_coverage=None, aggregate_confidence=None),
    )
    gate = QualityGate()
    assert gate.evaluate(empty_doc.quality) == "FAILED"


async def test_catalog_lifecycle_intake_to_deletion(session: AsyncSession) -> None:
    """E2E: create KB → source → document → version → lifecycle transitions."""
    from app.application.ingestion_intake_service import IngestionIntakeService
    from app.domain.tenant_context import TenantContext
    from app.infrastructure.rag_catalog import SqlAlchemyKnowledgeBaseRepository

    tenant = TenantContext(tenant_id=TENANT_ID, membership_id=str(uuid4()), user_id=str(uuid4()))
    kb_repo = SqlAlchemyKnowledgeBaseRepository(session)
    kb = await kb_repo.create(tenant_id=TENANT_ID, slug="e2e-kb", name="E2E KB", status="ACTIVE")

    service = IngestionIntakeService(session, Settings(_env_file=None))
    intake = await service.create_intake(
        tenant=tenant,
        knowledge_base_id=kb.id,
        filename="test.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        title="E2E Test",
    )
    assert intake.document_id is not None
    assert intake.upload_key.startswith(f"tenants/{TENANT_ID}/")

    status = await service.get_status(tenant=tenant, document_version_id=intake.document_version_id)
    assert status["lifecycleState"] == "RECEIVED"

    completion = await service.complete_intake(
        tenant=tenant,
        document_version_id=intake.document_version_id,
        content_checksum="sha256:abc123",
    )
    assert completion.lifecycle_state == "STORED"

    await service.soft_delete(tenant=tenant, document_version_id=intake.document_version_id)
    status_after = await service.get_status(tenant=tenant, document_version_id=intake.document_version_id)
    assert status_after["lifecycleState"] == "DELETING"
