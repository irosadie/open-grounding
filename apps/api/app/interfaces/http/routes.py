from typing import Annotated

from fastapi import APIRouter, Depends, Header, status

from app.core.security import decode_refresh_token
from app.core.settings import Settings, get_settings
from app.interfaces.http.dependencies import (
    AuthContextDependency,
    AuthServiceDependency,
)
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


@system_router.get("/")
async def get_app_info() -> dict[str, object]:
    return success("Application info loaded", {"name": "vibecoding-starter-api", "message": "FastAPI clean architecture API is ready"})


@system_router.get("/health")
async def get_health() -> dict[str, object]:
    from datetime import UTC, datetime

    return success("Health status loaded", {"status": "ok", "service": "vibecoding-starter-api", "timestamp": datetime.now(UTC).isoformat()})


@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, service: AuthServiceDependency) -> dict[str, object]:
    return success("Register success", await service.register(name=payload.name, email=str(payload.email), password=payload.password))


@auth_router.post("/login")
async def login(payload: LoginRequest, service: AuthServiceDependency) -> dict[str, object]:
    return success("Login success", await service.login(email=str(payload.email), password=payload.password))


@auth_router.post("/logout")
async def logout(context: AuthContextDependency, service: AuthServiceDependency) -> dict[str, object]:
    await service.logout(user_id=context["id"], session_id=context["sessionId"], access_token=context["accessToken"])
    return success("Logout success", {"success": True})


@auth_router.get("/me")
async def current_user(context: AuthContextDependency, service: AuthServiceDependency) -> dict[str, object]:
    return success("Current user loaded", await service.current_user(user_id=context["id"], session_id=context["sessionId"]))


@auth_router.post("/refresh")
async def refresh(
    service: AuthServiceDependency,
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    if not authorization or not authorization.startswith("Bearer "):
        from app.domain.errors import DomainError

        raise DomainError.unauthorized()
    refresh_token = authorization.removeprefix("Bearer ").strip()
    decode_refresh_token(refresh_token, settings)
    return success("Token refreshed", await service.refresh(refresh_token))
