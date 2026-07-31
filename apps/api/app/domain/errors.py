from dataclasses import dataclass
from typing import Any


@dataclass
class DomainError(Exception):
    code: str
    message: str
    status_code: int
    details: Any | None = None

    @classmethod
    def invalid_credentials(cls) -> "DomainError":
        return cls("INVALID_CREDENTIALS", "Invalid email or password", 401)

    @classmethod
    def invalid_token(cls, message: str = "Invalid or expired token") -> "DomainError":
        return cls("INVALID_TOKEN", message, 401)

    @classmethod
    def unauthorized(cls, message: str = "Authorization token required") -> "DomainError":
        return cls("UNAUTHORIZED", message, 401)

    @classmethod
    def forbidden(cls, message: str) -> "DomainError":
        return cls("FORBIDDEN", message, 403)

    @classmethod
    def duplicate_email(cls) -> "DomainError":
        return cls("DUPLICATE_EMAIL", "Email already registered", 409)

    @classmethod
    def user_not_found(cls) -> "DomainError":
        return cls("USER_NOT_FOUND", "User not found", 404)
