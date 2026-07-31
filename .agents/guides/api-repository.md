# Guide: API Repository Interface (`apps/api/app/domain/repositories.py`)

## Folder Contract

✅ Allowed:
- Define `Protocol` class for repository
- Method signature uses Entity types from `domain/models.py`
- Optional filter/pagination types local to each protocol
- All methods are `async`

❌ Forbidden:
- Concrete implementation — that goes in `infrastructure/database.py`
- Import SQLAlchemy
- Business logic

---

## Conventions

### Protocol Pattern

```python
# domain/repositories.py
from datetime import datetime
from typing import Protocol

from app.domain.models import AuthSession, User, UserRole, UserStatus


class UserRepository(Protocol):
    async def find_by_id(self, user_id: str) -> User | None: ...
    async def find_by_email(self, email: str) -> User | None: ...
    async def create(
        self, *, email: str, password_hash: str, name: str, role: UserRole, status: UserStatus, photo: str | None
    ) -> User: ...
    async def update(self, user_id: str, *, name: str) -> User: ...
    async def delete(self, user_id: str) -> None: ...
```

### Filter/Pagination Types

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class UserListFilter:
    search: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    page: int = 1
    limit: int = 10


@dataclass(frozen=True)
class UserListResult:
    data: list[User]
    total: int
```

### Naming

- File name: `repositories.py` (single file for all protocols) or `repositories/{domain}.py` when the file grows
- Protocol name: `{Domain}Repository` — no `I` prefix (Python uses `Protocol`, not `Interface`)
- Example: `UserRepository`, `AuthRepository`, `TenantRepository`

---

## Additional Rules

- Return type is always Entity (from `domain/models.py`), not ORM record
- Method `find_by_id` returns `T | None` (nullable)
- Method `delete` returns `None`
- All methods are `async` — the implementation uses `AsyncSession`
- Use keyword-only arguments (`*,`) for create/update methods to prevent positional argument errors
- File must end with newline
