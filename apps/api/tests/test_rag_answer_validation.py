from datetime import UTC, datetime, timedelta

import pytest

from app.application.rag_answer_validation import RagAnswerValidationService
from app.domain.models import ProvenanceKind
from app.domain.rag.answer import AnswerClaim, GroundedAnswer
from app.domain.rag.answer_validation import validate_answer
from app.domain.rag.evidence import Citation, EvidenceContext


def _evidence() -> EvidenceContext:
    return EvidenceContext("source", (Citation("S1", "chunk-1", "version-1", "Title", None, "source"),), 1)


def _answer(citation_id: str = "S1") -> GroundedAnswer:
    return GroundedAnswer((AnswerClaim("Fact", (citation_id,)),), (), (), ())


def test_validator_requires_valid_citations_and_material_claim_coverage() -> None:
    invalid = GroundedAnswer((AnswerClaim("Fact", ()),), (), (), ())
    validation = validate_answer(answer=invalid, evidence=_evidence())

    assert validation.is_valid is False
    assert validation.errors == ("Material claim lacks a citation",)


def test_validator_rejects_cross_trace_and_stale_mcp_provenance() -> None:
    citation = Citation(
        "M1",
        "",
        "",
        "MCP server/tool",
        "invocation-1",
        "live result",
        source_kind=ProvenanceKind.MCP,
        tenant_id="tenant-1",
        server_id="server-1",
        tool_id="tool-1",
        invocation_id="invocation-1",
        trace_id="trace-other",
        produced_at=datetime.now(UTC) - timedelta(minutes=2),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    validation = validate_answer(
        answer=_answer("M1"),
        evidence=EvidenceContext("mcp", (citation,), 1),
        tenant_id="tenant-1",
        trace_id="trace-current",
    )

    assert validation.is_valid is False
    assert "MCP citation belongs to another trace" in validation.errors
    assert "MCP citation is stale" in validation.errors


@pytest.mark.asyncio
async def test_validator_allows_one_repair_then_abstains_when_repair_stays_invalid() -> None:
    service = RagAnswerValidationService()
    calls = 0

    async def invalid_repair(errors: tuple[str, ...]) -> GroundedAnswer:
        nonlocal calls
        calls += 1
        assert errors == ("Claim references an unselected citation",)
        return _answer("S99")

    answer, validation, repaired = await service.validate_or_abstain(
        answer=_answer("S99"), evidence=_evidence(), repair=invalid_repair
    )

    assert answer is None
    assert validation.is_valid is False
    assert repaired is True
    assert calls == 1


@pytest.mark.asyncio
async def test_validator_returns_valid_repair() -> None:
    service = RagAnswerValidationService()

    async def valid_repair(_: tuple[str, ...]) -> GroundedAnswer:
        return _answer()

    answer, validation, repaired = await service.validate_or_abstain(
        answer=_answer("S99"), evidence=_evidence(), repair=valid_repair
    )

    assert answer == _answer()
    assert validation.is_valid is True
    assert repaired is True
