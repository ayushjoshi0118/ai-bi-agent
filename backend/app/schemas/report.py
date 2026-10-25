"""
Pydantic schemas for Reports, Saved Analyses, and Report Versions.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.report import ReportStatus
from app.schemas.chart import ChartSpec


class SavedAnalysisCreate(BaseModel):
    title: str = Field(..., max_length=500)
    description: Optional[str] = None
    conversation_id: Optional[uuid.UUID] = None
    query_execution_id: Optional[uuid.UUID] = None
    chart_config: Optional[Dict[str, Any]] = None


class SavedAnalysisResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: Optional[uuid.UUID]
    title: str
    description: Optional[str]
    conversation_id: Optional[uuid.UUID]
    query_execution_id: Optional[uuid.UUID]
    chart_config: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReportCreate(BaseModel):
    title: str = Field(..., max_length=500)
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Layout, saved analysis IDs, chart configurations, filters",
    )


class ReportUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    status: Optional[ReportStatus] = None
    config: Optional[Dict[str, Any]] = None


class ReportVersionResponse(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID
    version_number: int
    content: Optional[Dict[str, Any]]
    data_snapshot: Optional[Dict[str, Any]]
    generated_at: datetime

    model_config = {"from_attributes": True}


class ReportResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    created_by: Optional[uuid.UUID]
    title: str
    description: Optional[str]
    status: ReportStatus
    config: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    latest_version: Optional[ReportVersionResponse] = None

    model_config = {"from_attributes": True}
