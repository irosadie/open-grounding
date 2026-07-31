"""Logout a user by deleting their session and revoking the access token."""

from app.core.security import revoke_token
from app.domain.repositories import AuthRepository


async def logout_user(
    repo: AuthRepository, *, user_id: str, session_id: str, access_token: str
) -> None:
    """Delete the auth session and revoke the access token."""
    await repo.delete_auth_session(session_id, user_id)
    revoke_token(access_token)
