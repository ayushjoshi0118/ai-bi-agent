"""
Fernet-based encryption utilities for storing database credentials at rest.

Uses the ``ENCRYPTION_KEY`` from application settings.  The key must be a
valid 32-byte URL-safe base64-encoded Fernet key.  Generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

logger = structlog.get_logger(__name__)


def _get_fernet() -> Fernet:
    """Return a Fernet instance from the app encryption key."""
    settings = get_settings()
    key = settings.ENCRYPTION_KEY
    if key == "CHANGE-ME-IN-PRODUCTION":
        logger.warning("encryption.insecure_key", msg="Using default encryption key – NOT safe for production")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string and return the ciphertext as a UTF-8 string."""
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a ciphertext string back to plaintext."""
    fernet = _get_fernet()
    try:
        return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.error("encryption.decrypt_failed", msg="Invalid token – key mismatch or corrupted data")
        raise ValueError("Failed to decrypt credentials – encryption key may have changed")


def encrypt_dict(data: dict[str, Any]) -> str:
    """Serialize a dict to JSON and encrypt it."""
    return encrypt_value(json.dumps(data, default=str))


def decrypt_dict(ciphertext: str) -> dict[str, Any]:
    """Decrypt ciphertext and deserialize the JSON payload to a dict."""
    plaintext = decrypt_value(ciphertext)
    return json.loads(plaintext)
