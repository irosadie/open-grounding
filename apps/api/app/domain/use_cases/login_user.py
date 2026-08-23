"""Authenticate a user and create a new session."""

from datetime import UTC, datetime, timedelta

from app.core.security import (
    REFRESH_TOKEN_EXPIRY_SECONDS,
    build_token_pair,
    hash_session_token,
    new_session_id,
    verify_password,
)
from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.models import User, UserStatus
from app.domain.repositories import AuthRepository


async def login_user(repo: AuthRepository, settings: Settings, *, email: str, password: str) -> tuple[User, dict[str, str | int]]:
    """Verify credentials, build a token pair, and persist a new auth session.

    Deletes any existing sessions for the user before creating the new one.
    Raises DomainError.invalid_credentials if the email or password is wrong.
    Raises DomainError.forbidden if the account is suspended.
    """
    user = await repo.find_user_by_email(email)
    if user is None or not verify_password(password, user.password_hash):
        raise DomainError.invalid_credentials()
    if user.status is UserStatus.SUSPENDED:
        raise DomainError.forbidden("Account is suspended")
    session_id = new_session_id()
    tokens = build_token_pair(
        user_id=user.id,
        email=user.email,
        role=user.role,
        status=user.status,
        session_id=session_id,
        settings=settings,
    )
    # BUG-API-02: delete + create must be atomic — wrap in a single transaction
    # so a crash between the two operations cannot leave the user with no session.
    async with repo.transaction():
        await repo.delete_auth_sessions_for_user(user.id)
        await repo.create_auth_session(
            session_id=session_id,
            user_id=user.id,
            token_hash=hash_session_token(str(tokens["refreshToken"])),
            expires_at=(datetime.now(UTC) + timedelta(seconds=REFRESH_TOKEN_EXPIRY_SECONDS)).replace(tzinfo=None),
        )
    return user, tokens
