# Guide: API Request Schema (`apps/api/app/interfaces/http/schemas.py`)

## Folder Contract

✅ Allowed:
- Pydantic `BaseModel` for request validation (body, query, params)
- Field constraints via `Field(min_length=..., max_length=...)`
- `EmailStr` for email validation
- Group by domain in a single file or split to `schemas/{domain}.py` when it grows

❌ Forbidden:
- Business logic or database queries
- Import from `domain/` or `infrastructure/`
- Use `Any` for typed fields

---

## Conventions

### Request Schema Pattern

```python
# interfaces/http/schemas.py
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
```

### Query Parameter Schema

```python
class ListUserQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=10, ge=1, le=100)
    search: str | None = None
    role: str | None = None
```

### Success Envelope Schema

```python
class SuccessEnvelope(BaseModel):
    success: bool = True
    message: str
    data: Any | None = None
    meta: Any | None = None
```

### Naming

- File name: `schemas.py` (single file) or `schemas/{domain}.py` when it grows
- Class name: `{Action}{Domain}Request` or `{Domain}Query` — PascalCase
- Example: `RegisterRequest`, `LoginRequest`, `ListUserQuery`

---

## Additional Rules

- Pydantic v2 is the validation layer — it replaces Zod from the TypeScript stack
- FastAPI automatically validates request bodies against the Pydantic model before the handler runs
- Validation errors are caught by the `RequestValidationError` exception handler in `interfaces/http/errors.py`
- Use `Field(...)` for constraints — `min_length`, `max_length`, `ge`, `le`, `pattern`
- Use `EmailStr` for email fields (requires `email-validator` package)
- Optional fields use `T | None = None` (Pydantic v2 syntax)
- File must end with newline
