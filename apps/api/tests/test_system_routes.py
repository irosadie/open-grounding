from fastapi.testclient import TestClient

from app.main import create_app


def test_system_routes_keep_success_envelope() -> None:
    client = TestClient(create_app())

    root = client.get("/")
    health = client.get("/health")

    assert root.status_code == 200
    assert root.json()["success"] is True
    assert root.json()["data"]["name"] == "open-grounding-api"
    assert health.status_code == 200
    assert health.json()["data"]["status"] == "ok"


def test_validation_errors_use_api_envelope() -> None:
    client = TestClient(create_app())

    response = client.post("/auth/register", json={"email": "not-an-email"})

    assert response.status_code == 422
    assert response.json()["success"] is False
    assert response.json()["errors"][0]["code"] == "VALIDATION_ERROR"


def test_health_includes_tenant_diagnostics() -> None:
    client = TestClient(create_app())

    health = client.get("/health")

    assert health.status_code == 200
    data = health.json()["data"]
    assert "tenant" in data
    assert data["tenant"]["tenantMode"] == "single-deployment"
    assert "supportedModes" in data["tenant"]
    assert "single-deployment" in data["tenant"]["supportedModes"]


def test_client_tenant_header_is_ignored() -> None:
    """Client-supplied tenant headers must not affect server responses.

    The deployment tenant is derived from configuration, never from client
    headers. Even if a client sends X-Tenant-ID, the health endpoint must
    return the same deployment-tenant diagnostics.
    """
    client = TestClient(create_app())

    without_header = client.get("/health")
    with_header = client.get("/health", headers={"X-Tenant-ID": "00000000-0000-0000-0000-000000000000"})

    assert without_header.status_code == 200
    assert with_header.status_code == 200
    # The tenant diagnostics must be identical regardless of client headers.
    assert without_header.json()["data"]["tenant"] == with_header.json()["data"]["tenant"]


def test_client_tenant_query_param_is_ignored() -> None:
    """Client-supplied tenant query parameters must not affect server responses."""
    client = TestClient(create_app())

    without_param = client.get("/health")
    with_param = client.get("/health?tenantId=00000000-0000-0000-0000-000000000000")

    assert without_param.status_code == 200
    assert with_param.status_code == 200
    assert without_param.json()["data"]["tenant"] == with_param.json()["data"]["tenant"]


def test_tenant_context_endpoint_requires_auth() -> None:
    """The tenant context endpoint must reject unauthenticated requests."""
    client = TestClient(create_app())

    response = client.get("/auth/tenant/context")

    assert response.status_code == 401
    assert response.json()["success"] is False
    assert response.json()["errors"][0]["code"] == "UNAUTHORIZED"


def test_client_tenant_header_does_not_override_context() -> None:
    """Even with a conflicting X-Tenant-ID header, the tenant context endpoint
    must reject the request at the auth layer — the client cannot select a
    tenant.
    """
    client = TestClient(create_app())

    response = client.get(
        "/auth/tenant/context",
        headers={
            "X-Tenant-ID": "00000000-0000-0000-0000-000000000000",
            "X-Tenant-Slug": "attacker-tenant",
        },
    )

    # Without a valid bearer token, the request is rejected at the auth layer.
    # The client-supplied tenant headers are never read.
    assert response.status_code == 401
    assert response.json()["success"] is False
