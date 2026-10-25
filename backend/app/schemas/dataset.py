"""
Dataset schemas — metadata about tables synced from data sources.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class DatasetStatus(str, Enum):
    """Sync / profiling status of a dataset."""

    PENDING = "pending"
    PROFILING = "profiling"
    READY = "ready"
    ERROR = "error"


class ColumnInfo(BaseModel):
    """Schema information about a single column in a dataset."""

    name: str = Field(..., description="Column name")
    data_type: str = Field(..., description="SQL data type (e.g., INTEGER, TEXT)")
    nullable: bool = Field(default=True, description="Whether the column allows NULLs")
    is_primary_key: bool = Field(default=False, description="Whether this is a PK column")
    sample_values: Optional[List[Any]] = Field(
        None, description="Up to 5 sample values from the column"
    )

ColumnInfoSchema = ColumnInfo


class DatasetSchema(BaseModel):
    """Full schema representation of a dataset's columns and metadata."""

    id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    table_name: Optional[str] = None
    row_count: Optional[int] = None
    columns: List[ColumnInfo] = Field(..., description="Ordered list of column definitions")
    sample_data: Optional[List[dict]] = None
    profiled_at: Optional[datetime] = None


class DatasetResponse(BaseModel):
    """Dataset metadata returned by the API."""

    id: uuid.UUID = Field(..., description="Dataset unique identifier")
    org_id: Optional[uuid.UUID] = None
    data_source_id: uuid.UUID = Field(..., description="Parent data source ID")
    name: str = Field(..., description="Table or dataset name")
    description: Optional[str] = Field(None, description="User-supplied description")
    table_name: str = Field(..., description="Actual table name in the data source")
    row_count: Optional[int] = Field(None, description="Number of rows (from last profile)")
    column_count: Optional[int] = Field(None, description="Number of columns")
    status: DatasetStatus = Field(..., description="Current profiling status")
    profiled_at: Optional[datetime] = Field(
        None, description="Last successful profiling timestamp"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}



class DatasetUpdate(BaseModel):
    """Fields that can be updated on a dataset."""

    name: Optional[str] = Field(
        None, min_length=1, max_length=255, description="Updated display name"
    )
    description: Optional[str] = Field(
        None, max_length=1000, description="Updated description"
    )
