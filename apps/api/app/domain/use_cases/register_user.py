"""Register a new user."""

from app.domain.errors import DomainError
from app.domain.models import User, UserRole, UserStatus
from app.domain.repositories import AuthRepository


async def register_user(repo: AuthRepository, *, email: str, password_hash: str, name: str) -> User:
    """Create a new user after checking for duplicate email.

    Raises DomainError.duplicate_email if the email is already registered.
    """
    if await repo.find_user_by_email(email):
        raise DomainError.duplicate_email()
    return await repo.create_user(
        email=email,
        password_hash=password_hash,
        name=name,
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
        photo=None,
    )
