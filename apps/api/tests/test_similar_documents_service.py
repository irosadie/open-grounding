from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.application.similar_documents_service import MAX_PREVIEW_CHARS, SimilarDocumentsService
from app.domain.errors import DomainError
from app.domain.models import UserRole
from app.domain.rag.catalog import (
    Document,
    DocumentVersion,
    DocumentVersionLifecycleState,
    IndexGeneration,
    IndexGenerationStatus,
)
from app.domain.rag.policy import Classification
from app.domain.rag.profiles import IndexProfile
from app.domain.tenant_context import TenantContext


def _version(*, version_id: str, document_id: str, text: str | None, state: DocumentVersionLifecycleState) -> DocumentVersion:
    now = datetime.now(UTC)
    return DocumentVersion(
        id=version_id,
        tenant_id="tenant-1",
        document_id=document_id,
        version_number=1,
        lifecycle_state=state,
        content_checksum="checksum",
        source_revision=None,
        pipeline_fingerprint=None,
        parsed_text=text,
        metadata=None,
        object_key_raw="object",
        size_bytes=10,
        mime_type="text/plain",
        classification=Classification.INTERNAL,
        acl_principals=(),
        effective_from=None,
        effective_to=None,
        created_at=now,
        updated_at=now,
    )


def _service(
    current: DocumentVersion | None,
    catalog: list[tuple[DocumentVersion, str, str]],
    results: list[dict[str, object]],
) -> tuple[SimilarDocumentsService, AsyncMock]:
    versions = AsyncMock()
    versions.find_by_id.return_value = current
    versions.list_by_knowledge_base.return_value = catalog
    documents = AsyncMock()
    documents.find_by_id.return_value = Document(
        id="doc-current",
        tenant_id="tenant-1",
        knowledge_base_id="kb-1",
        source_id="source-1",
        title="Current",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    generations = AsyncMock()
    generations.find_active_for_knowledge_bases.return_value = [
        IndexGeneration(
            id="generation-1",
            tenant_id="tenant-1",
            document_version_id="other-version",
            index_profile_id="profile-1",
            status=IndexGenerationStatus.ACTIVE,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    ]
    profiles = AsyncMock()
    profiles.find_active.return_value = IndexProfile(
        id="profile-1",
        tenant_id="tenant-1",
        name="Default",
        embedding_profile_id="embedding-1",
        sparse_profile_id="sparse-1",
        reranker_profile_id=None,
        collection="rag",
        dimensions=384,
        distance_metric="cosine",
        chunking_strategy="RECURSIVE",
        chunk_size_tokens=400,
        chunk_overlap_tokens=50,
        parent_chunk_size=1500,
        version="v1",
        is_active=True,
    )
    retrieval = AsyncMock()
    retrieval.retrieve.return_value = (results, [])
    return SimilarDocumentsService(versions, documents, generations, profiles, retrieval), retrieval


@pytest.mark.asyncio
async def test_groups_chunk_hits_and_preserves_same_kb_scope() -> None:
    current = _version(version_id="current-version", document_id="doc-current", text="current text", state=DocumentVersionLifecycleState.NEEDS_REVIEW)
    match = _version(version_id="match-version", document_id="doc-match", text="indexed", state=DocumentVersionLifecycleState.READY)
    long_preview = "word " * (MAX_PREVIEW_CHARS // 4 + 20)
    service, retrieval = _service(
        current,
        [(current, "Current", "doc-current"), (match, "Related policy", "doc-match")],
        [
            {"score": 0.62, "payload": {"document_version_id": "match-version", "text": "lower score"}},
            {"score": 0.91, "payload": {"document_version_id": "match-version", "text": long_preview}},
            {"score": 0.99, "payload": {"document_version_id": "current-version", "text": "self"}},
            {"score": 0.98, "payload": {"document_version_id": str(uuid4()), "text": "not in catalog"}},
        ],
    )

    result = await service.find_similar(
        tenant=TenantContext("tenant-1", "membership-1", "user-1", UserRole.USER),
        version_id="current-version",
        limit=50,
    )

    assert result["knowledgeBaseId"] == "kb-1"
    assert result["documents"] == [
        {
            "documentVersionId": "match-version",
            "documentId": "doc-match",
            "title": "Related policy",
            "lifecycleState": "READY",
            "score": 0.91,
            "preview": f"{('word ' * (MAX_PREVIEW_CHARS // 4 + 20)).strip()[:MAX_PREVIEW_CHARS - 1].rstrip()}…",
        }
    ]
    retrieval.retrieve.assert_awaited_once()
    assert retrieval.retrieve.await_args.kwargs["knowledge_base_ids"] == ("kb-1",)
    assert retrieval.retrieve.await_args.kwargs["active_generation_ids"] == ("generation-1",)
    assert retrieval.retrieve.await_args.kwargs["sparse_profile_id"] is None


@pytest.mark.asyncio
async def test_missing_text_returns_empty_without_embedding() -> None:
    current = _version(version_id="current-version", document_id="doc-current", text=" ", state=DocumentVersionLifecycleState.NEEDS_REVIEW)
    service, retrieval = _service(current, [(current, "Current", "doc-current")], [])

    result = await service.find_similar(
        tenant=TenantContext("tenant-1", "membership-1", "user-1", UserRole.USER),
        version_id="current-version",
    )

    assert result == {"versionId": "current-version", "documents": []}
    retrieval.retrieve.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_version_raises_tenant_safe_not_found() -> None:
    service, retrieval = _service(None, [], [])

    with pytest.raises(DomainError) as error:
        await service.find_similar(
            tenant=TenantContext("tenant-1", "membership-1", "user-1", UserRole.USER),
            version_id="missing-version",
        )

    assert error.value.status_code == 404
    retrieval.retrieve.assert_not_awaited()


@pytest.mark.asyncio
async def test_retrieval_error_is_allowed_to_reach_non_blocking_ui() -> None:
    current = _version(version_id="current-version", document_id="doc-current", text="current text", state=DocumentVersionLifecycleState.NEEDS_REVIEW)
    service, retrieval = _service(current, [(current, "Current", "doc-current")], [])
    retrieval.retrieve.side_effect = RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        await service.find_similar(
            tenant=TenantContext("tenant-1", "membership-1", "user-1", UserRole.USER),
            version_id="current-version",
        )
