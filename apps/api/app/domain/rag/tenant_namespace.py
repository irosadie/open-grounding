"""Provider-neutral tenant namespace and filter primitives.

These primitives ensure that object-store keys, BullMQ job payloads,
idempotency keys, cache keys, Qdrant payload filters, and optional graph
predicates are always scoped by tenant identity. No adapter should construct
tenant-neutral keys or filters for tenant-owned content.

All construction is server-side from the immutable ``TenantContext``. Client
code never supplies a tenant value to these primitives.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantNamespace:
    """Encapsulates tenant-scoped key and filter construction.

    Created exclusively from a server-derived ``TenantContext``. The tenant ID
    is embedded in every derived key, filter, and predicate so that cross-tenant
    access is structurally prevented.
    """

    tenant_id: str

    # --- Object store ---------------------------------------------------------

    def object_key(self, *parts: str) -> str:
        """Build an S3-compatible object key prefixed with the tenant namespace.

        Example: ``tenants/{tenant_id}/documents/{doc_id}/raw``
        """
        segments = "/".join(part.strip("/") for part in parts if part)
        return f"tenants/{self.tenant_id}/{segments}"

    def object_prefix(self) -> str:
        """Return the tenant-level object-store prefix for listing operations."""
        return f"tenants/{self.tenant_id}/"

    # --- Queue (BullMQ) -------------------------------------------------------

    def job_queue_name(self, base_queue: str) -> str:
        """Return a tenant-scoped BullMQ queue name.

        In single-deployment mode the queue is shared but the job payload
        always carries the tenant ID for verification.
        """
        return f"tenant:{self.tenant_id}:{base_queue}"

    def job_payload(self, base_payload: dict[str, object]) -> dict[str, object]:
        """Inject tenant ID into a BullMQ job payload."""
        return {**base_payload, "tenantId": self.tenant_id}

    def idempotency_key(self, operation: str, resource_id: str) -> str:
        """Build a tenant-scoped idempotency key for deduplication."""
        return f"tenant:{self.tenant_id}:{operation}:{resource_id}"

    # --- Cache ----------------------------------------------------------------

    def cache_key(self, domain: str, key: str) -> str:
        """Build a tenant-scoped cache key."""
        return f"tenant:{self.tenant_id}:{domain}:{key}"

    # --- Vector (Qdrant) ------------------------------------------------------

    def qdrant_payload_filter(self) -> dict[str, object]:
        """Return the mandatory Qdrant payload filter for tenant-owned points.

        This filter MUST be applied to every vector read, write, scroll, and
        delete operation. Client-side filtering is prohibited.
        """
        return {"must": [{"key": "tenant_id", "match": {"value": self.tenant_id}}]}

    def qdrant_point_payload(self, extra: dict[str, object]) -> dict[str, object]:
        """Inject tenant ID into a Qdrant point payload for indexing."""
        return {**extra, "tenant_id": self.tenant_id}

    # --- Graph (optional) -----------------------------------------------------

    def graph_predicate(self, label: str) -> dict[str, object]:
        """Return a tenant-scoped graph predicate for traversal and results.

        Ensures graph queries only traverse nodes and edges owned by the
        active tenant.
        """
        return {"label": label, "tenant_id": self.tenant_id}

    def graph_node_id(self, node_type: str, node_id: str) -> str:
        """Build a tenant-scoped graph node identifier."""
        return f"tenant:{self.tenant_id}:{node_type}:{node_id}"