from uuid import uuid4

import pytest

from app.application.rag_reranking import RagRerankingService
from app.core.settings import Settings
from app.domain.models import UserRole
from app.domain.rag.query import EvidenceLevel, QueryRoute, gate_evidence
from app.domain.tenant_context import TenantContext


class RerankerStub:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def rerank(self, *, tenant: TenantContext, query: str, candidates: list[dict[str, object]], reranker_profile_id: str, top_k: int | None = None) -> list[dict[str, object]]:
        del tenant, query, reranker_profile_id, top_k
        if self.fail:
            raise RuntimeError("unavailable")
        return [*reversed(candidates), {"id": "unfiltered"}]


def _tenant() -> TenantContext:
    return TenantContext(tenant_id=str(uuid4()), membership_id=str(uuid4()), user_id=str(uuid4()), role=UserRole.USER)


@pytest.mark.asyncio
async def test_reranker_removes_unfiltered_candidates() -> None:
    service = RagRerankingService(Settings(_env_file=None), RerankerStub())
    candidates = [{"id": "a"}, {"id": "b"}]

    ranked, degraded = await service.rerank(tenant=_tenant(), query="q", candidates=candidates, profile_id="reranker-v1")

    assert ranked == [{"id": "b"}, {"id": "a"}]
    assert degraded is False


@pytest.mark.asyncio
async def test_reranker_failure_keeps_deterministic_fused_order() -> None:
    service = RagRerankingService(Settings(_env_file=None), RerankerStub(fail=True))
    candidates = [{"id": "a"}, {"id": "b"}]

    ranked, degraded = await service.rerank(tenant=_tenant(), query="q", candidates=candidates, profile_id="reranker-v1")

    assert ranked == candidates
    assert degraded is True


def test_evidence_gate_has_no_numeric_confidence_and_bounded_retry() -> None:
    high = gate_evidence(candidate_count=2, independent_source_count=2, top_score=0.9, retry_attempted=False)
    medium = gate_evidence(candidate_count=1, independent_source_count=1, top_score=0.6, retry_attempted=False)
    retried_medium = gate_evidence(candidate_count=1, independent_source_count=1, top_score=0.6, retry_attempted=True)
    none = gate_evidence(candidate_count=0, independent_source_count=0, top_score=None, retry_attempted=False)

    assert (high.level, high.route, high.should_retry) == (EvidenceLevel.HIGH, QueryRoute.GROUNDED, False)
    assert (medium.level, medium.should_retry) == (EvidenceLevel.MEDIUM, True)
    assert (retried_medium.route, retried_medium.should_retry) == (QueryRoute.CLARIFY, False)
    assert (none.level, none.route) == (EvidenceLevel.NONE, QueryRoute.ANSWERED)
