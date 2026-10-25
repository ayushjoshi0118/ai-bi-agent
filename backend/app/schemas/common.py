"""
Common response schemas used across all API endpoints.

Provides standardized error, success, and paginated response wrappers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Individual error detail within an error response."""

    field: Optional[str] = Field(None, description="Field that caused the error, if applicable")
    message: str = Field(..., description="Human-readable error message")
    code: Optional[str] = Field(None, description="Machine-readable error code")


class ErrorResponse(BaseModel):
    """Standard error response returned by all endpoints on failure."""

    error: bool = Field(default=True, description="Always True for error responses")
    message: str = Field(..., description="Top-level error summary")
    details: Optional[List[ErrorDetail]] = Field(
        None, description="List of individual error details"
    )
    request_id: Optional[str] = Field(None, description="Correlation ID for tracing")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Time the error occurred"
    )

    model_config = {"json_schema_extra": {"examples": [{"error": True, "message": "Not found"}]}}


class SuccessResponse(BaseModel):
    """Standard success response wrapper."""

    success: bool = Field(default=True, description="Always True for success responses")
    message: str = Field(default="Operation completed successfully")
    data: Optional[Any] = Field(None, description="Optional payload")


class PaginationMeta(BaseModel):
    """Pagination metadata included in paginated responses."""

    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(..., ge=1, le=100, description="Items per page")
    total_items: int = Field(..., ge=0, description="Total number of items")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether a next page exists")
    has_previous: bool = Field(..., description="Whether a previous page exists")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response wrapper.

    Usage::

        PaginatedResponse[UserResponse]
    """

    items: List[T] = Field(..., description="List of items on the current page")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")

    model_config = {"arbitrary_types_allowed": True}


class PaginationParams(BaseModel):
    """Query parameters for paginated endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
