from app.core.security import hash_password
from app.core.settings import Settings
from app.domain.models import User
from app.domain.repositories import AuthRepository
from app.domain.use_cases.get_current_user import get_current_user
from app.domain.use_cases.login_user import login_user
from app.domain.use_cases.logout_user import logout_user
from app.domain.use_cases.refresh_token import refresh_tokens
from app.domain.use_cases.register_user import register_user


class AuthService:
    def __init__(self, repository: AuthRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    async def register(self, *, name: str, email: str, password: str) -> dict[str, object]:
        user = await register_user(
            self._repository,
            email=email.strip().lower(),
            password_hash=hash_password(password),
            name=name.strip(),
        )
        return {"user": _user_dto(user)}

    async def login(self, *, email: str, password: str) -> dict[str, object]:
        user, tokens = await login_user(
            self._repository,
            self._settings,
            email=email.strip().lower(),
            password=password,
        )
        return {"user": _user_dto(user), "tokens": tokens}

    async def refresh(self, refresh_token: str) -> dict[str, object]:
        tokens = await refresh_tokens(self._repository, self._settings, refresh_token)
        return {"tokens": tokens}

    async def logout(self, *, user_id: str, session_id: str, access_token: str) -> None:
        await logout_user(self._repository, user_id=user_id, session_id=session_id, access_token=access_token)

    async def current_user(self, *, user_id: str, session_id: str) -> dict[str, object]:
        user, session = await get_current_user(self._repository, user_id=user_id, session_id=session_id)
        return {"user": _user_dto(user), "session": {"expiresAt": session.expires_at.isoformat() if session else None}}


def _user_dto(user: User) -> dict[str, str | None]:
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role.value, "status": user.status.value, "photo": user.photo}
