"""Future RAG adapter ports that require tenant context.

These are provider-neutral protocols (ports) for object storage, queue,
vector, and graph adapters. Each method requires a ``TenantContext`` and
rejects missing or mismatched tenant scope before any adapter operation
executes.

Concrete adapter implementations will be added in future RAG resource
changes. The ports exist now to enforce the tenant-scoped contract before
any RAG infrastructure is built.
"""

from typing import Protocol

from app.domain.rag.tenant_namespace import TenantNamespace
from app.domain.tenant_context import TenantContext


class ObjectStoreAdapter(Protocol):
    """Port for S3-compatible object storage operations.

    All operations require tenant context and MUST construct keys using
    ``TenantNamespace.object_key``. Tenant-neutral keys are prohibited.
    """

    async def put_object(
        self, *, tenant: TenantContext, key_suffix: str, data: bytes, content_type: str
    ) -> str:
        """Store an object beneath the tenant namespace. Returns the full key."""
        ...

    async def get_object(self, *, tenant: TenantContext, key_suffix: str) -> bytes | None:
        """Retrieve an object from the tenant namespace."""
        ...

    async def delete_object(self, *, tenant: TenantContext, key_suffix: str) -> None:
        """Delete an object from the tenant namespace."""
        ...


class QueueAdapter(Protocol):
    """Port for BullMQ job queue operations.

    Job payloads MUST include the tenant ID via ``TenantNamespace.job_payload``
    and use tenant-scoped idempotency keys. A worker MUST reject any job whose
    tenant ID is missing or does not match the deployment tenant.
    """

    async def enqueue(
        self, *, tenant: TenantContext, queue: str, job_name: str, payload: dict[str, object]
    ) -> str:
        """Enqueue a tenant-scoped job. Returns the job ID."""
        ...


class VectorStoreAdapter(Protocol):
    """Port for Qdrant vector store operations.

    Every read, write, scroll, and delete MUST apply the mandatory tenant
    payload filter from ``TenantNamespace.qdrant_payload_filter``. Points
    MUST include ``tenant_id`` in their payload via
    ``TenantNamespace.qdrant_point_payload``.
    """

    async def upsert_points(
        self, *, tenant: TenantContext, collection: str, points: list[dict[str, object]]
    ) -> None:
        ...

    async def search(
        self, *, tenant: TenantContext, collection: str, vector: list[float], limit: int
    ) -> list[dict[str, object]]:
        ...

    async def delete_points(
        self, *, tenant: TenantContext, collection: str, document_version_id: str
    ) -> None:
        """Delete only points matching both the tenant ID and document-version ID."""
        ...


class GraphAdapter(Protocol):
    """Optional port for graph database traversal.

    Traversal and results MUST use tenant-scoped predicates from
    ``TenantNamespace.graph_predicate`` and tenant-scoped node IDs.
    """

    async def traverse(
        self, *, tenant: TenantContext, start_node_id: str, max_depth: int
    ) -> list[dict[str, object]]:
        ...


def assert_tenant_scope(tenant: TenantContext, expected_tenant_id: str) -> TenantNamespace:
    """Verify that the tenant context matches the expected deployment tenant.

    Raises ``DomainError.tenant_scope_mismatch`` if the tenant context does not
    match. Returns a ``TenantNamespace`` for constructing scoped keys and filters.
    """
    from app.domain.errors import DomainError

    if tenant.tenant_id != expected_tenant_id:
        raise DomainError.tenant_scope_mismatch()
    return TenantNamespace(tenant_id=tenant.tenant_id)