from uuid import uuid4

import pytest

from app.application.rag_reranking import RagRerankingService
from app.core.settings import Settings
from app.domain.models import UserRole
from app.domain.rag.policy import qdrant_policy_filter
from app.domain.rag.query import EvidenceLevel, QueryRoute, gate_evidence
from app.domain.rag.retrieval import fuse_rrf, select_diverse
from app.domain.tenant_context import TenantContext


class FailingReranker:
    async def rerank(
        self,
        *,
        tenant: TenantContext,
        query: str,
        candidates: list[dict[str, object]],
        reranker_profile_id: str,
        top_k: int | None = None,
    ) -> list[dict[str, object]]:
        del tenant, query, candidates, reranker_profile_id, top_k
        raise RuntimeError("adapter unavailable")


def _tenant() -> TenantContext:
    return TenantContext(
        tenant_id=str(uuid4()),
        membership_id=str(uuid4()),
        user_id=str(uuid4()),
        role=UserRole.USER,
    )


def _candidate(candidate_id: str, source_id: str, checksum: str) -> dict[str, object]:
    return {
        "id": candidate_id,
        "document_version_id": f"version-{candidate_id}",
        "source_id": source_id,
        "checksum": checksum,
    }


def test_retrieval_policy_filter_cannot_escape_acl_classification_or_time_scope() -> None:
    tenant = _tenant()

    filter_value = qdrant_policy_filter(
        tenant=tenant,
        knowledge_base_ids=("kb-1",),
        active_generation_ids=("generation-1",),
    )

    conditions = filter_value["must"]
    assert conditions[0] == {"key": "tenant_id", "match": {"value": tenant.tenant_id}}
    assert conditions[3] == {"key": "classification", "match": {"any": ["PUBLIC", "INTERNAL"]}}
    assert conditions[4]["should"][0]["match"]["any"] == [f"user:{tenant.user_id}", "role:USER"]
    assert conditions[5]["should"][0]["key"] == "effective_from"
    assert conditions[6]["should"][0]["key"] == "effective_to"


@pytest.mark.asyncio
async def test_hybrid_overlap_diversity_and_reranker_failure_preserve_safe_candidates() -> None:
    dense = [_candidate("a", "source-1", "same"), _candidate("b", "source-1", "other")]
    sparse = [_candidate("b", "source-1", "other"), _candidate("c", "source-2", "third")]
    fused = fuse_rrf(dense=dense, sparse=sparse, limit=3)
    diverse = select_diverse(candidates=fused, limit=3, max_per_source=1)
    fallback, degraded = await RagRerankingService(Settings(_env_file=None), FailingReranker()).rerank(
        tenant=_tenant(),
        query="question",
        candidates=[candidate.trace() | {"id": candidate.chunk_id} for candidate in diverse],
        profile_id="reranker-v1",
    )

    assert [candidate.chunk_id for candidate in fused] == ["b", "a", "c"]
    assert [candidate.chunk_id for candidate in diverse] == ["b", "c"]
    assert [candidate["id"] for candidate in fallback] == ["b", "c"]
    assert degraded is True


def test_low_evidence_is_answered_without_numeric_confidence() -> None:
    low = gate_evidence(candidate_count=1, independent_source_count=1, top_score=0.2, retry_attempted=False)
    none = gate_evidence(candidate_count=0, independent_source_count=0, top_score=None, retry_attempted=False)

    assert (low.level, low.route, low.should_retry) == (EvidenceLevel.LOW, QueryRoute.ANSWERED, False)
    assert (none.level, none.route, none.should_retry) == (EvidenceLevel.NONE, QueryRoute.ANSWERED, False)
