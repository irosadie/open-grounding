# Guide: API Use Case (`apps/api/app/domain/use_cases/`)

## Folder Contract

✅ Allowed:
- One business logic operation per file
- Throw `DomainError` for expected errors (not found, conflict, unauthorized)
- Call repository interface (Protocol), not concrete implementation
- Validate business rules: check duplicates, domain authorization, etc.

❌ Forbidden:
- Access SQLAlchemy or database directly
- Import from FastAPI or HTTP library
- Raise `HTTPException` — use `DomainError`
- Orchestrate multiple domain operations — that's the service's job

---

## Conventions

### Structure

```
domain/use_cases/
├── __init__.py
├── register_user.py
├── login_user.py
├── get_user_by_id.py
└── delete_user.py
```

### Use Case Pattern

```python
# domain/use_cases/register_user.py
from app.domain.errors import DomainError
from app.domain.models import User, UserRole, UserStatus
from app.domain.repositories import UserRepository


async def register_user(
    repo: UserRepository, *, email: str, password_hash: str, name: str
) -> User:
    existing = await repo.find_by_email(email)
    if existing:
        raise DomainError.duplicate_email()
    return await repo.create(
        email=email,
        password_hash=password_hash,
        name=name,
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
        photo=None,
    )
```

### Use Case with Auth Check

```python
# domain/use_cases/delete_user.py
from app.domain.errors import DomainError
from app.domain.repositories import UserRepository


async def delete_user(
    repo: UserRepository, user_id: str, requester_id: str
) -> None:
    user = await repo.find_by_id(user_id)
    if user is None:
        raise DomainError.user_not_found()
    if user.id != requester_id:
        raise DomainError.forbidden("Cannot delete other user")
    await repo.delete(user_id)
```

### Naming

- File name: `{verb}_{domain}.py` — snake_case, starts with verb
- Example: `register_user.py`, `get_user_by_id.py`, `cancel_shipment.py`
- Export: `async def` function (not class)

---

## Additional Rules

- First parameter is always the repository Protocol — dependency injection via parameter
- Use keyword-only arguments (`*,`) for the remaining parameters
- Use cases are `async` functions — they `await` repository calls
- Use cases are reusable across delivery mechanisms (HTTP, worker, CLI) — they have no HTTP/framework dependency
- Input type can be defined locally in the use case file or imported from domain models
- File must end with newline
