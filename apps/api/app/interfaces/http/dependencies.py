from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth_service import AuthService
from app.core.security import decode_access_token
from app.core.settings import Settings, get_settings
from app.domain.errors import DomainError
from app.domain.tenant_context import TenantContext
from app.infrastructure.database import SqlAlchemyAuthRepository, SqlAlchemyTenantRepository, get_session


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(SqlAlchemyAuthRepository(session), settings)


async def get_auth_context(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise DomainError.unauthorized()
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise DomainError.unauthorized()
    payload = decode_access_token(token, settings)
    if payload.get("status") == "SUSPENDED":
        raise DomainError.forbidden("Account is suspended")
    if payload.get("type") not in {"admin", "user"}:
        raise DomainError.invalid_token("Invalid token payload")
    return {**payload, "accessToken": token}


AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]
AuthContextDependency = Annotated[dict[str, str], Depends(get_auth_context)]


async def get_tenant_context(
    request: Request,
    auth_context: AuthContextDependency,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TenantContext:
    """Resolve the immutable tenant context from deployment configuration and
    authenticated active membership.

    The deployment tenant ID is read from application state (set during startup
    verification). Client-supplied tenant values in headers, path, query, body,
    or JWT claims are never used.
    """
    if settings.deployment_tenant_id is None:
        raise DomainError.tenant_not_configured()

    bootstrap = getattr(request.app.state, "tenant_bootstrap_result", None)
    if bootstrap is None:
        raise DomainError.tenant_not_configured()

    tenant_repo = SqlAlchemyTenantRepository(session)
    membership = await tenant_repo.find_active_membership(
        tenant_id=bootstrap.tenant_id,
        user_id=auth_context["id"],
    )
    if membership is None:
        raise DomainError.tenant_membership_inactive()

    return TenantContext(
        tenant_id=bootstrap.tenant_id,
        membership_id=membership.id,
        user_id=auth_context["id"],
    )


TenantContextDependency = Annotated[TenantContext, Depends(get_tenant_context)]
