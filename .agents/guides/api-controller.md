# Guide: API Controller Contract (`apps/api/app/interfaces/http/routes.py`)

> **Note:** In this hybrid 4-hop architecture, the controller is **inline** — the FastAPI route handler IS the controller. There is no separate controller class or folder. This guide defines the **contract** that every route handler must follow.

## Folder Contract

✅ Allowed (route handler):
- Parse request via Pydantic model (auto-validated by FastAPI)
- Call service method
- Format and return response via `success()` envelope helper
- Use `Annotated[..., Depends()]` for dependency injection

❌ Forbidden (route handler):
- Business logic — that goes in service and use case
- Call use case or repository directly — must go through service
- `try/except` for domain errors — let them bubble to `@app.exception_handler(DomainError)`
- Import SQLAlchemy or domain infrastructure

---

## Conventions

### Route Handler = Controller

```python
# interfaces/http/routes.py
from typing import Annotated

from fastapi import APIRouter, Depends, Header, status

from app.interfaces.http.dependencies import AuthServiceDependency
from app.interfaces.http.schemas import LoginRequest, RegisterRequest

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


def success(message: str, data: object | None = None, meta: object | None = None) -> dict[str, object]:
    response: dict[str, object] = {"success": True, "message": message}
    if data is not None:
        response["data"] = data
    if meta is not None:
        response["meta"] = meta
    return response


@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, service: AuthServiceDependency) -> dict[str, object]:
    return success(
        "Register success",
        await service.register(name=payload.name, email=str(payload.email), password=payload.password),
    )


@auth_router.post("/login")
async def login(payload: LoginRequest, service: AuthServiceDependency) -> dict[str, object]:
    return success(
        "Login success",
        await service.login(email=str(payload.email), password=payload.password),
    )
```

### Controller Contract Summary

| Responsibility | Where it happens |
|---|---|
| Parse request body/query/params | Pydantic model (auto-validated by FastAPI before handler) |
| Authentication/authorization | `Depends()` dependency (e.g., `AuthContextDependency`) |
| Call business logic | Service method |
| Format response | `success()` envelope helper |
| Error handling | `@app.exception_handler(DomainError)` (bubbles up) |

### Naming

- File name: `routes.py` (single file) or `routes/{domain}.py` when it grows
- Router variable: `{domain}_router` — `APIRouter(prefix="/{domain}", tags=["{Domain}"])`
- Handler function: verb name — `register`, `login`, `logout`, `current_user`
- Example: `auth_router`, `system_router`

---

## Additional Rules

- The route handler is thin — parse, call service, return envelope
- All data transformation is in service, all business logic is in use case
- Dependency injection via `Annotated[..., Depends()]` type aliases (defined in `dependencies.py`)
- Use `status.HTTP_201_CREATED` etc. from `fastapi import status` for status codes
- File must end with newline
