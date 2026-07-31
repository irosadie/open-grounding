from datetime import UTC, datetime, timedelta
from hashlib import scrypt, sha256
from hmac import compare_digest
from uuid import uuid4

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.settings import Settings
from app.domain.errors import DomainError
from app.domain.models import UserRole, UserStatus

ACCESS_TOKEN_EXPIRY_SECONDS = 60 * 60
REFRESH_TOKEN_EXPIRY_SECONDS = 7 * 24 * 60 * 60
JWT_ISSUER = "reva-api"
JWT_AUDIENCE = "reva-client"
password_hash = PasswordHash.recommended()
revoked_tokens: set[str] = set()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded_password: str) -> bool:
    if ":" in encoded_password:
        return _verify_legacy_scrypt(password, encoded_password)
    return password_hash.verify(password, encoded_password)


def _verify_legacy_scrypt(password: str, encoded_password: str) -> bool:
    salt_hex, _, expected_hex = encoded_password.partition(":")
    if not salt_hex or not expected_hex:
        return False
    try:
        derived = scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=16384, r=8, p=1, dklen=64)
    except ValueError:
        return False
    return compare_digest(derived.hex(), expected_hex)


def hash_session_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def build_token_pair(*, user_id: str, email: str, role: UserRole, status: UserStatus, session_id: str, settings: Settings) -> dict[str, str | int]:
    access_claims = {
        "id": user_id,
        "email": email,
        "type": role.value.lower(),
        "status": status.value,
        "sessionId": session_id,
    }
    refresh_claims = {"id": user_id, "email": email, "type": role.value.lower(), "sessionId": session_id}
    return {
        "accessToken": _encode(access_claims, settings.jwt_secret, ACCESS_TOKEN_EXPIRY_SECONDS),
        "refreshToken": _encode(refresh_claims, settings.refresh_secret, REFRESH_TOKEN_EXPIRY_SECONDS),
        "expiresIn": ACCESS_TOKEN_EXPIRY_SECONDS,
    }


def _encode(claims: dict[str, str], secret: str, expiry_seconds: int) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {**claims, "iat": now, "exp": now + timedelta(seconds=expiry_seconds), "iss": JWT_ISSUER, "aud": JWT_AUDIENCE},
        secret,
        algorithm="HS256",
    )


def decode_access_token(token: str, settings: Settings) -> dict[str, str]:
    if token in revoked_tokens:
        raise DomainError.invalid_token("Token has been revoked")
    return _decode(token, settings.jwt_secret)


def decode_refresh_token(token: str, settings: Settings) -> dict[str, str]:
    return _decode(token, settings.refresh_secret)


def _decode(token: str, secret: str) -> dict[str, str]:
    try:
        decoded = jwt.decode(token, secret, algorithms=["HS256"], issuer=JWT_ISSUER, audience=JWT_AUDIENCE)
    except InvalidTokenError as error:
        raise DomainError.invalid_token() from error
    if not all(isinstance(decoded.get(field), str) for field in ("id", "email", "type", "sessionId")):
        raise DomainError.invalid_token("Invalid token payload")
    return {key: value for key, value in decoded.items() if isinstance(value, str)}


def new_session_id() -> str:
    return str(uuid4())


def revoke_token(token: str) -> None:
    revoked_tokens.add(token)
