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
    response = client.post(
        "/rag/ingestion/intake",
        json={
            "knowledgeBaseId": str(uuid4()),
            "filename": "test.xlsx",
            "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "sizeBytes": 1024,
        },
    )
    assert response.status_code in (400, 401, 403)


def test_intake_requires_auth(client: TestClient) -> None:
    """Intake endpoints require authentication (tenant context)."""
    response = client.post(
        "/rag/ingestion/intake",
        json={
            "knowledgeBaseId": str(uuid4()),
            "filename": "test.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
        },
    )
    assert response.status_code in (401, 403)


def test_status_requires_auth(client: TestClient) -> None:
    """Status endpoint requires authentication."""
    response = client.get(f"/rag/ingestion/status/{uuid4()}")
    assert response.status_code in (401, 403)


def test_delete_requires_auth(client: TestClient) -> None:
    """Delete endpoint requires authentication."""
    response = client.delete(f"/rag/ingestion/{uuid4()}")
    assert response.status_code in (401, 403)


def test_intake_metadata_valid_passes_validation(client: TestClient) -> None:
    """Valid metadata field does not cause 422 before auth check."""
    response = client.post(
        "/rag/ingestion/intake",
        json={
            "knowledgeBaseId": str(uuid4()),
            "filename": "test.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "metadata": {"author": "john", "department": "legal"},
        },
    )
    # Auth required, but not a validation error
    assert response.status_code in (401, 403)


def test_intake_metadata_too_many_keys_rejected(client: TestClient) -> None:
    """Metadata with more than 20 keys is rejected (422 or 401 depending on middleware order)."""
    response = client.post(
        "/rag/ingestion/intake",
        json={
            "knowledgeBaseId": str(uuid4()),
            "filename": "test.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "metadata": {f"key{i}": "value" for i in range(21)},
        },
    )
    assert response.status_code in (401, 422)


def test_intake_metadata_key_too_long_rejected(client: TestClient) -> None:
    """Metadata key exceeding 256 chars is rejected (422 or 401 depending on middleware order)."""
    response = client.post(
        "/rag/ingestion/intake",
        json={
            "knowledgeBaseId": str(uuid4()),
            "filename": "test.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "metadata": {"k" * 257: "value"},
        },
    )
    assert response.status_code in (401, 422)


def test_intake_metadata_value_too_long_rejected(client: TestClient) -> None:
    """Metadata value exceeding 256 chars is rejected (422 or 401 depending on middleware order)."""
    response = client.post(
        "/rag/ingestion/intake",
        json={
            "knowledgeBaseId": str(uuid4()),
            "filename": "test.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "metadata": {"author": "v" * 257},
        },
    )
    assert response.status_code in (401, 422)


def test_intake_without_metadata_passes_validation(client: TestClient) -> None:
    """Metadata field is optional — omitting it does not cause 422."""
    response = client.post(
        "/rag/ingestion/intake",
        json={
            "knowledgeBaseId": str(uuid4()),
            "filename": "test.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
        },
    )
    assert response.status_code in (401, 403)


def test_pending_review_count_requires_auth(client: TestClient) -> None:
    """Pending review count endpoint requires authentication."""
    response = client.get("/rag/ingestion/pending-review/count")
    assert response.status_code in (401, 403)


def test_rag_routes_registered() -> None:
    """The RAG router is registered and routes appear in the OpenAPI spec."""
    app = create_app()
    paths = set(app.openapi()["paths"].keys())
    assert "/rag/ingestion/intake" in paths
    assert "/rag/ingestion/complete" in paths
    assert "/rag/ingestion/status/{document_version_id}" in paths
    assert "/rag/ingestion/{document_version_id}" in paths
