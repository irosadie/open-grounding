"""Score-agnostic Reciprocal Rank Fusion for retrieval candidates."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FusedRetrievalResult:
    id: str
    score: float
    candidate: dict[str, object]


def rrf_fuse(
    dense: list[dict[str, object]],
    sparse: list[dict[str, object]],
    k: int,
    dense_weight: float,
    sparse_weight: float,
    cap: int,
) -> list[FusedRetrievalResult]:
    scores: dict[str, float] = {}
    candidates: dict[str, dict[str, object]] = {}
    for weight, results in ((dense_weight, dense), (sparse_weight, sparse)):
        for rank, candidate in enumerate(results, start=1):
            candidate_id = str(candidate.get("id", ""))
            if not candidate_id:
                continue
            scores[candidate_id] = scores.get(candidate_id, 0.0) + weight / (k + rank)
            candidates.setdefault(candidate_id, candidate)
    fused = [FusedRetrievalResult(id=candidate_id, score=score, candidate=candidates[candidate_id]) for candidate_id, score in scores.items()]
    fused.sort(key=lambda result: (-result.score, result.id))
    return fused[:cap]
