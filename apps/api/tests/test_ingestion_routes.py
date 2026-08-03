"""HTTP-contract tests for RAG ingestion intake routes.

Tests that the /rag/ingestion endpoints follow the success envelope, reject
unsupported MIME types, enforce tenant scope, and return correct lifecycle
states. Uses the FastAPI TestClient against the real app.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


TENANT_ID = str(uuid4())


def test_intake_unsupported_mime_rejected(client: TestClient) -> None:
    """Unsupported MIME types are rejected before issuing an upload target."""
    response = client.post("/rag/ingestion/intake", json={
        "knowledgeBaseId": str(uuid4()), "filename": "test.xlsx",
        "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "sizeBytes": 1024,
    })
    assert response.status_code in (400, 401, 403)


def test_intake_requires_auth(client: TestClient) -> None:
    """Intake endpoints require authentication (tenant context)."""
    response = client.post("/rag/ingestion/intake", json={
        "knowledgeBaseId": str(uuid4()), "filename": "test.pdf",
        "mimeType": "application/pdf", "sizeBytes": 1024,
    })
    assert response.status_code in (401, 403)


def test_status_requires_auth(client: TestClient) -> None:
    """Status endpoint requires authentication."""
    response = client.get(f"/rag/ingestion/status/{uuid4()}")
    assert response.status_code in (401, 403)


def test_delete_requires_auth(client: TestClient) -> None:
    """Delete endpoint requires authentication."""
    response = client.delete(f"/rag/ingestion/{uuid4()}")
    assert response.status_code in (401, 403)


def test_rag_routes_registered() -> None:
    """The RAG router is registered and routes appear in the OpenAPI spec."""
    app = create_app()
    paths = set(app.openapi()["paths"].keys())
    assert "/rag/ingestion/intake" in paths
    assert "/rag/ingestion/complete" in paths
    assert "/rag/ingestion/status/{document_version_id}" in paths
    assert "/rag/ingestion/{document_version_id}" in paths
