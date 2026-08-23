"""AES-256-GCM encryption utilities for provider credentials.

Credentials are encrypted at rest using AES-256-GCM with a random IV per write.
The encryption key is derived from SECRET_KEY env var (fallback: JWT_SECRET).

Storage format: base64(iv[12] + ciphertext + tag[16])
"""

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _derive_key(secret: str) -> bytes:
    """Derive a 32-byte AES key from a secret string via SHA-256."""
    return hashlib.sha256(secret.encode()).digest()


def encrypt(value: str, secret: str) -> str:
    """Encrypt a string value. Returns base64-encoded iv+ciphertext+tag."""
    key = _derive_key(secret)
    iv = os.urandom(12)  # 96-bit IV for GCM
    aesgcm = AESGCM(key)
    ciphertext_with_tag = aesgcm.encrypt(iv, value.encode(), None)
    return base64.b64encode(iv + ciphertext_with_tag).decode()


def decrypt(encrypted: str, secret: str) -> str:
    """Decrypt a base64-encoded encrypted value. Returns original string."""
    key = _derive_key(secret)
    raw = base64.b64decode(encrypted.encode())
    iv = raw[:12]
    ciphertext_with_tag = raw[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(iv, ciphertext_with_tag, None)
    return plaintext.decode()


def get_encryption_key(settings: object) -> str:
    """Get the encryption key from settings. Falls back to jwt_secret."""
    secret_key = getattr(settings, "secret_key", None)
    if secret_key:
        return secret_key
    jwt_secret = getattr(settings, "jwt_secret", None)
    if jwt_secret:
        return jwt_secret
    raise RuntimeError("No SECRET_KEY or JWT_SECRET configured for credential encryption.")
