"""Server-derived RAG evidence policy primitives."""

from datetime import UTC, datetime
from enum import IntEnum, StrEnum

from app.domain.models import UserRole
from app.domain.tenant_context import TenantContext


class Classification(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"


class Clearance(IntEnum):
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2


def effective_principals(tenant: TenantContext) -> tuple[str, ...]:
    return (f"user:{tenant.user_id}", f"role:{tenant.role.value}")


def clearance_for_role(role: UserRole) -> Classification:
    return Classification.CONFIDENTIAL if role is UserRole.ADMIN else Classification.INTERNAL


def qdrant_policy_filter(*, tenant: TenantContext, knowledge_base_ids: tuple[str, ...], active_generation_ids: tuple[str, ...], now: datetime | None = None) -> dict[str, object]:
    timestamp = (now or datetime.now(UTC)).isoformat()
    return {
        "must": [
            {"key": "tenant_id", "match": {"value": tenant.tenant_id}},
            {"key": "knowledge_base_id", "match": {"any": list(knowledge_base_ids)}},
            {"key": "generation_id", "match": {"any": list(active_generation_ids)}},
            {"key": "classification", "match": {"any": _allowed_classifications(tenant.role)}},
            {
                "should": [
                    {"key": "acl_principals", "match": {"any": list(effective_principals(tenant))}},
                    {"is_empty": {"key": "acl_principals"}},
                ]
            },
            {"should": [{"key": "effective_from", "range": {"lte": timestamp}}, {"is_empty": {"key": "effective_from"}}]},
            {"should": [{"key": "effective_to", "range": {"gte": timestamp}}, {"is_empty": {"key": "effective_to"}}]},
        ]
    }


def _allowed_classifications(role: UserRole) -> list[str]:
    if clearance_for_role(role) is Classification.CONFIDENTIAL:
        return [Classification.PUBLIC.value, Classification.INTERNAL.value, Classification.CONFIDENTIAL.value]
    return [Classification.PUBLIC.value, Classification.INTERNAL.value]
