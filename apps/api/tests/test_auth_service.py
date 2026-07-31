from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.auth_service import AuthService
from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.models import AuthSession, User, UserRole, UserStatus


class InMemoryAuthRepository:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.sessions: dict[str, AuthSession] = {}

    async def find_user_by_email(self, email: str) -> User | None:
        return next((user for user in self.users.values() if user.email == email), None)

    async def find_user_by_id(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    async def create_user(self, *, email: str, password_hash: str, name: str, role: UserRole, status: UserStatus, photo: str | None) -> User:
        now = datetime.now(UTC)
        user = User(str(uuid4()), email, password_hash, name, role, status, photo, now, now)
        self.users[user.id] = user
        return user

    async def create_auth_session(self, *, session_id: str, user_id: str, token_hash: str, expires_at: datetime) -> AuthSession:
        session = AuthSession(session_id, user_id, token_hash, expires_at, datetime.now(UTC))
        self.sessions[session.id] = session
        return session

    async def find_auth_session(self, session_id: str, user_id: str) -> AuthSession | None:
        session = self.sessions.get(session_id)
        if session is None or session.user_id != user_id or session.expires_at <= datetime.now(UTC).replace(tzinfo=None):
            return None
        return session

    async def delete_auth_session(self, session_id: str, user_id: str) -> None:
        session = await self.find_auth_session(session_id, user_id)
        if session:
            del self.sessions[session_id]

    async def delete_auth_sessions_for_user(self, user_id: str) -> None:
        for session_id, session in list(self.sessions.items()):
            if session.user_id == user_id:
                del self.sessions[session_id]


@pytest.mark.asyncio
async def test_register_login_and_refresh() -> None:
    service = AuthService(InMemoryAuthRepository(), Settings(jwt_secret="test-secret"))

    registered = await service.register(name="Baim", email="BAIM@example.com", password="password123")
    logged_in = await service.login(email="baim@example.com", password="password123")
    refreshed = await service.refresh(logged_in["tokens"]["refreshToken"])

    assert registered["user"]["email"] == "baim@example.com"
    assert logged_in["tokens"]["accessToken"]
    assert refreshed["tokens"]["accessToken"]


@pytest.mark.asyncio
async def test_rejects_duplicate_email() -> None:
    service = AuthService(InMemoryAuthRepository(), Settings(jwt_secret="test-secret"))
    await service.register(name="Baim", email="baim@example.com", password="password123")

    with pytest.raises(DomainError, match="Email already registered"):
        await service.register(name="Other", email="baim@example.com", password="password123")
