"""Minimal Qdrant REST adapter for tenant-scoped RAG vectors."""

import asyncio
import random

import httpx

from app.core.settings import Settings
from app.domain.rag.policy import qdrant_policy_filter
from app.domain.rag.tenant_namespace import TenantNamespace
from app.domain.tenant_context import TenantContext

_PAYLOAD_INDEXES = {
    "tenant_id": "keyword",
    "knowledge_base_id": "keyword",
    "generation_id": "keyword",
    "classification": "keyword",
    "acl_principals": "keyword",
    "effective_from": "datetime",
    "effective_to": "datetime",
}

_QUERY_TIMEOUT_S = 8.0
_PROVISION_TIMEOUT_S = 8.0
_RETRY_JITTER_S = 0.2


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, asyncio.CancelledError):
        return False
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)):
        return True
    status = getattr(exc, "status_code", None)
    if status in (408, 409, 425, 429):
        return True
    if isinstance(status, int) and 500 <= status <= 599:
        return True
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    if response_status in (408, 409, 425, 429):
        return True
    if isinstance(response_status, int) and 500 <= response_status <= 599:
        return True
    return False


class QdrantVectorStoreAdapter:
    """Qdrant implementation that always scopes vector operations to a tenant."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._base_url = settings.qdrant_url.rstrip("/")
        self._client = client
        self._headers = {"api-key": settings.qdrant_api_key} if settings.qdrant_api_key else {}
        self._provisioned: set[str] = set()
        self._provision_lock = asyncio.Lock()

    async def provision_payload_indexes(self, *, collection: str) -> None:
        """Create idempotent indexes for every server-built retrieval filter field.

        Cheap-guard: each collection is provisioned at most once per adapter
        instance. Call once at startup/background — never per query. The guard
        keeps accidental per-query callers cheap without changing filter semantics.
        """
        if collection in self._provisioned:
            return
        async with self._provision_lock:
            if collection in self._provisioned:
                return
            for field_name, field_schema in _PAYLOAD_INDEXES.items():
                response = await self._client.put(
                    f"{self._base_url}/collections/{collection}/index",
                    headers=self._headers,
                    json={"field_name": field_name, "field_schema": field_schema},
                    timeout=_PROVISION_TIMEOUT_S,
                )
                response.raise_for_status()
            self._provisioned.add(collection)

    async def upsert_points(self, *, tenant: TenantContext, collection: str, points: list[dict[str, object]]) -> None:
        namespace = TenantNamespace(tenant.tenant_id)
        scoped_points = [{**point, "payload": namespace.qdrant_point_payload(_payload(point))} for point in points]
        response = await self._client.put(
            f"{self._base_url}/collections/{collection}/points",
            headers=self._headers,
            json={"points": scoped_points},
        )
        response.raise_for_status()

    async def search(self, *, tenant: TenantContext, collection: str, vector: list[float], limit: int) -> list[dict[str, object]]:
        return await self._query(collection=collection, vector=vector, limit=limit, filter_value=TenantNamespace(tenant.tenant_id).qdrant_payload_filter())

    async def search_permitted(
        self,
        *,
        tenant: TenantContext,
        collection: str,
        vector: list[float],
        limit: int,
        knowledge_base_ids: tuple[str, ...],
        active_generation_ids: tuple[str, ...],
    ) -> list[dict[str, object]]:
        return await self._query(
            collection=collection,
            vector=vector,
            limit=limit,
            filter_value=qdrant_policy_filter(
                tenant=tenant,
                knowledge_base_ids=knowledge_base_ids,
                active_generation_ids=active_generation_ids,
            ),
        )

    async def search_sparse_permitted(
        self,
        *,
        tenant: TenantContext,
        collection: str,
        vector: dict[str, object],
        limit: int,
        knowledge_base_ids: tuple[str, ...],
        active_generation_ids: tuple[str, ...],
    ) -> list[dict[str, object]]:
        return await self._query(
            collection=collection,
            vector=vector,
            limit=limit,
            filter_value=qdrant_policy_filter(
                tenant=tenant,
                knowledge_base_ids=knowledge_base_ids,
                active_generation_ids=active_generation_ids,
            ),
        )

    async def _query(
        self, *, collection: str, vector: list[float] | dict[str, object], limit: int, filter_value: dict[str, object]
    ) -> list[dict[str, object]]:
        try:
            response = await self._client.post(
                f"{self._base_url}/collections/{collection}/points/query",
                headers=self._headers,
                json={"query": vector, "limit": limit, "filter": filter_value, "with_payload": True},
                timeout=_QUERY_TIMEOUT_S,
            )
        except Exception as exc:
            if not _is_retryable(exc):
                raise
            await asyncio.sleep(random.uniform(0, _RETRY_JITTER_S))
            response = await self._client.post(
                f"{self._base_url}/collections/{collection}/points/query",
                headers=self._headers,
                json={"query": vector, "limit": limit, "filter": filter_value, "with_payload": True},
                timeout=_QUERY_TIMEOUT_S,
            )
        response.raise_for_status()
        result = response.json().get("result", {})
        points = result.get("points", []) if isinstance(result, dict) else []
        return [point for point in points if isinstance(point, dict)]

    async def delete_points(self, *, tenant: TenantContext, collection: str, document_version_id: str) -> None:
        tenant_filter = {
            "must": [
                {"key": "tenant_id", "match": {"value": tenant.tenant_id}},
                {"key": "document_version_id", "match": {"value": document_version_id}},
            ]
        }
        response = await self._client.post(
            f"{self._base_url}/collections/{collection}/points/delete",
            headers=self._headers,
            json={"filter": tenant_filter},
        )
        response.raise_for_status()


def _payload(point: dict[str, object]) -> dict[str, object]:
    payload = point.get("payload", {})
    return dict(payload) if isinstance(payload, dict) else {}
