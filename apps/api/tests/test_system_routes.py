from fastapi.testclient import TestClient

from app.main import create_app


def test_system_routes_keep_success_envelope() -> None:
    client = TestClient(create_app())

    root = client.get("/")
    health = client.get("/health")

    assert root.status_code == 200
    assert root.json()["success"] is True
    assert root.json()["data"]["name"] == "vibecoding-starter-api"
    assert health.status_code == 200
    assert health.json()["data"]["status"] == "ok"


def test_validation_errors_use_api_envelope() -> None:
    client = TestClient(create_app())

    response = client.post("/auth/register", json={"email": "not-an-email"})

    assert response.status_code == 422
    assert response.json()["success"] is False
    assert response.json()["errors"][0]["code"] == "VALIDATION_ERROR"
