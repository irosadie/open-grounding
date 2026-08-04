import pytest

from app.application.rag_evaluation import EvaluationFixture, EvaluationObservation, RagEvaluationService
from app.application.rag_profile_promotion import RagProfilePromotionService
from app.domain.errors import DomainError
from app.domain.models import UserRole
from app.domain.tenant_context import TenantContext


class ResultsStub:
    def __init__(self) -> None:
        self.metrics: dict[str, float] | None = None
        self.passing = False

    async def upsert(self, *, tenant_id: str, profile_id: str, fixture_id: str, metrics: dict[str, float]) -> None:
        assert (tenant_id, profile_id, fixture_id) == ("tenant-1", "profile-v2", "fixture-1")
        self.metrics = metrics

    async def has_passing_result(self, *, tenant_id: str, profile_id: str) -> bool:
        assert (tenant_id, profile_id) == ("tenant-1", "profile-v2")
        return self.passing


class IndexProfilesStub:
    def __init__(self) -> None:
        self.activated: tuple[str, str] | None = None

    async def activate(self, *, tenant_id: str, profile_id: str):
        from app.domain.rag.profiles import IndexProfile

        self.activated = (tenant_id, profile_id)
        return IndexProfile(profile_id, "embedding-1", None, "rag", 768, "cosine", "2", is_active=True)


def _tenant() -> TenantContext:
    return TenantContext(tenant_id="tenant-1", membership_id="membership-1", user_id="user-1", role=UserRole.ADMIN)


@pytest.mark.asyncio
async def test_labeled_fixture_runner_records_grounded_quality_metrics() -> None:
    results = ResultsStub()
    metrics = await RagEvaluationService(results).run(
        tenant=_tenant(),
        profile_id="profile-v2",
        fixture=EvaluationFixture("fixture-1", frozenset({"chunk-1", "chunk-2"}), frozenset({"S1"}), False),
        observation=EvaluationObservation(frozenset({"chunk-1", "chunk-2"}), frozenset({"S1"}), True, "grounded"),
    )

    assert metrics["retrievalRecall"] == 1.0
    assert metrics["citationCorrectness"] == 1.0
    assert metrics["citationCoverage"] == 1.0
    assert metrics["groundedness"] == 1.0
    assert metrics["abstentionQuality"] == 1.0
    assert metrics["failureRate"] == 0.0
    assert results.metrics == metrics


@pytest.mark.asyncio
async def test_advanced_profile_promotion_requires_passing_labeled_evidence() -> None:
    results = ResultsStub()
    service = RagEvaluationService(results)

    with pytest.raises(DomainError, match="passing labeled evaluation"):
        await service.require_passing_evidence(tenant=_tenant(), profile_id="profile-v2")

    results.passing = True
    await service.require_passing_evidence(tenant=_tenant(), profile_id="profile-v2")


@pytest.mark.asyncio
async def test_promotion_cannot_activate_a_profile_before_evaluation_passes() -> None:
    results = ResultsStub()
    profiles = IndexProfilesStub()
    service = RagProfilePromotionService(RagEvaluationService(results), profiles)

    with pytest.raises(DomainError, match="passing labeled evaluation"):
        await service.promote(tenant=_tenant(), profile_id="profile-v2")
    assert profiles.activated is None

    results.passing = True
    assert await service.promote(tenant=_tenant(), profile_id="profile-v2") == {"profileId": "profile-v2", "isActive": True}
    assert profiles.activated == ("tenant-1", "profile-v2")
