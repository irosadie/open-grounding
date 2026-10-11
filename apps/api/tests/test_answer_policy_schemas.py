import pytest
from pydantic import ValidationError

from app.interfaces.http.schemas import AnswerBehaviorProfileRequest, GuardrailProfileRequest


def test_answer_behavior_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AnswerBehaviorProfileRequest(version="v1", unsupported="value")


def test_answer_behavior_request_rejects_ungrounded_strict_policy() -> None:
    with pytest.raises(ValidationError, match="ANSWER_UNGROUNDED"):
        AnswerBehaviorProfileRequest(
            version="v1",
            source_policy="DOCUMENT_ONLY",
            allow_mcp_sources=False,
        )


def test_guardrail_request_accepts_bounded_limits() -> None:
    result = GuardrailProfileRequest(
        version="g1",
        max_tool_calls=2,
        max_tool_timeout_seconds=10,
        max_tool_payload_bytes=65_536,
        max_mcp_freshness_seconds=60,
    )
    assert result.max_tool_calls == 2
