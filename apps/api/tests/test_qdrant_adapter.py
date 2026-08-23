import json
from uuid import uuid4

import httpx
import pytest

from app.core.settings import Settings
from app.domain.models import UserRole
from app.domain.tenant_context import TenantContext
from app.infrastructure.qdrant import QdrantVectorStoreAdapter


def _tenant() -> TenantContext:
    return TenantContext(tenant_id=str(uuid4()), membership_id=str(uuid4()), user_id=str(uuid4()), role=UserRole.USER)


@pytest.mark.asyncio
async def test_provision_payload_indexes_covers_mandatory_retrieval_fields() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"status": "ok"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = QdrantVectorStoreAdapter(Settings(_env_file=None), client)
        await adapter.provision_payload_indexes(collection="rag-test")

    assert {_request_body(request)["field_name"] for request in requests} == {
        "tenant_id",
        "knowledge_base_id",
        "generation_id",
        "classification",
        "acl_principals",
        "effective_from",
        "effective_to",
    }


@pytest.mark.asyncio
async def test_search_and_delete_apply_tenant_filter() -> None:
    requests: list[httpx.Request] = []
    tenant = _tenant()

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"result": {"points": []}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = QdrantVectorStoreAdapter(Settings(_env_file=None), client)
        await adapter.search(tenant=tenant, collection="rag-test", vector=[0.1], limit=1)
        await adapter.delete_points(tenant=tenant, collection="rag-test", document_version_id="version-1")

    search_filter = _request_body(requests[0])["filter"]["must"]
    delete_filter = _request_body(requests[1])["filter"]["must"]
    assert search_filter == [{"key": "tenant_id", "match": {"value": tenant.tenant_id}}]
    assert delete_filter[0] == {"key": "tenant_id", "match": {"value": tenant.tenant_id}}
    assert delete_filter[1] == {"key": "document_version_id", "match": {"value": "version-1"}}


@pytest.mark.asyncio
async def test_permitted_search_builds_full_server_derived_policy_filter() -> None:
    requests: list[httpx.Request] = []
    tenant = _tenant()

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"result": {"points": []}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = QdrantVectorStoreAdapter(Settings(_env_file=None), client)
        await adapter.search_permitted(
            tenant=tenant,
            collection="rag-test",
            vector=[0.1],
            limit=1,
            knowledge_base_ids=("kb-1",),
            active_generation_ids=("generation-1",),
        )

    filter_value = _request_body(requests[0])["filter"]["must"]
    assert filter_value[0] == {"key": "tenant_id", "match": {"value": tenant.tenant_id}}
    assert filter_value[1] == {"key": "knowledge_base_id", "match": {"any": ["kb-1"]}}
    assert filter_value[2] == {"key": "generation_id", "match": {"any": ["generation-1"]}}


def _request_body(request: httpx.Request) -> dict[str, object]:
    return json.loads(request.content)
