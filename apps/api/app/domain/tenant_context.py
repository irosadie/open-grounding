from dataclasses import dataclass

from app.domain.models import UserRole


@dataclass(frozen=True)
class TenantContext:
    """Immutable, server-derived tenant context.

    Created from deployment configuration and authenticated active membership.
    Never accepted from a client request, header, path, query parameter, body,
    or JWT claim. Required for every tenant-owned operation.
    """

    tenant_id: str
    membership_id: str
    user_id: str
    role: UserRole = UserRole.USER
