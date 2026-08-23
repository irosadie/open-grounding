from app.domain.rag.retrieval import fuse_rrf, select_diverse


def _candidate(candidate_id: str, source_id: str, checksum: str | None = None) -> dict[str, object]:
    return {
        "id": candidate_id,
        "document_version_id": f"version-{candidate_id}",
        "source_id": source_id,
        "checksum": checksum,
    }


def test_rrf_fuses_overlapping_dense_and_sparse_candidates_deterministically() -> None:
    fused = fuse_rrf(
        dense=[_candidate("a", "source-1"), _candidate("b", "source-2")],
        sparse=[_candidate("b", "source-2"), _candidate("c", "source-3")],
        limit=3,
    )

    assert [candidate.chunk_id for candidate in fused] == ["b", "a", "c"]
    assert fused[0].dense_rank == 2
    assert fused[0].sparse_rank == 1
    assert fused[0].trace()["sourceId"] == "source-2"


def test_diversity_removes_duplicate_checksums_and_source_dominance() -> None:
    fused = fuse_rrf(
        dense=[
            _candidate("a", "source-1", "same"),
            _candidate("b", "source-1", "same"),
            _candidate("c", "source-1", "other"),
            _candidate("d", "source-1", "third"),
            _candidate("e", "source-2", "fourth"),
        ],
        sparse=[],
        limit=5,
    )

    selected = select_diverse(candidates=fused, limit=4, max_per_source=2)

    assert [candidate.chunk_id for candidate in selected] == ["a", "c", "e"]
