# Guide: API DTO (`apps/api/app/application/dtos.py`)

## Folder Contract

✅ Allowed:
- Pydantic `BaseModel` for output sent to client
- Subset or transform from Entity (serializable: `str`, `int`, `bool` — not `datetime` object)
- `Field` for response constraints if needed

❌ Forbidden:
- Request/payload validation (that goes in `interfaces/http/schemas.py`)
- Business logic or methods
- SQLAlchemy ORM record types
- Use `Any` for typed fields

---

## Conventions

### DTO Pattern

```python
# application/dtos.py
from pydantic import BaseModel


class UserDto(BaseModel):
    id: str
    email: str
    name: str
    role: str
    status: str
    photo: str | None = None


class TokenPairDto(BaseModel):
    accessToken: str
    refreshToken: str
    expiresIn: int


class UserListDto(BaseModel):
    data: list[UserDto]
    meta: dict[str, int]
```

### DTO Mapper Function

```python
# in application/auth_service.py
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

- File name: `dtos.py` (single file) or `dtos/{domain}.py` when it grows
- Class name: `{Domain}Dto`, `{Domain}ListDto`, `{Domain}DetailDto` — PascalCase with `Dto` suffix
- Example: `UserDto`, `TokenPairDto`, `UserListDto`

---

## Additional Rules

- `datetime` → `str` (ISO format) in DTO for JSON serialization
- Nullable fields use `T | None = None` (Pydantic v2 syntax)
- DTO can be used as `response_model` in FastAPI route handlers for proper OpenAPI generation
- The `_to_dto` mapper function lives in the service file, not the DTO file
- File must end with newline
