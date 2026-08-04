from datetime import UTC, datetime
from uuid import uuid4

from app.domain.models import UserRole
from app.domain.rag.policy import qdrant_policy_filter
from app.domain.tenant_context import TenantContext


def test_query_policy_filter_is_server_derived_and_role_scoped() -> None:
    tenant = TenantContext(
        tenant_id=str(uuid4()),
        membership_id=str(uuid4()),
        user_id=str(uuid4()),
        role=UserRole.USER,
    )
    filter_value = qdrant_policy_filter(
        tenant=tenant,
        knowledge_base_ids=("kb-1",),
        active_generation_ids=("generation-1",),
        now=datetime(2026, 8, 4, tzinfo=UTC),
    )
    conditions = filter_value["must"]
    assert conditions[0] == {"key": "tenant_id", "match": {"value": tenant.tenant_id}}
    assert conditions[1] == {"key": "knowledge_base_id", "match": {"any": ["kb-1"]}}
    assert conditions[2] == {"key": "generation_id", "match": {"any": ["generation-1"]}}
    assert conditions[3] == {"key": "classification", "match": {"any": ["PUBLIC", "INTERNAL"]}}
    assert conditions[4]["should"][0]["key"] == "acl_principals"
    assert conditions[4]["should"][1] == {"is_empty": {"key": "acl_principals"}}
