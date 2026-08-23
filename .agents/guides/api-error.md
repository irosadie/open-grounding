# Guide: API Domain Error (`apps/api/app/domain/errors.py`)

## Folder Contract

✅ Allowed:
- Define `DomainError` as a `@dataclass` that extends `Exception`
- Class methods for common error types (factory pattern)
- Error codes as string constants

❌ Forbidden:
- Import from FastAPI or HTTP library
- HTTP error handling here — that goes in exception handlers (`interfaces/http/errors.py`)
- Raise `HTTPException` — use `DomainError`

---

## Conventions

### DomainError

```python
# domain/errors.py
from dataclasses import dataclass
from typing import Any


@dataclass
class DomainError(Exception):
    code: str
    message: str
    status_code: int
    details: Any | None = None

    @classmethod
    def duplicate_email(cls) -> "DomainError":
        return cls("DUPLICATE_EMAIL", "Email already registered", 409)

    @classmethod
    def user_not_found(cls) -> "DomainError":
        return cls("USER_NOT_FOUND", "User not found", 404)

    @classmethod
    def unauthorized(cls, message: str = "Authorization token required") -> "DomainError":
        return cls("UNAUTHORIZED", message, 401)

    @classmethod
    def forbidden(cls, message: str) -> "DomainError":
        return cls("FORBIDDEN", message, 403)

    @classmethod
    def invalid_credentials(cls) -> "DomainError":
        return cls("INVALID_CREDENTIALS", "Invalid email or password", 401)

    @classmethod
    def invalid_token(cls, message: str = "Invalid or expired token") -> "DomainError":
        return cls("INVALID_TOKEN", message, 401)
```

### Exception Handler

```python
# interfaces/http/errors.py
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.errors import DomainError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, error: DomainError) -> JSONResponse:
        details = error.details if isinstance(error.details, dict) else {}
        return JSONResponse(
            status_code=error.status_code,
            content={"success": False, "errors": [{"code": error.code, "message": error.message, **details}]},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        errors = [
            {"code": "VALIDATION_ERROR", "message": item["msg"], "path": ".".join(str(p) for p in item["loc"] if p != "body")}
            for item in error.errors()
        ]
        return JSONResponse(status_code=422, content={"success": False, "errors": errors})

    @app.exception_handler(Exception)
    async def handle_unknown_error(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"success": False, "errors": [{"code": "INTERNAL_SERVER_ERROR", "message": "Internal Server Error"}]})
```

### Usage in Use Case

```python
from app.domain.errors import DomainError

raise DomainError.duplicate_email()
raise DomainError.user_not_found()
raise DomainError.forbidden("Insufficient permissions")
```

---

## Additional Rules

- Always use class method factories — do not instantiate `DomainError(code, message, status_code)` directly outside `errors.py`
- Error codes are always `SCREAMING_SNAKE_CASE`
- The `status_code` is mapped at the error definition, not in the handler — the handler just reads `error.status_code`
- `DomainError` bubbles up through service → handler → `@app.exception_handler(DomainError)` → JSON response
- Do not `try/except DomainError` in service or handler — let it bubble
- File must end with newline
