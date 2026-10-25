"""
Query execution schemas — represents a single SQL query run against a data source.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    """Result of SQL validation / safety checks."""

    PENDING = "pending"
    SAFE = "safe"
    BLOCKED = "blocked"
    WARNING = "warning"


class ExecutionStatus(str, Enum):
    """Execution lifecycle status of a query."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class QueryExecutionResponse(BaseModel):
    """Result of executing a generated SQL query."""

    id: uuid.UUID = Field(..., description="Query execution unique identifier")
    sql_query: str = Field(..., description="The SQL that was executed")
    validation_status: ValidationStatus = Field(
        ..., description="Safety validation result"
    )
    validation_details: Optional[Dict[str, Any]] = Field(
        None, description="Details from the validation step"
    )
    execution_status: ExecutionStatus = Field(
        ..., description="Execution lifecycle status"
    )
    result_summary: Optional[str] = Field(
        None, description="AI-generated summary of the results"
    )
    row_count: Optional[int] = Field(
        None, ge=0, description="Number of rows returned"
    )
    column_names: Optional[List[str]] = Field(
        None, description="Column names in the result set"
    )
    execution_time_ms: Optional[float] = Field(
        None, ge=0, description="Wall-clock execution time in milliseconds"
    )
    error_message: Optional[str] = Field(
        None, description="Error details if execution failed"
    )
    executed_at: Optional[datetime] = Field(
        None, description="Timestamp when execution completed"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")

    model_config = {"from_attributes": True}


class QueryResultData(BaseModel):
    """
    Actual data rows from a query execution.

    Separated from QueryExecutionResponse to avoid sending large payloads
    when only metadata is needed.
    """

    columns: List[str] = Field(..., description="Column names")
    rows: List[List[Any]] = Field(..., description="Row data as lists of values")
    truncated: bool = Field(
        default=False,
        description="Whether the result was truncated to MAX_ROWS",
    )
