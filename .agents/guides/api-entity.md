# Guide: API Entity (`apps/api/app/domain/models.py`)

## Folder Contract

✅ Allowed:
- Python `@dataclass(frozen=True)` that represents a domain model
- Domain-specific fields — not database columns
- Pure domain methods (calculations, internal validation)
- `StrEnum` for fixed-value fields (roles, statuses)

❌ Forbidden:
- Import SQLAlchemy types or ORM records
- HTTP or database dependencies
- Business logic that changes per use case — put that in use cases

---

## Conventions

### Entity as Frozen Dataclass

```python
# domain/models.py
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class UserRole(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


@dataclass(frozen=True)
class User:
    id: str
    email: str
    password_hash: str
    name: str
    role: UserRole
    status: UserStatus
    photo: str | None
    created_at: datetime
    updated_at: datetime
```

### Enum via StrEnum

```python
class TenantStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
```

Values are always `SCREAMING_SNAKE_CASE`.

### Naming

- File name: `models.py` (single file for all entities) or `models/{domain}.py` when the file grows
- Entity class: PascalCase, no suffix — `User`, `Order`, `TenantMembership`
- Enum class: PascalCase — `UserRole`, `UserStatus`, `TenantStatus`

---

## Additional Rules

- Entity is the source of truth for the domain — not a mirror of the ORM record
- Python convention is `snake_case` for fields — Entity and ORM record use the same field names
- Use `@dataclass(frozen=True)` for immutability — entities should not be mutated after creation
- Use primitive types (`str`, `int`, `datetime`, `bool`) — not SQLAlchemy column types
- Use `StrEnum` for any field with a fixed set of string values
- File must end with newline
