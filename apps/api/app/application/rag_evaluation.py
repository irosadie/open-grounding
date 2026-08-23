"""Deterministic labeled evaluation for grounded-query profile evidence."""

from dataclasses import dataclass
from time import monotonic
from typing import Protocol

from app.domain.errors import DomainError
from app.domain.tenant_context import TenantContext


@dataclass(frozen=True)
class EvaluationFixture:
    fixture_id: str
    expected_chunk_ids: frozenset[str]
    expected_citation_ids: frozenset[str]
    expects_abstention: bool


@dataclass(frozen=True)
class EvaluationObservation:
    retrieved_chunk_ids: frozenset[str]
    citation_ids: frozenset[str]
    is_grounded: bool
    route: str
    failed: bool = False


class EvaluationResultRepository(Protocol):
    async def upsert(self, *, tenant_id: str, profile_id: str, fixture_id: str, metrics: dict[str, float]) -> None: ...

    async def has_passing_result(self, *, tenant_id: str, profile_id: str) -> bool: ...


class RagEvaluationService:
    def __init__(self, results: EvaluationResultRepository) -> None:
        self._results = results

    async def run(
        self,
        *,
        tenant: TenantContext,
        profile_id: str,
        fixture: EvaluationFixture,
        observation: EvaluationObservation,
    ) -> dict[str, float]:
        started_at = monotonic()
        recall = _ratio(fixture.expected_chunk_ids.intersection(observation.retrieved_chunk_ids), fixture.expected_chunk_ids)
        citation_correctness = _ratio(fixture.expected_citation_ids.intersection(observation.citation_ids), observation.citation_ids)
        citation_coverage = _ratio(fixture.expected_citation_ids.intersection(observation.citation_ids), fixture.expected_citation_ids)
        abstention_quality = float((observation.route == "abstain") == fixture.expects_abstention)
        metrics = {
            "retrievalRecall": recall,
            "citationCorrectness": citation_correctness,
            "citationCoverage": citation_coverage,
            "groundedness": float(observation.is_grounded),
            "abstentionQuality": abstention_quality,
            "latencyMs": float(int((monotonic() - started_at) * 1_000)),
            "failureRate": float(observation.failed),
        }
        await self._results.upsert(tenant_id=tenant.tenant_id, profile_id=profile_id, fixture_id=fixture.fixture_id, metrics=metrics)
        return metrics

    async def require_passing_evidence(self, *, tenant: TenantContext, profile_id: str) -> None:
        if not await self._results.has_passing_result(tenant_id=tenant.tenant_id, profile_id=profile_id):
            raise DomainError("PROFILE_EVALUATION_REQUIRED", "A passing labeled evaluation is required before profile promotion.", 409)


def _ratio(numerator: frozenset[str], denominator: frozenset[str]) -> float:
    return len(numerator) / len(denominator) if denominator else 1.0
