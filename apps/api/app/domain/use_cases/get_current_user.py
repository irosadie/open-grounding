"""Load the current authenticated user and their active session."""

from app.domain.errors import DomainError
from app.domain.models import AuthSession, User, UserStatus
from app.domain.repositories import AuthRepository


async def get_current_user(
    repo: AuthRepository, *, user_id: str, session_id: str
) -> tuple[User, AuthSession | None]:
    """Find the user by ID and verify their session is still active.

    Raises DomainError.user_not_found if the user does not exist.
    Raises DomainError.forbidden if the account is suspended.
    Returns the user and their session (session may be None if expired).
    """
    user = await repo.find_user_by_id(user_id)
    if user is None:
        raise DomainError.user_not_found()
    if user.status is UserStatus.SUSPENDED:
        raise DomainError.forbidden("Account is suspended")
    session = await repo.find_auth_session(session_id, user_id)
    return user, session
