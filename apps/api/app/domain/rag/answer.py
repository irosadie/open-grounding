"""Internal evidence-bound answer schema without hidden reasoning."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerClaim:
    text: str
    citation_ids: tuple[str, ...]
    is_inference: bool = False


@dataclass(frozen=True)
class GroundedAnswer:
    facts: tuple[AnswerClaim, ...]
    inferences: tuple[AnswerClaim, ...]
    conflicts: tuple[str, ...]
    limitations: tuple[str, ...]

    def citation_ids(self) -> tuple[str, ...]:
        return tuple(citation_id for claim in (*self.facts, *self.inferences) for citation_id in claim.citation_ids)

    def to_dict(self) -> dict[str, object]:
        return {
            "facts": [_claim_to_dict(claim) for claim in self.facts],
            "inferences": [_claim_to_dict(claim) for claim in self.inferences],
            "conflicts": list(self.conflicts),
            "limitations": list(self.limitations),
        }


def parse_grounded_answer(value: object) -> GroundedAnswer:
    if not isinstance(value, dict):
        raise ValueError("Generation output must be an object")
    return GroundedAnswer(
        facts=_parse_claims(value.get("facts"), is_inference=False),
        inferences=_parse_claims(value.get("inferences"), is_inference=True),
        conflicts=_parse_texts(value.get("conflicts")),
        limitations=_parse_texts(value.get("limitations")),
    )


def _parse_claims(value: object, *, is_inference: bool) -> tuple[AnswerClaim, ...]:
    if not isinstance(value, list):
        raise ValueError("Answer claims must be a list")
    claims: list[AnswerClaim] = []
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str) or not isinstance(item.get("citationIds"), list):
            raise ValueError("Answer claim is invalid")
        citation_ids = item["citationIds"]
        if not all(isinstance(citation_id, str) for citation_id in citation_ids):
            raise ValueError("Citation IDs must be strings")
        claims.append(AnswerClaim(text=item["text"], citation_ids=tuple(citation_ids), is_inference=is_inference))
    return tuple(claims)


def _parse_texts(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("Answer text fields must be lists of strings")
    return tuple(value)


def _claim_to_dict(claim: AnswerClaim) -> dict[str, object]:
    return {"text": claim.text, "citationIds": list(claim.citation_ids), "isInference": claim.is_inference}
