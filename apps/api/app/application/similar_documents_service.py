"""Find tenant-scoped indexed documents related to a source under review."""

import asyncio
from typing import Protocol, TypedDict

from app.domain.errors import DomainError
from app.domain.rag.catalog import DocumentVersion
from app.domain.rag.repositories import (
    DocumentRepository,
    DocumentVersionRepository,
    IndexGenerationRepository,
    IndexProfileRepository,
)
from app.domain.tenant_context import TenantContext

MAX_RESULTS = 10
DEFAULT_RESULTS = 5
MAX_QUERY_CHARS = 12_000
MAX_PREVIEW_CHARS = 320


class RetrievalPort(Protocol):
    async def retrieve(
        self,
        *,
        tenant: TenantContext,
        query: str,
        collection: str,
        knowledge_base_ids: tuple[str, ...],
        active_generation_ids: tuple[str, ...],
        embedding_profile_id: str,
        sparse_profile_id: str | None = None,
        index_profile_id: str | None = None,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]: ...


class SimilarDocument(TypedDict):
    documentVersionId: str
    documentId: str
    title: str
    lifecycleState: str
    score: float
    preview: str


class SimilarDocumentsService:
    """Orchestrate read-only semantic similarity for a document version."""

    def __init__(
        self,
        versions: DocumentVersionRepository,
        documents: DocumentRepository,
        generations: IndexGenerationRepository,
        profiles: IndexProfileRepository,
        retrieval: RetrievalPort,
    ) -> None:
        self._versions = versions
        self._documents = documents
        self._generations = generations
        self._profiles = profiles
        self._retrieval = retrieval

    async def find_similar(
        self,
        *,
        tenant: TenantContext,
        version_id: str,
        limit: int = DEFAULT_RESULTS,
    ) -> dict[str, object]:
        version = await self._versions.find_by_id(tenant_id=tenant.tenant_id, version_id=version_id)
        if version is None:
            raise DomainError.not_found("Document version not found")

        bounded_limit = max(1, min(limit, MAX_RESULTS))
        if not version.parsed_text or not version.parsed_text.strip():
            return _empty_result(version)

        document = await self._documents.find_by_id(tenant_id=tenant.tenant_id, document_id=version.document_id)
        if document is None:
            raise DomainError.not_found("Document not found")

        knowledge_base_ids = (document.knowledge_base_id,)
        # Independent lookups run concurrently (bounded by event loop +
        # pool); latency ~= slowest, not sum. Fail-soft preserved below.
        generations, profile = await asyncio.gather(
            self._generations.find_active_for_knowledge_bases(
                tenant_id=tenant.tenant_id,
                knowledge_base_ids=knowledge_base_ids,
            ),
            self._profiles.find_active(tenant_id=tenant.tenant_id),
        )
        if not generations or profile is None:
            return _empty_result(version, knowledge_base_id=document.knowledge_base_id)

        dense_results, _ = await self._retrieval.retrieve(
            tenant=tenant,
            query=version.parsed_text[:MAX_QUERY_CHARS],
            collection=profile.collection,
            knowledge_base_ids=knowledge_base_ids,
            active_generation_ids=tuple(generation.id for generation in generations),
            embedding_profile_id=profile.embedding_profile_id,
            sparse_profile_id=None,
            index_profile_id=profile.id,
        )
        if not dense_results:
            return {
                "versionId": version.id,
                "knowledgeBaseId": document.knowledge_base_id,
                "documents": [],
            }
        wanted_ids = _collect_wanted_version_ids(dense_results, current_version_id=version.id)
        if not wanted_ids:
            return {
                "versionId": version.id,
                "knowledgeBaseId": document.knowledge_base_id,
                "documents": [],
            }
        catalog_rows = await _load_catalog_batch(
            self._versions,
            tenant_id=tenant.tenant_id,
            knowledge_base_id=document.knowledge_base_id,
            version_ids=tuple(wanted_ids),
        )
        catalog = {candidate.id: (candidate, title, document_id) for candidate, title, document_id in catalog_rows}
        grouped = _group_results(dense_results, current_version_id=version.id, catalog=catalog)
        matches = sorted(grouped.values(), key=lambda item: item["score"], reverse=True)[:bounded_limit]
        return {
            "versionId": version.id,
            "knowledgeBaseId": document.knowledge_base_id,
            "documents": matches,
        }


def _empty_result(version: DocumentVersion, *, knowledge_base_id: str | None = None) -> dict[str, object]:
    result: dict[str, object] = {"versionId": version.id, "documents": []}
    if knowledge_base_id is not None:
        result["knowledgeBaseId"] = knowledge_base_id
    return result


def _collect_wanted_version_ids(
    results: list[dict[str, object]],
    *,
    current_version_id: str,
) -> list[str]:
    """Extract unique candidate version ids from retrieval payloads (no DB I/O)."""
    wanted: list[str] = []
    seen: set[str] = set()
    for result in results:
        payload = result.get("payload")
        if not isinstance(payload, dict):
            continue
        version_id = payload.get("document_version_id")
        if not isinstance(version_id, str) or version_id == current_version_id or version_id in seen:
            continue
        seen.add(version_id)
        wanted.append(version_id)
    return wanted


async def _load_catalog_batch(
    versions: DocumentVersionRepository,
    *,
    tenant_id: str,
    knowledge_base_id: str,
    version_ids: tuple[str, ...],
) -> list[tuple[DocumentVersion, str, str]]:
    """Load only the wanted versions via batch lookup; bounded fallback preserves legacy repos."""
    loader = getattr(versions, "list_by_ids", None)
    if callable(loader):
        try:
            loaded = await loader(tenant_id=tenant_id, version_ids=version_ids)
        except TypeError:
            loaded = None
        if isinstance(loaded, list):
            return loaded
    fallback_rows = await versions.list_by_knowledge_base(  # type: ignore[call-arg]
        tenant_id=tenant_id,
        knowledge_base_id=knowledge_base_id,
        limit=200,
    )
    wanted_set = set(version_ids)
    return [row for row in fallback_rows if row[0].id in wanted_set]


def _group_results(
    results: list[dict[str, object]],
    *,
    current_version_id: str,
    catalog: dict[str, tuple[DocumentVersion, str, str]],
) -> dict[str, SimilarDocument]:
    grouped: dict[str, SimilarDocument] = {}
    for result in results:
        payload = result.get("payload")
        if not isinstance(payload, dict):
            continue
        version_id = payload.get("document_version_id")
        if not isinstance(version_id, str) or version_id == current_version_id or version_id not in catalog:
            continue
        score = result.get("score")
        if not isinstance(score, int | float):
            continue
        text = payload.get("text")
        preview = _preview(text if isinstance(text, str) else "")
        existing = grouped.get(version_id)
        if existing is not None and float(existing["score"]) >= float(score):
            continue
        version, title, document_id = catalog[version_id]
        grouped[version_id] = {
            "documentVersionId": version.id,
            "documentId": document_id,
            "title": title,
            "lifecycleState": version.lifecycle_state.value,
            "score": float(score),
            "preview": preview,
        }
    return grouped


def _preview(text: str) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= MAX_PREVIEW_CHARS:
        return normalized
    return f"{normalized[: MAX_PREVIEW_CHARS - 1].rstrip()}…"
