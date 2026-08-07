from app.application.task_resumer import TaskResumer
from app.domain.rag.task_plan import TaskResult, TaskType


def test_resumer_merges_evidence_and_labels_supplementary_context() -> None:
    result = TaskResumer().resume([
        TaskResult("r1", TaskType.RAG, "success", rag=[{"id": "a", "score": 0.8, "source": "doc"}]),
        TaskResult("g1", TaskType.GENERAL, "success", general="context"),
    ], top_k=5)
    assert len(result.evidence) == 1
    assert "[Related context:]" in result.supplementary_context
    assert result.route == "grounded"


def test_resumer_abstains_without_successful_outputs() -> None:
    result = TaskResumer().resume([TaskResult("r1", TaskType.RAG, "error")], top_k=5)
    assert result.route == "abstain"
