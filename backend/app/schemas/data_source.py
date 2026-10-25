"""
Data source connection schemas.

Connection configs are polymorphic — each source type has its own config model.
Credentials are NEVER returned in API responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, SecretStr, field_validator


class DataSourceType(str, Enum):
    """Supported data source types."""

    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    CSV_UPLOAD = "csv_upload"
    EXCEL_UPLOAD = "excel_upload"


class DataSourceStatus(str, Enum):
    """Connection / sync status of a data source."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    SYNCING = "syncing"
    ERROR = "error"


# ── Connection config models ─────────────────────────────────────────────


class PostgresConnectionConfig(BaseModel):
    """Connection details for a PostgreSQL data source."""

    host: str = Field(..., min_length=1, max_length=255, description="Database host")
    port: int = Field(default=5432, ge=1, le=65535, description="Database port")
    database: str = Field(..., min_length=1, max_length=128, description="Database name")
    username: str = Field(..., min_length=1, max_length=128, description="Database user")
    password: SecretStr = Field(..., description="Database password (stored encrypted)")
    schema_name: str = Field(
        default="public", max_length=128, description="PostgreSQL schema"
    )
    ssl_mode: Optional[str] = Field(
        default="prefer",
        description="SSL mode: disable | allow | prefer | require | verify-ca | verify-full",
    )


class MySQLConnectionConfig(BaseModel):
    """Connection details for a MySQL data source."""

    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(default=3306, ge=1, le=65535)
    database: str = Field(..., min_length=1, max_length=128)
    username: str = Field(..., min_length=1, max_length=128)
    password: SecretStr = Field(...)
    ssl_enabled: bool = Field(default=False)


class FileUploadConfig(BaseModel):
    """Config for CSV/Excel file uploads."""

    file_path: str = Field(..., description="Server-side path to the uploaded file")
    original_filename: str = Field(..., description="Original upload filename")
    sheet_name: Optional[str] = Field(
        None, description="Sheet name for Excel files"
    )


ConnectionConfig = Union[
    PostgresConnectionConfig,
    MySQLConnectionConfig,
    FileUploadConfig,
]


# ── Request / Response ───────────────────────────────────────────────────


class DataSourceCreate(BaseModel):
    """Payload to register a new data source."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Human-readable name"
    )
    source_type: DataSourceType = Field(..., description="Type of the data source")
    connection_config: Dict[str, Any] = Field(
        ..., description="Source-type-specific connection parameters"
    )

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class DataSourceResponse(BaseModel):
    """Data source details returned by the API — credentials are excluded."""

    id: uuid.UUID = Field(..., description="Data source unique identifier")
    name: str = Field(..., description="Display name")
    source_type: DataSourceType = Field(..., description="Source type")
    status: DataSourceStatus = Field(..., description="Current connection status")
    created_at: datetime = Field(..., description="Registration timestamp")
    last_synced_at: Optional[datetime] = Field(
        None, description="Last successful sync timestamp"
    )
    table_count: Optional[int] = Field(
        None, description="Number of discovered tables"
    )

    model_config = {"from_attributes": True}


class DataSourceTestResult(BaseModel):
    """Result of testing a data source connection."""

    success: bool = Field(..., description="Whether the connection test succeeded")
    message: str = Field(..., description="Human-readable result message")
    tables_found: Optional[List[str]] = Field(
        None, description="Tables discovered during the connection test"
    )
    latency_ms: Optional[float] = Field(
        None, description="Connection latency in milliseconds"
    )


class DataSourceUpdate(BaseModel):
    """Fields that can be updated on a data source."""

    name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="Updated display name"
    )
    connection_config: Optional[Dict[str, Any]] = Field(
        None, description="Updated connection parameters"
    )
