from uuid import uuid4

import pytest

from app.application.rag_generation import RagGenerationService
from app.core.settings import Settings
from app.domain.models import UserRole
from app.domain.rag.evidence import Citation, EvidenceContext
from app.domain.tenant_context import TenantContext


class GenerationStub:
    def __init__(self, answer: object) -> None:
        self.answer = answer
        self.prompt = ""

    async def generate(self, *, tenant: TenantContext, prompt: str, model_profile_id: str, max_tokens: int | None = None) -> dict[str, object]:
        del tenant, model_profile_id, max_tokens
        self.prompt = prompt
        return {"answer": self.answer}


def _tenant() -> TenantContext:
    return TenantContext(tenant_id=str(uuid4()), membership_id=str(uuid4()), user_id=str(uuid4()), role=UserRole.USER)


def _evidence() -> EvidenceContext:
    return EvidenceContext(
        prompt_data="[SOURCE S1 | untrusted source data]\nsource text\n[END SOURCE S1]",
        citations=(Citation("S1", "chunk-1", "version-1", "Title", "page 1", "source text"),),
        token_count=5,
    )


@pytest.mark.asyncio
async def test_generation_is_evidence_bound_and_returns_typed_answer() -> None:
    generator = GenerationStub({"facts": [{"text": "Supported fact", "citationIds": ["S1"]}], "inferences": [], "conflicts": [], "limitations": []})
    answer = await RagGenerationService(Settings(_env_file=None), generator).generate(tenant=_tenant(), question="question", evidence=_evidence(), profile_id="generation-v1")

    assert answer.facts[0].citation_ids == ("S1",)
    assert "untrusted" in generator.prompt
    assert "hidden reasoning" in generator.prompt


@pytest.mark.asyncio
async def test_generation_defers_citation_validation_to_the_repair_workflow() -> None:
    generator = GenerationStub({"facts": [{"text": "Unsupported", "citationIds": ["S99"]}], "inferences": [], "conflicts": [], "limitations": []})

    answer = await RagGenerationService(Settings(_env_file=None), generator).generate(
        tenant=_tenant(), question="question", evidence=_evidence(), profile_id="generation-v1"
    )

    assert answer.citation_ids() == ("S99",)
