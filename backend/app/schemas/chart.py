"""
Chart specification schemas for frontend visualization rendering.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

HTML_TAG_REGEX = re.compile(r"<[^>]*>|javascript:|onerror=|onload=", re.IGNORECASE)
SAFE_IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z0-9_.\- ()%$/]+$")


def sanitize_text(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    if HTML_TAG_REGEX.search(text):
        raise ValueError("Malicious markup or script detected in chart metadata")
    return text.strip()


class ChartType(str, Enum):
    """Supported chart types for the BI dashboard."""

    LINE = "line"
    BAR = "bar"
    STACKED_BAR = "stacked_bar"
    SCATTER = "scatter"
    TABLE = "table"
    KPI_CARD = "kpi_card"


class AxisConfig(BaseModel):
    """Configuration for a chart axis."""

    field: str = Field(..., description="Column name mapped to this axis")
    label: Optional[str] = Field(None, description="Display label for the axis")
    format: Optional[str] = Field(
        None, description="Format string (e.g., ',.0f' for integers, '.2%' for pct)"
    )
    sort: Optional[str] = Field(
        None, description="Sort order: 'asc' | 'desc' | None"
    )

    @field_validator("field", "label")
    @classmethod
    def validate_fields(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_text(v)


class SeriesConfig(BaseModel):
    """Configuration for a data series (used in multi-series charts)."""

    field: str = Field(..., description="Column name for the series values")
    label: Optional[str] = Field(None, description="Display name for the series")
    color: Optional[str] = Field(
        None, description="Hex color code (e.g., '#4A90D9')"
    )
    aggregate: Optional[str] = Field(
        None, description="Aggregation function: sum | avg | count | min | max"
    )

    @field_validator("field", "label")
    @classmethod
    def validate_series_text(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_text(v)


class ChartFilter(BaseModel):
    """A filter applied to chart data."""

    field: str = Field(..., description="Column name to filter on")
    operator: str = Field(
        ..., description="Filter operator: eq | ne | gt | gte | lt | lte | in | between"
    )
    value: Any = Field(..., description="Filter value")


class ChartSpec(BaseModel):
    """
    Complete chart specification sent to the frontend for rendering.

    The frontend chart component consumes this to render the appropriate
    visualization without additional server calls.
    """

    chart_type: ChartType = Field(..., description="Type of chart to render")
    title: str = Field(..., max_length=255, description="Chart title")
    subtitle: Optional[str] = Field(None, max_length=500, description="Chart subtitle")
    x_axis: Optional[AxisConfig] = Field(
        None, description="X-axis configuration (not used for KPI cards)"
    )
    y_axis: Optional[AxisConfig] = Field(
        None, description="Y-axis configuration (not used for KPI cards)"
    )
    series: Optional[List[SeriesConfig]] = Field(
        None, description="Data series configurations"
    )
    data: List[Dict[str, Any]] = Field(
        ..., description="Chart data as list of row dicts"
    )
    filters: Optional[List[ChartFilter]] = Field(
        None, description="Filters applied to produce this chart"
    )
    # KPI card specific fields
    kpi_value: Optional[str] = Field(
        None, description="Primary KPI value (for kpi_card type)"
    )
    kpi_change: Optional[str] = Field(
        None, description="KPI change indicator (e.g., '+12.5%')"
    )
    kpi_change_direction: Optional[str] = Field(
        None, description="'up' | 'down' | 'neutral'"
    )
    insights: Optional[str] = Field(
        None, description="AI-generated insight about the chart data"
    )

    @field_validator("title", "subtitle", "kpi_value", "insights")
    @classmethod
    def validate_chart_text(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_text(v)
