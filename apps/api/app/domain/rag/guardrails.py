"""Small, provider-independent safety guardrails for query conversations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailDecision:
    allowed: bool
    code: str | None = None
    reason: str | None = None


_PROTECTED_REQUEST_PATTERNS = (
    "ignore all previous instructions",
    "ignore previous instructions",
    "reveal the system prompt",
    "show me the system prompt",
    "provide your api key",
    "show me your api key",
    "tell me the password",
    "expose your secrets",
)

_REFUSAL_REASON = "This request cannot be answered because it violates the safety guardrails."


def evaluate_query(message: str) -> GuardrailDecision:
    return _evaluate_text(message)


def evaluate_answer(answer: str) -> GuardrailDecision:
    return _evaluate_text(answer)


def _evaluate_text(text: str) -> GuardrailDecision:
    normalized = " ".join(text.casefold().split())
    if any(pattern in normalized for pattern in _PROTECTED_REQUEST_PATTERNS):
        return GuardrailDecision(allowed=False, code="POLICY_REFUSAL", reason=_REFUSAL_REASON)
    return GuardrailDecision(allowed=True)
