from app.application.retrieval_fusion import rrf_fuse


def _candidate(candidate_id: str) -> dict[str, object]:
    return {"id": candidate_id, "text": candidate_id}


def test_rrf_applies_band_weights() -> None:
    results = rrf_fuse([_candidate("dense")], [_candidate("sparse")], 1, 1.0, 2.0, 2)
    assert [result.id for result in results] == ["sparse", "dense"]


def test_rrf_uses_k_and_missing_band() -> None:
    results = rrf_fuse([_candidate("both"), _candidate("dense")], [_candidate("both")], 2, 1.0, 1.0, 3)
    assert results[0].score == 2 / 3
    assert results[1].score == 1 / 4


def test_rrf_caps_and_breaks_ties_by_id() -> None:
    results = rrf_fuse([_candidate("b")], [_candidate("a")], 60, 1.0, 1.0, 1)
    assert [result.id for result in results] == ["a"]
