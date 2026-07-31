from datetime import UTC, datetime, timedelta

from app.core.security import (
    REFRESH_TOKEN_EXPIRY_SECONDS,
    build_token_pair,
    decode_refresh_token,
    hash_password,
    hash_session_token,
    new_session_id,
    revoke_token,
    verify_password,
)
from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.models import User, UserRole, UserStatus
from app.domain.repositories import AuthRepository


class AuthService:
    def __init__(self, repository: AuthRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    async def register(self, *, name: str, email: str, password: str) -> dict[str, object]:
        normalized_email = email.strip().lower()
        if await self._repository.find_user_by_email(normalized_email):
            raise DomainError.duplicate_email()
        user = await self._repository.create_user(
            email=normalized_email,
            password_hash=hash_password(password),
            name=name.strip(),
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
            photo=None,
        )
        return {"user": _user_dto(user)}

    async def login(self, *, email: str, password: str) -> dict[str, object]:
        user = await self._repository.find_user_by_email(email.strip().lower())
        if user is None or not verify_password(password, user.password_hash):
            raise DomainError.invalid_credentials()
        if user.status is UserStatus.SUSPENDED:
            raise DomainError.forbidden("Account is suspended")
        session_id = new_session_id()
        tokens = build_token_pair(user_id=user.id, email=user.email, role=user.role, status=user.status, session_id=session_id, settings=self._settings)
        await self._repository.delete_auth_sessions_for_user(user.id)
        await self._repository.create_auth_session(
            session_id=session_id,
            user_id=user.id,
            token_hash=hash_session_token(str(tokens["refreshToken"])),
            expires_at=(datetime.now(UTC) + timedelta(seconds=REFRESH_TOKEN_EXPIRY_SECONDS)).replace(tzinfo=None),
        )
        return {"user": _user_dto(user), "tokens": tokens}

    async def refresh(self, refresh_token: str) -> dict[str, object]:
        payload = decode_refresh_token(refresh_token, self._settings)
        user = await self._repository.find_user_by_id(payload["id"])
        if user is None or user.status is UserStatus.SUSPENDED:
            raise DomainError.invalid_token()
        session = await self._repository.find_auth_session(payload["sessionId"], user.id)
        if session is None or session.token_hash != hash_session_token(refresh_token):
            raise DomainError.invalid_token()
        tokens = build_token_pair(user_id=user.id, email=user.email, role=user.role, status=user.status, session_id=session.id, settings=self._settings)
        return {"tokens": tokens}

    async def logout(self, *, user_id: str, session_id: str, access_token: str) -> None:
        await self._repository.delete_auth_session(session_id, user_id)
        revoke_token(access_token)

    async def current_user(self, *, user_id: str, session_id: str) -> dict[str, object]:
        user = await self._repository.find_user_by_id(user_id)
        if user is None:
            raise DomainError.user_not_found()
        if user.status is UserStatus.SUSPENDED:
            raise DomainError.forbidden("Account is suspended")
        session = await self._repository.find_auth_session(session_id, user_id)
        return {"user": _user_dto(user), "session": {"expiresAt": session.expires_at.isoformat() if session else None}}


def _user_dto(user: User) -> dict[str, str | None]:
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role.value, "status": user.status.value, "photo": user.photo}
