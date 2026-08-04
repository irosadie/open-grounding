"""Deterministic hybrid retrieval fusion and source-diverse selection."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalCandidate:
    chunk_id: str
    document_version_id: str
    source_id: str
    checksum: str | None
    dense_rank: int | None
    sparse_rank: int | None
    fused_score: float

    def trace(self) -> dict[str, object]:
        return {
            "chunkId": self.chunk_id,
            "documentVersionId": self.document_version_id,
            "sourceId": self.source_id,
            "denseRank": self.dense_rank,
            "sparseRank": self.sparse_rank,
            "fusedScore": self.fused_score,
        }


def fuse_rrf(
    *, dense: list[dict[str, object]], sparse: list[dict[str, object]], limit: int, rrf_k: int = 60
) -> list[RetrievalCandidate]:
    candidates: dict[tuple[str, str], RetrievalCandidate] = {}
    for rank, candidate in enumerate(dense, start=1):
        _merge_candidate(candidates, candidate, rank=rank, is_dense=True, rrf_k=rrf_k)
    for rank, candidate in enumerate(sparse, start=1):
        _merge_candidate(candidates, candidate, rank=rank, is_dense=False, rrf_k=rrf_k)
    return sorted(candidates.values(), key=lambda candidate: (-candidate.fused_score, candidate.chunk_id))[:limit]


def select_diverse(*, candidates: list[RetrievalCandidate], limit: int, max_per_source: int = 2) -> list[RetrievalCandidate]:
    selected: list[RetrievalCandidate] = []
    source_counts: dict[str, int] = {}
    seen_checksums: set[str] = set()
    for candidate in candidates:
        if candidate.checksum and candidate.checksum in seen_checksums:
            continue
        if source_counts.get(candidate.source_id, 0) >= max_per_source:
            continue
        selected.append(candidate)
        source_counts[candidate.source_id] = source_counts.get(candidate.source_id, 0) + 1
        if candidate.checksum:
            seen_checksums.add(candidate.checksum)
        if len(selected) == limit:
            break
    return selected


def _merge_candidate(
    candidates: dict[tuple[str, str], RetrievalCandidate],
    raw: dict[str, object],
    *,
    rank: int,
    is_dense: bool,
    rrf_k: int,
) -> None:
    chunk_id = str(raw["id"])
    document_version_id = str(raw["document_version_id"])
    key = (chunk_id, document_version_id)
    existing = candidates.get(key)
    dense_rank = rank if is_dense else existing.dense_rank if existing else None
    sparse_rank = existing.sparse_rank if is_dense and existing else rank if not is_dense else None
    score = (1 / (rrf_k + dense_rank) if dense_rank else 0) + (1 / (rrf_k + sparse_rank) if sparse_rank else 0)
    candidates[key] = RetrievalCandidate(
        chunk_id=chunk_id,
        document_version_id=document_version_id,
        source_id=str(raw["source_id"]),
        checksum=str(raw["checksum"]) if raw.get("checksum") is not None else None,
        dense_rank=dense_rank,
        sparse_rank=sparse_rank,
        fused_score=score,
    )
