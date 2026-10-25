"""
Pydantic schemas for Scheduled Jobs and Job Runs.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.scheduled_job import JobRunStatus, JobType


class ScheduledJobCreate(BaseModel):
    job_type: JobType
    name: str = Field(..., max_length=255)
    schedule_cron: str = Field(..., description="Standard 5-part cron syntax")
    timezone: str = Field(default="UTC")
    config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Parameters for the job, e.g. report_id or dataset_id & metric",
    )


class ScheduledJobUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    schedule_cron: Optional[str] = None
    timezone: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class JobRunResponse(BaseModel):
    id: uuid.UUID
    scheduled_job_id: uuid.UUID
    status: JobRunStatus
    started_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ScheduledJobResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    created_by: Optional[uuid.UUID]
    name: str
    job_type: JobType
    config: Optional[Dict[str, Any]]
    schedule_cron: str
    timezone: str
    is_active: bool
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    latest_run: Optional[JobRunResponse] = None

    model_config = {"from_attributes": True}
