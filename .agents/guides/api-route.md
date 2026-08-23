# Guide: API Route (`apps/api/app/interfaces/http/routes.py`)

## Folder Contract

✅ Allowed:
- Define `APIRouter` with prefix and tags
- Validate request with Pydantic model (auto-validated by FastAPI)
- Attach dependencies per route (auth, tenant context) via `Depends()`
- Delegate to service method — handler is the controller (see `api-controller.md`)

❌ Forbidden:
- Business logic
- Call use case or repository directly — must go through service
- Format response manually (use `success()` envelope helper)

---

## Conventions

### Router Pattern

```python
# interfaces/http/routes.py
from fastapi import APIRouter, status

from app.interfaces.http.dependencies import AuthContextDependency, AuthServiceDependency
from app.interfaces.http.schemas import LoginRequest, RegisterRequest

system_router = APIRouter(tags=["System"])
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
    return success("Register success", await service.register(name=payload.name, email=str(payload.email), password=payload.password))


@auth_router.post("/login")
async def login(payload: LoginRequest, service: AuthServiceDependency) -> dict[str, object]:
    return success("Login success", await service.login(email=str(payload.email), password=payload.password))
```

### Registration in `main.py`

```python
# main.py
from fastapi import FastAPI
from app.interfaces.http.errors import register_exception_handlers
from app.interfaces.http.routes import auth_router, system_router


def create_app() -> FastAPI:
    app = FastAPI(title="...", version="0.1.0")
    register_exception_handlers(app)
    app.include_router(system_router)
    app.include_router(auth_router)
    return app


app = create_app()
```

### Protected Route with Dependencies

```python
@auth_router.get("/me")
async def current_user(
    context: AuthContextDependency,
    service: AuthServiceDependency,
) -> dict[str, object]:
    return success("Current user loaded", await service.current_user(user_id=context["id"], session_id=context["sessionId"]))
```

### Naming

- File name: `routes.py` (single file) or `routes/{domain}.py` when it grows
- Router variable: `{domain}_router` — `APIRouter(prefix="/{domain}", tags=["{Domain}"])`
- Handler function: verb name — `register`, `login`, `logout`, `current_user`
- Example: `auth_router`, `system_router`

---

## Additional Rules

- Instantiate dependencies via `Depends()` providers defined in `dependencies.py` — not manually in route file
- Use `Annotated[..., Depends()]` type aliases for clean handler signatures
- Pydantic request models are auto-validated — no need for manual validation calls
- File must end with newline
