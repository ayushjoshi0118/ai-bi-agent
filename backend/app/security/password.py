"""
Password hashing utilities using direct bcrypt library.
Avoids passlib compatibility issues with bcrypt >= 4.1.
"""

from __future__ import annotations

import bcrypt


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password and return the bcrypt hash string."""
    # Ensure password bytes are truncated at 72 bytes as per bcrypt specification
    pwd_bytes = plain_password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a stored bcrypt hash."""
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False
