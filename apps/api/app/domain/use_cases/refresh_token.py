"""Refresh an expired access token using a valid refresh token."""

from app.core.security import (
    build_token_pair,
    decode_refresh_token,
    hash_session_token,
)
from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.models import UserStatus
from app.domain.repositories import AuthRepository


async def refresh_tokens(repo: AuthRepository, settings: Settings, refresh_token: str) -> dict[str, str | int]:
    """Validate the refresh token and return a new token pair.

    Raises DomainError.invalid_token if the token is expired, the user is
    not found, the account is suspended, or the session does not match.
    """
    payload = decode_refresh_token(refresh_token, settings)
    user = await repo.find_user_by_id(payload["id"])
    if user is None or user.status is UserStatus.SUSPENDED:
        raise DomainError.invalid_token()
    session = await repo.find_auth_session(payload["sessionId"], user.id)
    if session is None or session.token_hash != hash_session_token(refresh_token):
        raise DomainError.invalid_token()
    return build_token_pair(
        user_id=user.id,
        email=user.email,
        role=user.role,
        status=user.status,
        session_id=session.id,
        settings=settings,
    )
