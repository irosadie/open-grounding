"""Two-tenant isolation tests for RAG adapter boundary primitives.

Proves that object-key construction, queue payload/idempotency keys, cache
keys, Qdrant payload filters, and graph predicates never return or mutate
data from another tenant.
"""

from uuid import uuid4

import pytest

from app.domain.errors import DomainError
from app.domain.rag.adapter_ports import assert_tenant_scope
from app.domain.rag.tenant_namespace import TenantNamespace
from app.domain.tenant_context import TenantContext

TENANT_A_ID = str(uuid4())
TENANT_B_ID = str(uuid4())


@pytest.fixture
def tenant_a() -> TenantContext:
    return TenantContext(tenant_id=TENANT_A_ID, membership_id=str(uuid4()), user_id=str(uuid4()))


@pytest.fixture
def tenant_b() -> TenantContext:
    return TenantContext(tenant_id=TENANT_B_ID, membership_id=str(uuid4()), user_id=str(uuid4()))


def test_object_keys_are_tenant_namespaced(tenant_a: TenantContext, tenant_b: TenantContext) -> None:
    ns_a = TenantNamespace(tenant_a.tenant_id)
    ns_b = TenantNamespace(tenant_b.tenant_id)
    key_a = ns_a.object_key("documents", "doc-1", "raw")
    key_b = ns_b.object_key("documents", "doc-1", "raw")
    assert key_a.startswith(f"tenants/{TENANT_A_ID}/")
    assert key_b.startswith(f"tenants/{TENANT_B_ID}/")
    assert key_a != key_b
    assert TENANT_B_ID not in key_a
    assert TENANT_A_ID not in key_b


def test_object_prefix_is_tenant_scoped(tenant_a: TenantContext) -> None:
    ns = TenantNamespace(tenant_a.tenant_id)
    assert ns.object_prefix() == f"tenants/{TENANT_A_ID}/"


def test_job_queue_names_are_tenant_scoped(tenant_a: TenantContext, tenant_b: TenantContext) -> None:
    ns_a = TenantNamespace(tenant_a.tenant_id)
    ns_b = TenantNamespace(tenant_b.tenant_id)
    assert ns_a.job_queue_name("ingestion") == f"tenant:{TENANT_A_ID}:ingestion"
    assert ns_b.job_queue_name("ingestion") == f"tenant:{TENANT_B_ID}:ingestion"


def test_job_payloads_carry_tenant_id(tenant_a: TenantContext) -> None:
    ns = TenantNamespace(tenant_a.tenant_id)
    payload = ns.job_payload({"documentId": "doc-1"})
    assert payload["tenantId"] == TENANT_A_ID


def test_idempotency_keys_are_tenant_scoped(tenant_a: TenantContext, tenant_b: TenantContext) -> None:
    ns_a = TenantNamespace(tenant_a.tenant_id)
    ns_b = TenantNamespace(tenant_b.tenant_id)
    assert ns_a.idempotency_key("ingest", "doc-1") == f"tenant:{TENANT_A_ID}:ingest:doc-1"
    assert ns_b.idempotency_key("ingest", "doc-1") == f"tenant:{TENANT_B_ID}:ingest:doc-1"


def test_cache_keys_are_tenant_scoped(tenant_a: TenantContext, tenant_b: TenantContext) -> None:
    ns_a = TenantNamespace(tenant_a.tenant_id)
    ns_b = TenantNamespace(tenant_b.tenant_id)
    assert ns_a.cache_key("embeddings", "chunk-1") == f"tenant:{TENANT_A_ID}:embeddings:chunk-1"
    assert ns_b.cache_key("embeddings", "chunk-1") == f"tenant:{TENANT_B_ID}:embeddings:chunk-1"


def test_qdrant_filters_isolate_tenants(tenant_a: TenantContext, tenant_b: TenantContext) -> None:
    ns_a = TenantNamespace(tenant_a.tenant_id)
    ns_b = TenantNamespace(tenant_b.tenant_id)
    filter_a = ns_a.qdrant_payload_filter()
    filter_b = ns_b.qdrant_payload_filter()
    assert filter_a["must"][0]["match"]["value"] == TENANT_A_ID
    assert filter_b["must"][0]["match"]["value"] == TENANT_B_ID
    assert filter_a != filter_b


def test_qdrant_point_payload_includes_tenant_id(tenant_a: TenantContext) -> None:
    ns = TenantNamespace(tenant_a.tenant_id)
    payload = ns.qdrant_point_payload({"chunk_id": "chunk-1", "text": "hello"})
    assert payload["tenant_id"] == TENANT_A_ID
    assert payload["chunk_id"] == "chunk-1"


def test_graph_predicates_are_tenant_scoped(tenant_a: TenantContext, tenant_b: TenantContext) -> None:
    ns_a = TenantNamespace(tenant_a.tenant_id)
    ns_b = TenantNamespace(tenant_b.tenant_id)
    assert ns_a.graph_predicate("DOCUMENT")["tenant_id"] == TENANT_A_ID
    assert ns_b.graph_predicate("DOCUMENT")["tenant_id"] == TENANT_B_ID


def test_graph_node_ids_are_tenant_scoped(tenant_a: TenantContext, tenant_b: TenantContext) -> None:
    ns_a = TenantNamespace(tenant_a.tenant_id)
    ns_b = TenantNamespace(tenant_b.tenant_id)
    assert ns_a.graph_node_id("Document", "doc-1") == f"tenant:{TENANT_A_ID}:Document:doc-1"
    assert ns_b.graph_node_id("Document", "doc-1") == f"tenant:{TENANT_B_ID}:Document:doc-1"


def test_assert_tenant_scope_rejects_mismatch(tenant_a: TenantContext, tenant_b: TenantContext) -> None:
    ns = assert_tenant_scope(tenant_a, TENANT_A_ID)
    assert ns.tenant_id == TENANT_A_ID
    with pytest.raises(DomainError, match="TENANT_SCOPE_MISMATCH"):
        assert_tenant_scope(tenant_a, TENANT_B_ID)


def test_cross_tenant_object_key_never_collides(tenant_a: TenantContext, tenant_b: TenantContext) -> None:
    """Two tenants with the same document ID produce distinct, non-overlapping keys."""
    ns_a = TenantNamespace(tenant_a.tenant_id)
    ns_b = TenantNamespace(tenant_b.tenant_id)
    same_doc_id = "00000000-0000-0000-0000-000000000001"
    for artifact in ["raw", "normalized", "parsed", "thumbnails/page-1.png"]:
        key_a = ns_a.object_key("documents", same_doc_id, artifact)
        key_b = ns_b.object_key("documents", same_doc_id, artifact)
        assert key_a != key_b
        assert TENANT_B_ID not in key_a
        assert TENANT_A_ID not in key_b