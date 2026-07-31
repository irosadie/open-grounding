from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth_service import AuthService
from app.core.security import decode_access_token
from app.core.settings import Settings, get_settings
from app.domain.errors import DomainError
from app.infrastructure.database import SqlAlchemyAuthRepository, get_session


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
