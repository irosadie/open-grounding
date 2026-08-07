"""Merge task outcomes into grounded evidence and supplementary context."""

from __future__ import annotations

from app.application.evidence_merger import merge_evidence
from app.domain.rag.query import gate_evidence
from app.domain.rag.task_plan import ResumeResult, TaskResult, TaskType


class TaskResumer:
    def resume(self, results: list[TaskResult], *, top_k: int) -> ResumeResult:
        rag_results = [result.rag or [] for result in results if result.task_type is TaskType.RAG and result.status == "success"]
        evidence, dedup_removed = merge_evidence(rag_results, top_k)
        supplementary: list[str] = []
        for result in results:
            if result.status != "success":
                continue
            if result.task_type is TaskType.MCP and result.mcp:
                supplementary.append(f"[Live tool results:]\n{result.mcp.get('result_text', '')}")
            elif result.task_type is TaskType.GENERAL and result.general:
                supplementary.append(f"[Related context:]\n{result.general}")
        sources = {str(item.get("source", "")) for item in evidence if item.get("source")}
        top_score = float(evidence[0].get("score", 0.0)) if evidence else None
        decision = gate_evidence(candidate_count=len(evidence), independent_source_count=len(sources), top_score=top_score, retry_attempted=False)
        if not evidence and not supplementary:
            route = "abstain"
        else:
            route = decision.route.value if evidence else "grounded"
        return ResumeResult(tuple(evidence), "\n\n".join(supplementary), route, dedup_removed, len(supplementary))
