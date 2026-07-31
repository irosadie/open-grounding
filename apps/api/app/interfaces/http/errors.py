from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.errors import DomainError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, error: DomainError) -> JSONResponse:
        details = error.details if isinstance(error.details, dict) else {}
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
