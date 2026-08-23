"""Logout a user by deleting their session and revoking the access token."""

from app.core.security import revoke_token_async
from app.core.settings import Settings
from app.domain.repositories import AuthRepository


async def logout_user(repo: AuthRepository, settings: Settings, *, user_id: str, session_id: str, access_token: str) -> None:
    """Delete the auth session and revoke the access token in Redis."""
    await repo.delete_auth_session(session_id, user_id)
    await revoke_token_async(access_token, settings)
