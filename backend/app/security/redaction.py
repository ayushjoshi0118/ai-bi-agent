"""
Security Redaction Utilities.
Redacts secrets, JWT tokens, connection passwords, Fernet keys, and PII from logs and context.
"""

from __future__ import annotations

import re
from typing import Any, Dict

# Regex patterns for sensitive data
SECRET_PATTERNS = [
    # Connection string passwords: protocol://user:pass@host
    (re.compile(r"([a-zA-Z0-9+]+://[^:]+:)([^@]+)(@)", re.IGNORECASE), r"\1***\3"),
    # JWT tokens: eyJ...
    (re.compile(r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b"), "[REDACTED_JWT]"),
    # Authorization header: Bearer ...
    (re.compile(r"(Authorization\s*[:=]\s*Bearer\s+)[^\s,'\"]+", re.IGNORECASE), r"\1[REDACTED_TOKEN]"),
    # API Keys: sk-...
    (re.compile(r"\b(sk-[a-zA-Z0-9]{20,})\b"), "[REDACTED_API_KEY]"),
    # Fernet keys (44-char base64 ending in =)
    (re.compile(r"\b[A-Za-z0-9_-]{43}=\b"), "[REDACTED_FERNET_KEY]"),
    # Credit card numbers
    (re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"), "[REDACTED_CC]"),
    # Social Security Numbers
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
]

SENSITIVE_KEY_NAMES = {
    "password",
    "password_hash",
    "secret",
    "secret_key",
    "jwt_secret_key",
    "encryption_key",
    "llm_api_key",
    "token",
    "access_token",
    "refresh_token",
    "credentials",
    "encrypted_credentials",
    "authorization",
}


def redact_string(val: str) -> str:
    """Redact sensitive patterns from a string."""
    if not isinstance(val, str):
        return str(val)
    res = val
    for pattern, repl in SECRET_PATTERNS:
        res = pattern.sub(repl, res)
    return res


def redact_dictionary(data: Any) -> Any:
    """Recursively redact dictionary keys and values."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if str(k).lower() in SENSITIVE_KEY_NAMES:
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = redact_dictionary(v)
        return cleaned
    elif isinstance(data, list):
        return [redact_dictionary(item) for item in data]
    elif isinstance(data, str):
        return redact_string(data)
    else:
        return data


def structlog_redaction_processor(logger, method_name, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Structlog processor to sanitize all log event dictionaries before formatting."""
    return redact_dictionary(event_dict)
