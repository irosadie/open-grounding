from dataclasses import dataclass
from typing import Any


@dataclass
class DomainError(Exception):
    code: str
    message: str
    status_code: int
    details: Any | None = None

    @classmethod
    def invalid_credentials(cls) -> "DomainError":
        return cls("INVALID_CREDENTIALS", "Invalid email or password", 401)

    @classmethod
    def invalid_token(cls, message: str = "Invalid or expired token") -> "DomainError":
        return cls("INVALID_TOKEN", message, 401)

    @classmethod
    def unauthorized(cls, message: str = "Authorization token required") -> "DomainError":
        return cls("UNAUTHORIZED", message, 401)

    @classmethod
    def forbidden(cls, message: str) -> "DomainError":
        return cls("FORBIDDEN", message, 403)

    @classmethod
    def duplicate_email(cls) -> "DomainError":
        return cls("DUPLICATE_EMAIL", "Email already registered", 409)

    @classmethod
    def user_not_found(cls) -> "DomainError":
        return cls("USER_NOT_FOUND", "User not found", 404)

    # --- Tenant errors --------------------------------------------------------

    @classmethod
    def tenant_not_configured(cls) -> "DomainError":
        return cls(
            "TENANT_NOT_CONFIGURED",
            "DEPLOYMENT_TENANT_ID is not set. Configure it before starting the application.",
            500,
        )

    @classmethod
    def tenant_mismatch(cls, *, configured_id: str, persisted_id: str) -> "DomainError":
        return cls(
            "TENANT_MISMATCH",
            "Configured DEPLOYMENT_TENANT_ID does not match the persisted deployment tenant. "
            "Changing the tenant ID in place is not supported; provision a new deployment instead.",
            500,
            {"configuredTenantId": configured_id, "persistedTenantId": persisted_id},
        )

    @classmethod
    def tenant_membership_inactive(cls) -> "DomainError":
        return cls(
            "TENANT_MEMBERSHIP_INACTIVE",
            "User does not have an active membership in the deployment tenant.",
            403,
        )

    @classmethod
    def tenant_membership_required(cls) -> "DomainError":
        return cls(
            "TENANT_MEMBERSHIP_REQUIRED",
            "Tenant membership is required to access this resource.",
            403,
        )

    @classmethod
    def tenant_scope_missing(cls) -> "DomainError":
        return cls(
            "TENANT_SCOPE_MISSING",
            "Tenant scope is required for this operation.",
            400,
        )

    @classmethod
    def tenant_scope_mismatch(cls) -> "DomainError":
        return cls(
            "TENANT_SCOPE_MISMATCH",
            "Operation tenant scope does not match the active deployment tenant.",
            403,
        )
