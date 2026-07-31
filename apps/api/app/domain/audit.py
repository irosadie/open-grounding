from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class AuditAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    ACCESS_GRANTED = "ACCESS_GRANTED"
    ACCESS_DENIED = "ACCESS_DENIED"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    MEMBERSHIP_INACTIVE = "MEMBERSHIP_INACTIVE"


@dataclass(frozen=True)
class AuditEvent:
    """A tenant-aware audit event for mutations and security-relevant denials.

    Records tenant ID, actor ID (when available), action, resource identity,
    and trace/request ID. Persisted or logged for compliance and forensics.
    """

    tenant_id: str | None
    actor_id: str | None
    action: AuditAction
    resource_type: str
    resource_id: str | None
    trace_id: str
    timestamp: datetime
    details: dict[str, object] | None = None