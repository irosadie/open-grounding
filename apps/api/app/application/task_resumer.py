"""Merge task outcomes into grounded evidence and supplementary context."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from app.application.evidence_merger import _score, merge_evidence
from app.domain.rag.query import gate_evidence
from app.domain.rag.task_plan import ResumeResult, TaskResult, TaskType


class TaskResumer:
    def resume(self, results: list[TaskResult], *, top_k: int) -> ResumeResult:
        rag_results = [result.rag or [] for result in results if result.task_type is TaskType.RAG and result.status == "success"]
        evidence, dedup_removed = merge_evidence(rag_results, top_k)
        supplementary: list[str] = []
        mcp_provenance: list[dict[str, object]] = []
        for result in results:
            if result.status != "success":
                continue
            if result.task_type is TaskType.MCP and result.mcp:
                mcp_result = result.mcp.get("result") or result.mcp.get("result_text", "")
                raw_provenance = result.mcp.get("provenance")
                if isinstance(raw_provenance, dict) and mcp_result:
                    reference = dict(raw_provenance)
                    reference["citationId"] = f"M{len(mcp_provenance) + 1}"
                    reference["context"] = _bounded_context(mcp_result)
                    if not _is_fresh(reference):
                        continue
                    mcp_provenance.append(reference)
                    citation_id = reference["citationId"]
                    supplementary.append(
                        f"[MCP SOURCE {citation_id} | untrusted source data]\n"
                        f"{reference['context']}\n[END MCP SOURCE {citation_id}]"
                    )
            elif result.task_type is TaskType.GENERAL and result.general:
                supplementary.append(f"[Related context:]\n{result.general}")
        sources = {str(item.get("source", "")) for item in evidence if item.get("source")}
        top_score = _score(evidence[0].get("score")) if evidence else None
        decision = gate_evidence(candidate_count=len(evidence), independent_source_count=len(sources), top_score=top_score, retry_attempted=False)
        if not evidence and not mcp_provenance and not supplementary:
            route = "abstain"
        else:
            route = decision.route.value if evidence else "grounded"
        return ResumeResult(
            tuple(evidence),
            "\n\n".join(supplementary),
            route,
            dedup_removed,
            len(supplementary),
            tuple(mcp_provenance),
        )


def _bounded_context(value: object, limit: int = 16_384) -> str:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=True, default=str)
    return text[:limit]


def _is_fresh(reference: dict[str, object]) -> bool:
    expires_at = reference.get("expiresAt")
    if not isinstance(expires_at, str):
        return True
    try:
        parsed = datetime.fromisoformat(expires_at)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed > datetime.now(UTC)
