"""Audit logging infrastructure for tenant-aware events.

Records tenant ID, actor ID, action, resource identity, and trace ID for
tenant-owned mutations and security-relevant access denials. Uses structured
logging (stdout) as the initial sink — a persistent audit table can be added
in a future change without changing the domain contract.
"""

import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.audit import AuditAction, AuditEvent

logger = logging.getLogger("tenant_audit")


def new_trace_id() -> str:
    return str(uuid4())


def record_audit_event(
    *,
    tenant_id: str | None,
    actor_id: str | None,
    action: AuditAction,
    resource_type: str,
    resource_id: str | None = None,
    trace_id: str | None = None,
    details: dict[str, object] | None = None,
) -> AuditEvent:
    """Create and emit an audit event."""
    event = AuditEvent(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        trace_id=trace_id or new_trace_id(),
        timestamp=datetime.now(UTC),
        details=details,
    )
    _emit(event)
    return event


def _emit(event: AuditEvent) -> None:
    payload = {
        "audit": True,
        "tenantId": event.tenant_id,
        "actorId": event.actor_id,
        "action": event.action.value,
        "resourceType": event.resource_type,
        "resourceId": event.resource_id,
        "traceId": event.trace_id,
        "timestamp": event.timestamp.isoformat(),
        "details": event.details,
    }
    logger.info(json.dumps(payload, default=str))
