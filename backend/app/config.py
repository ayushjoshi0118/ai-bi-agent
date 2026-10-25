"""
Application configuration using Pydantic Settings.

All settings are read from environment variables with sensible defaults
for local development. In production, set these via .env or container env.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────
    APP_NAME: str = "BI Agent"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENVIRONMENT: str = Field(default="development", description="development | staging | production")

    # ── Database (PostgreSQL) ────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/bi_agent",
        description="Async database URL (asyncpg driver)",
    )
    DATABASE_URL_SYNC: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/bi_agent",
        description="Sync database URL for Alembic / Celery",
    )
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_ECHO: bool = False

    # ── Redis ────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = Field(default=300, description="Default cache TTL in seconds")

    # ── JWT / Auth ───────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(
        default="CHANGE-ME-IN-PRODUCTION",
        description="Secret key for signing JWTs",
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Encryption ───────────────────────────────────────────────────────
    ENCRYPTION_KEY: str = Field(
        default="CHANGE-ME-IN-PRODUCTION",
        description="Fernet key for encrypting stored credentials",
    )

    # ── LLM / AI ─────────────────────────────────────────────────────────
    LLM_PROVIDER: str = Field(default="openai", description="openai | google | anthropic")
    LLM_MODEL: str = "gpt-4o"
    LLM_API_KEY: str = ""
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 4096
    LLM_REQUEST_TIMEOUT: int = 60

    # ── Upload Limits ────────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = Field(
        default=[".csv", ".xlsx", ".xls"],
    )
    UPLOAD_DIR: str = "uploads"

    # ── Query Safety ─────────────────────────────────────────────────────
    QUERY_MAX_ROWS: int = Field(default=10_000, description="Max rows returned per query")
    QUERY_TIMEOUT_SECONDS: int = Field(default=30, description="SQL execution timeout")
    QUERY_MAX_COST_ESTIMATE: int = Field(default=1_000_000, description="Max estimated cost threshold")
    QUERY_BLOCKED_KEYWORDS: List[str] = Field(
        default=["DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE", "GRANT", "REVOKE"],
    )

    # ── CORS ─────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
    )
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = Field(default=["*"])
    CORS_ALLOW_HEADERS: List[str] = Field(default=["*"])

    # ── Rate Limiting ────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 20

    # ── Celery ───────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_TASK_SOFT_TIME_LIMIT: int = 300
    CELERY_TASK_TIME_LIMIT: int = 600

    # ── Sentry (optional) ────────────────────────────────────────────────
    SENTRY_DSN: str = ""
    LOG_LEVEL: str = "INFO"

    def __getattr__(self, name: str):
        # Allow case-insensitive attribute access
        upper_name = name.upper()
        if upper_name in self.__dict__:
            return self.__dict__[upper_name]
        if upper_name == "APP_ENV":
            return self.ENVIRONMENT
        if upper_name == "RATE_LIMIT_REQUESTS_PER_MINUTE":
            return self.RATE_LIMIT_PER_MINUTE
        if upper_name == "LLM_TIMEOUT_SECONDS":
            return self.LLM_REQUEST_TIMEOUT
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


    # ── Validators ───────────────────────────────────────────────────────
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list) -> list:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("QUERY_BLOCKED_KEYWORDS", mode="before")
    @classmethod
    def parse_blocked_keywords(cls, v: str | list) -> list:
        if isinstance(v, str):
            return [kw.strip() for kw in v.split(",") if kw.strip()]
        return v

    @field_validator("ALLOWED_UPLOAD_EXTENSIONS", mode="before")
    @classmethod
    def parse_upload_extensions(cls, v: str | list) -> list:
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(",") if ext.strip()]
        return v

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of application settings."""
    return Settings()
