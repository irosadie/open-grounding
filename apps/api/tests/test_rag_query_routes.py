from uuid import uuid4

from fastapi.testclient import TestClient

from app.domain.models import UserRole
from app.domain.tenant_context import TenantContext
from app.interfaces.http.dependencies import get_rag_query_service, get_tenant_context
from app.main import create_app


class QueryServiceStub:
    def __init__(self, result: dict[str, object] | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.result = result

    async def query(
        self,
        *,
        tenant: TenantContext,
        message: str,
        knowledge_base_ids: tuple[str, ...],
        conversation_id: str | None,
        decomposition_enabled: bool | None = None,
        decomposition_max_sub_queries: int | None = None,
        memory_enabled: bool | None = None,
        session: object = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "tenantId": tenant.tenant_id,
                "message": message,
                "knowledgeBaseIds": knowledge_base_ids,
                "conversationId": conversation_id,
            }
        )
        return self.result or {
            "answer": None,
            "route": "abstain",
            "evidenceLevel": "none",
            "citations": [],
            "limitations": ["No requested knowledge base is available to this tenant."],
            "traceId": str(uuid4()),
            "decomposition": None,
            "memory": None,
        }


def _query_client() -> tuple[TestClient, QueryServiceStub]:
    app = create_app()
    tenant = TenantContext(
        tenant_id=str(uuid4()),
        membership_id=str(uuid4()),
        user_id=str(uuid4()),
        role=UserRole.USER,
    )
    service = QueryServiceStub()
    app.dependency_overrides[get_tenant_context] = lambda: tenant
    app.dependency_overrides[get_rag_query_service] = lambda: service
    return TestClient(app), service


def test_query_route_rejects_scope_override_before_service_execution() -> None:
    client, service = _query_client()

    response = client.post(
        "/rag/query",
        json={"message": "question", "knowledge_base_ids": ["kb-1"], "tenant_id": "attacker"},
    )

    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "VALIDATION_ERROR"
    assert service.calls == []


def test_query_route_returns_safe_policy_denial_without_filter_details() -> None:
    client, service = _query_client()

    response = client.post("/rag/query", json={"message": "question", "knowledge_base_ids": ["kb-1"]})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["route"] == "abstain"
    assert data["citations"] == []
    assert "filter" not in str(data).lower()
    assert service.calls[0]["knowledgeBaseIds"] == ("kb-1",)


def test_query_route_requires_auth_without_dependency_override() -> None:
    client = TestClient(create_app())

    response = client.post("/rag/query", json={"message": "question", "knowledge_base_ids": ["kb-1"]})

    assert response.status_code == 401
    assert response.json()["errors"][0]["code"] == "UNAUTHORIZED"


def test_stream_query_emits_only_final_safe_events_in_order() -> None:
    client, _ = _query_client()

    response = client.post("/rag/query", json={"message": "question", "knowledge_base_ids": ["kb-1"], "stream": True})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert [line.removeprefix("event: ") for line in response.text.splitlines() if line.startswith("event: ")] == [
        "response.started",
        "response.route",
        "response.retrieval_summary",
        "response.citations",
        "response.completed",
    ]
    assert "mandatoryFilter" not in response.text
    assert "filter" not in response.text.lower()


def test_stream_query_emits_answer_delta_only_as_final_response_content() -> None:
    client, service = _query_client()
    service.result = {
        "answer": {"facts": [{"text": "Supported fact", "citationIds": ["S1"], "isInference": False}]},
        "route": "grounded",
        "evidenceLevel": "high",
        "citations": [{"citationId": "S1", "title": "Title"}],
        "limitations": [],
        "traceId": str(uuid4()),
    }

    response = client.post("/rag/query", json={"message": "question", "knowledge_base_ids": ["kb-1"], "stream": True})

    events = [line.removeprefix("event: ") for line in response.text.splitlines() if line.startswith("event: ")]
    assert events == [
        "response.started",
        "response.route",
        "response.retrieval_summary",
        "response.delta",
        "response.citations",
        "response.completed",
    ]
    assert "Supported fact" in response.text
