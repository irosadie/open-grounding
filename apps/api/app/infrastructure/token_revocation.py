"""Redis-backed token revocation store.

Revoked access tokens are stored in Redis with a TTL matching
ACCESS_TOKEN_EXPIRY_SECONDS so the set self-cleans and never grows unbounded.
This is safe for multi-worker and multi-process deployments because all workers
share the same Redis instance.

Key format:  revoked_token:<sha256(token)>
Value:       "1"
TTL:         ACCESS_TOKEN_EXPIRY_SECONDS

The token is hashed before storage so the raw JWT is never persisted in Redis.
"""

import logging
from hashlib import sha256

import redis.asyncio as aioredis

from app.core.security import ACCESS_TOKEN_EXPIRY_SECONDS

logger = logging.getLogger(__name__)

_REVOCATION_PREFIX = "revoked_token:"


def _token_key(token: str) -> str:
    return f"{_REVOCATION_PREFIX}{sha256(token.encode()).hexdigest()}"


async def revoke_token_redis(token: str, redis_url: str) -> None:
    """Mark a token as revoked in Redis with TTL = ACCESS_TOKEN_EXPIRY_SECONDS."""
    client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        await client.set(_token_key(token), "1", ex=ACCESS_TOKEN_EXPIRY_SECONDS)
        logger.debug("Token revoked in Redis (key=%s)", _token_key(token))
    except Exception:
        logger.exception("Failed to revoke token in Redis — falling back to in-process store")
        # Fallback: keep in-process set so logout is still effective within
        # the current worker process even if Redis is temporarily unavailable.
        from app.core.security import revoked_tokens
        revoked_tokens.add(token)
    finally:
        await client.aclose()


async def is_token_revoked_redis(token: str, redis_url: str) -> bool:
    """Return True if the token has been revoked (checked against Redis)."""
    client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        result = await client.exists(_token_key(token))
        return bool(result)
    except Exception:
        logger.exception("Failed to check token revocation in Redis — falling back to in-process store")
        # Fallback: check in-process set.
        from app.core.security import revoked_tokens
        return token in revoked_tokens
    finally:
        await client.aclose()
