"""One-repair answer validation workflow with safe abstention fallback."""

from collections.abc import Awaitable, Callable

from app.domain.rag.answer import GroundedAnswer
from app.domain.rag.answer_validation import AnswerValidation, validate_answer
from app.domain.rag.evidence import EvidenceContext

Repair = Callable[[tuple[str, ...]], Awaitable[GroundedAnswer]]


class RagAnswerValidationService:
    async def validate_or_abstain(
        self,
        *,
        answer: GroundedAnswer,
        evidence: EvidenceContext,
        repair: Repair | None,
        tenant_id: str | None = None,
        trace_id: str | None = None,
    ) -> tuple[GroundedAnswer | None, AnswerValidation, bool]:
        validation = validate_answer(answer=answer, evidence=evidence, tenant_id=tenant_id, trace_id=trace_id)
        if validation.is_valid:
            return answer, validation, False
        if repair is None:
            return None, validation, False
        try:
            repaired = await repair(validation.errors)
        except Exception:
            return None, validation, True
        repaired_validation = validate_answer(
            answer=repaired,
            evidence=evidence,
            tenant_id=tenant_id,
            trace_id=trace_id,
        )
        return (repaired if repaired_validation.is_valid else None), repaired_validation, True
