"""Unit tests for evidence_merger."""

from app.application.evidence_merger import merge_evidence


def test_empty_results_returns_empty() -> None:
    result, removed = merge_evidence([], top_k=10)
    assert result == []
    assert removed == 0


def test_single_sub_query_returns_capped() -> None:
    chunks = [{"id": f"c{i}", "score": float(i)} for i in range(10)]
    result, removed = merge_evidence([chunks], top_k=5)
    assert len(result) == 5
    assert removed == 0


def test_dedup_by_chunk_id() -> None:
    chunk = {"id": "c1", "score": 0.8}
    result, removed = merge_evidence([[chunk], [chunk]], top_k=10)
    assert len(result) == 1
    assert removed == 1


def test_keeps_max_score_on_dedup() -> None:
    chunk_low = {"id": "c1", "score": 0.5}
    chunk_high = {"id": "c1", "score": 0.9}
    result, _ = merge_evidence([[chunk_low], [chunk_high]], top_k=10)
    assert result[0]["score"] == 0.9


def test_sorted_by_score_descending() -> None:
    sub1 = [{"id": "c1", "score": 0.3}, {"id": "c2", "score": 0.9}]
    sub2 = [{"id": "c3", "score": 0.6}]
    result, _ = merge_evidence([sub1, sub2], top_k=10)
    scores = [float(c["score"]) for c in result]
    assert scores == sorted(scores, reverse=True)


def test_top_k_cap_applied() -> None:
    sub1 = [{"id": f"a{i}", "score": float(i)} for i in range(5)]
    sub2 = [{"id": f"b{i}", "score": float(i)} for i in range(5)]
    result, _ = merge_evidence([sub1, sub2], top_k=3)
    assert len(result) == 3


def test_dedup_removed_count_correct() -> None:
    shared = {"id": "shared", "score": 0.5}
    unique1 = {"id": "u1", "score": 0.3}
    unique2 = {"id": "u2", "score": 0.4}
    result, removed = merge_evidence([[shared, unique1], [shared, unique2]], top_k=10)
    assert len(result) == 3
    assert removed == 1


def test_chunks_without_id_are_skipped() -> None:
    chunks = [{"score": 0.9}, {"id": "c1", "score": 0.5}]
    result, _ = merge_evidence([chunks], top_k=10)
    assert len(result) == 1
    assert result[0]["id"] == "c1"


def test_multiple_sub_queries_merged_correctly() -> None:
    sub1 = [{"id": "a", "score": 0.9}, {"id": "b", "score": 0.7}]
    sub2 = [{"id": "b", "score": 0.8}, {"id": "c", "score": 0.6}]
    sub3 = [{"id": "d", "score": 0.5}]
    result, removed = merge_evidence([sub1, sub2, sub3], top_k=10)
    assert len(result) == 4
    assert removed == 1
    # b should have score 0.8 (max from sub2)
    b_chunk = next(c for c in result if c["id"] == "b")
    assert b_chunk["score"] == 0.8
