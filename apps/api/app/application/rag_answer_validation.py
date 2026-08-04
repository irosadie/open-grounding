"""One-repair answer validation workflow with safe abstention fallback."""

from collections.abc import Awaitable, Callable

from app.domain.rag.answer import GroundedAnswer
from app.domain.rag.answer_validation import AnswerValidation, validate_answer
from app.domain.rag.evidence import EvidenceContext

Repair = Callable[[tuple[str, ...]], Awaitable[GroundedAnswer]]


class RagAnswerValidationService:
    async def validate_or_abstain(
        self, *, answer: GroundedAnswer, evidence: EvidenceContext, repair: Repair | None
    ) -> tuple[GroundedAnswer | None, AnswerValidation, bool]:
        validation = validate_answer(answer=answer, evidence=evidence)
        if validation.is_valid:
            return answer, validation, False
        if repair is None:
            return None, validation, False
        repaired = await repair(validation.errors)
        repaired_validation = validate_answer(answer=repaired, evidence=evidence)
        return (repaired if repaired_validation.is_valid else None), repaired_validation, True
