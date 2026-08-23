"""Evidence merger for query decomposition.

Deduplicates and merges evidence chunks from multiple sub-query retrievals.
Dedup by chunk ID (exact match), rank by max relevance score, cap at top_k.
"""

from __future__ import annotations


def merge_evidence(
    sub_results: list[list[dict[str, object]]],
    top_k: int,
) -> tuple[list[dict[str, object]], int]:
    """Merge evidence from multiple sub-query retrievals.

    Args:
        sub_results: List of retrieval result lists, one per sub-query.
                     Each item is a list of chunk dicts with at least 'id' and 'score'.
        top_k: Maximum number of chunks to return after merge.

    Returns:
        Tuple of (merged_chunks, dedup_removed_count).
    """
    seen: dict[str, dict[str, object]] = {}

    for result_list in sub_results:
        for chunk in result_list:
            chunk_id = str(chunk.get("id", ""))
            if not chunk_id:
                continue
            if chunk_id not in seen:
                seen[chunk_id] = dict(chunk)
            else:
                # Keep highest score across sub-queries
                existing_score = float(seen[chunk_id].get("score", 0.0))
                new_score = float(chunk.get("score", 0.0))
                if new_score > existing_score:
                    seen[chunk_id] = dict(chunk)

    total_raw = sum(len(r) for r in sub_results)
    dedup_removed = total_raw - len(seen)

    # Sort by score descending
    merged = sorted(seen.values(), key=lambda c: float(c.get("score", 0.0)), reverse=True)

    return merged[:top_k], max(dedup_removed, 0)
