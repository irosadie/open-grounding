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


@dataclass(frozen=True)
class AuthSession:
    id: str
    user_id: str
    token_hash: str
    expires_at: datetime
    created_at: datetime
