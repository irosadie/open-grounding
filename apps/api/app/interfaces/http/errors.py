from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.audit import AuditAction
from app.domain.errors import DomainError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, error: DomainError) -> JSONResponse:
        details = error.details if isinstance(error.details, dict) else {}
        _audit_security_relevant_denial(request, error)
        return JSONResponse(
            status_code=error.status_code,
            content={"success": False, "errors": [{"code": error.code, "message": error.message, **details}]},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        errors = [{"code": "VALIDATION_ERROR", "message": item["msg"], "path": ".".join(str(part) for part in item["loc"] if part != "body"), "type": item["type"]} for item in error.errors()]
        return JSONResponse(status_code=422, content={"success": False, "errors": errors})

    @app.exception_handler(Exception)
    async def handle_unknown_error(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"success": False, "errors": [{"code": "INTERNAL_SERVER_ERROR", "message": "Internal Server Error"}]})


def _audit_security_relevant_denial(request: Request, error: DomainError) -> None:
    """Record an audit event for security-relevant access denials (401, 403)."""
    if error.status_code not in {401, 403}:
        return

    from app.infrastructure.audit import record_audit_event

    action = AuditAction.ACCESS_DENIED
    if error.code == "TENANT_MEMBERSHIP_INACTIVE":
        action = AuditAction.MEMBERSHIP_INACTIVE
    elif error.code == "TENANT_MISMATCH":
        action = AuditAction.TENANT_MISMATCH

    actor_id = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from app.core.security import decode_access_token
            from app.core.settings import get_settings

            token = auth_header.removeprefix("Bearer ").strip()
            payload = decode_access_token(token, get_settings())
            actor_id = payload.get("id")
        except DomainError:
            pass

    tenant_id = details_value(error.details, "configuredTenantId") or details_value(error.details, "persistedTenantId")

    trace_id = request.headers.get("x-trace-id") or request.headers.get("x-request-id")

    record_audit_event(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        resource_type="auth",
        trace_id=trace_id,
        details={"code": error.code, "path": str(request.url.path), "method": request.method},
    )


def details_value(details: object, key: str) -> str | None:
    if isinstance(details, dict):
        value = details.get(key)
        return str(value) if value is not None else None
    return None
