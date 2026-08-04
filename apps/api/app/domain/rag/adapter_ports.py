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

from app.domain.rag.elements import ParsedDocument
from app.domain.rag.tenant_namespace import TenantNamespace
from app.domain.tenant_context import TenantContext


class ObjectStoreAdapter(Protocol):
    """Port for S3-compatible object storage operations.

    All operations require tenant context and MUST construct keys using
    ``TenantNamespace.object_key``. Tenant-neutral keys are prohibited.
    """

    async def put_object(self, *, tenant: TenantContext, key_suffix: str, data: bytes, content_type: str) -> str:
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

    async def enqueue(self, *, tenant: TenantContext, queue: str, job_name: str, payload: dict[str, object]) -> str:
        """Enqueue a tenant-scoped job. Returns the job ID."""
        ...


class VectorStoreAdapter(Protocol):
    """Port for Qdrant vector store operations.

    Every read, write, scroll, and delete MUST apply the mandatory tenant
    payload filter from ``TenantNamespace.qdrant_payload_filter``. Points
    MUST include ``tenant_id`` in their payload via
    ``TenantNamespace.qdrant_point_payload``.
    """

    async def upsert_points(self, *, tenant: TenantContext, collection: str, points: list[dict[str, object]]) -> None: ...

    async def search(self, *, tenant: TenantContext, collection: str, vector: list[float], limit: int) -> list[dict[str, object]]: ...

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
        """Search only evidence allowed by server-derived policy inputs."""
        ...

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
        """Sparse search using the identical server-derived policy inputs."""
        ...

    async def delete_points(self, *, tenant: TenantContext, collection: str, document_version_id: str) -> None:
        """Delete only points matching both the tenant ID and document-version ID."""
        ...


class GraphAdapter(Protocol):
    """Optional port for graph database traversal.

    Traversal and results MUST use tenant-scoped predicates from
    ``TenantNamespace.graph_predicate`` and tenant-scoped node IDs.
    """

    async def traverse(self, *, tenant: TenantContext, start_node_id: str, max_depth: int) -> list[dict[str, object]]: ...


class GenerationAdapter(Protocol):
    """Port for LLM answer generation.

    Generation requests MUST carry tenant context and a generation model
    profile reference. The adapter MUST NOT persist secrets and returns only
    the generated text and usage metadata.
    """

    async def generate(
        self,
        *,
        tenant: TenantContext,
        prompt: str,
        model_profile_id: str,
        max_tokens: int | None = None,
    ) -> dict[str, object]:
        """Generate text for the tenant. Returns text and usage metadata."""
        ...


class EmbeddingAdapter(Protocol):
    """Port for dense vector embedding.

    Embedding requests MUST carry tenant context and an embedding model
    profile reference. The adapter returns ordered dense vectors matching the
    declared profile dimensions.
    """

    async def embed(self, *, tenant: TenantContext, texts: list[str], model_profile_id: str) -> list[list[float]]:
        """Return one dense vector per input text in order."""
        ...


class SparseEncoderAdapter(Protocol):
    """Port for sparse vector encoding.

    Sparse encoding requests MUST carry tenant context and a sparse profile
    reference. The adapter returns ordered sparse representations compatible
    with the active index profile.
    """

    async def encode(self, *, tenant: TenantContext, texts: list[str], sparse_profile_id: str) -> list[dict[str, object]]:
        """Return one sparse representation per input text in order."""
        ...


class RerankerAdapter(Protocol):
    """Port for cross-encoder reranking.

    Reranking requests MUST carry tenant context. The adapter returns the
    candidates reordered by relevance score without discarding the original
    query or exceeding the configured candidate budget.
    """

    async def rerank(
        self,
        *,
        tenant: TenantContext,
        query: str,
        candidates: list[dict[str, object]],
        reranker_profile_id: str,
        top_k: int | None = None,
    ) -> list[dict[str, object]]:
        """Return candidates annotated with reranker scores, ordered."""
        ...


class DocumentParser(Protocol):
    """Port for tenant-aware document parsing.

    The parser accepts a tenant context and a source reference (object-store
    key or bytes) and returns ordered canonical ``DocumentElement`` records
    plus a bounded quality summary. The port is provider-neutral; concrete
    adapters (e.g. docling) live in infrastructure and MUST NOT be imported
    by domain or application code.

    The port MUST reject missing or mismatched tenant scope before any
    parser operation executes, and MUST reject unsupported MIME types for
    the v1 officially supported set (PDF, Markdown, TXT) without attempting
    conversion.
    """

    async def parse(
        self,
        *,
        tenant: TenantContext,
        source: bytes,
        mime_type: str,
        parser_profile_id: str,
    ) -> ParsedDocument:
        """Parse a source into ordered canonical elements + quality summary."""
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
