"""Deterministic validation for evidence-bound generated answers."""

from dataclasses import dataclass

from app.domain.rag.answer import GroundedAnswer
from app.domain.rag.evidence import EvidenceContext


@dataclass(frozen=True)
class AnswerValidation:
    is_valid: bool
    errors: tuple[str, ...]


def validate_answer(*, answer: GroundedAnswer, evidence: EvidenceContext) -> AnswerValidation:
    allowed_citations = {citation.citation_id for citation in evidence.citations}
    errors: list[str] = []
    for claim in (*answer.facts, *answer.inferences):
        if not claim.text.strip():
            errors.append("Claim text is empty")
        if not claim.citation_ids:
            errors.append("Material claim lacks a citation")
        elif not set(claim.citation_ids).issubset(allowed_citations):
            errors.append("Claim references an unselected citation")
    facts = {claim.text.casefold() for claim in answer.facts}
    inferences = {claim.text.casefold() for claim in answer.inferences}
    if facts.intersection(inferences):
        errors.append("A claim cannot be both fact and inference")
    if any(_contains_disallowed_policy_text(text) for text in (*answer.conflicts, *answer.limitations)):
        errors.append("Answer contains disallowed policy output")
    return AnswerValidation(is_valid=not errors, errors=tuple(errors))


def _contains_disallowed_policy_text(text: str) -> bool:
    normalized = text.casefold()
    return "system prompt" in normalized or "api key" in normalized or "password" in normalized
