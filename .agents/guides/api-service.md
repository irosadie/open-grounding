# Guide: API Service (`apps/api/app/application/{domain}_service.py`)

## Folder Contract

✅ Allowed:
- Orchestrate one or more use cases
- Transform Entity to DTO before returning to the route handler
- Inject repository interface and settings via `__init__`
- Coordinate side effects (send email via worker queue, etc.)

❌ Forbidden:
- Pure business logic — that goes in use cases
- Access SQLAlchemy directly — must go through repository interface
- HTTP concerns (status code, headers, `JSONResponse`)
- `try/except` for domain errors — let them bubble

---

## Conventions

### Service Pattern

```python
# application/auth_service.py
from app.core.security import hash_password, verify_password, build_token_pair
from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.models import User, UserRole, UserStatus
from app.domain.repositories import AuthRepository
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
        user = await self._repository.find_by_email(email.strip().lower())
        if user is None or not verify_password(password, user.password_hash):
            raise DomainError.invalid_credentials()
        if user.status is UserStatus.SUSPENDED:
            raise DomainError.forbidden("Account is suspended")
        # ... build tokens, create session
        return {"user": _user_dto(user), "tokens": tokens}


def _user_dto(user: User) -> dict[str, str | None]:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role.value,
        "status": user.status.value,
        "photo": user.photo,
    }
```

### Naming

- File name: `{domain}_service.py` — snake_case with `_service` suffix
- Example: `auth_service.py`, `user_service.py`, `order_service.py`
- Class name: `{Domain}Service` — PascalCase

---

## Additional Rules

- Constructor only accepts repository interface (Protocol) + settings — not concrete implementation
- Service has no knowledge of HTTP — do not import FastAPI
- `_to_dto` mapper function is written below the class as a private function (underscore prefix)
- DTO output can be a `dict` or a Pydantic `BaseModel` (see `api-dto.md`)
- Service delegates business rules to use cases — it only orchestrates and maps
- File must end with newline
