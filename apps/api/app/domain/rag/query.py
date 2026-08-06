"""Deterministic query planning primitives; never accepts client security scope."""

from dataclasses import dataclass
from enum import StrEnum
from unicodedata import normalize


class QueryRoute(StrEnum):
    GROUNDED = "grounded"
    CLARIFY = "clarify"
    ABSTAIN = "abstain"


class EvidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass(frozen=True)
class EvidenceDecision:
    level: EvidenceLevel
    should_retry: bool
    route: QueryRoute


def gate_evidence(*, candidate_count: int, independent_source_count: int, top_score: float | None, retry_attempted: bool) -> EvidenceDecision:
    if candidate_count == 0 or top_score is None:
        return EvidenceDecision(EvidenceLevel.NONE, False, QueryRoute.ABSTAIN)
    if top_score >= 0.8 and independent_source_count >= 2:
        return EvidenceDecision(EvidenceLevel.HIGH, False, QueryRoute.GROUNDED)
    if top_score >= 0.5:
        return EvidenceDecision(EvidenceLevel.MEDIUM, not retry_attempted, QueryRoute.CLARIFY if retry_attempted else QueryRoute.GROUNDED)
    if top_score >= 0.25:
        return EvidenceDecision(EvidenceLevel.LOW, not retry_attempted, QueryRoute.GROUNDED)
    return EvidenceDecision(EvidenceLevel.LOW, False, QueryRoute.CLARIFY)


@dataclass(frozen=True)
class QueryPlan:
    original_query: str
    standalone_query: str
    route: QueryRoute
    reason: str | None


def normalize_query(message: str, *, max_chars: int) -> str:
    return " ".join(normalize("NFKC", message).split())[:max_chars]


def plan_query(message: str, *, max_chars: int, knowledge_base_ids: tuple[str, ...]) -> QueryPlan:
    normalized = normalize_query(message, max_chars=max_chars)
    if not normalized:
        return QueryPlan(message, normalized, QueryRoute.CLARIFY, "A question is required.")
    if not knowledge_base_ids:
        return QueryPlan(message, normalized, QueryRoute.ABSTAIN, "No authorized knowledge base was selected.")
    return QueryPlan(message, normalized, QueryRoute.GROUNDED, None)
