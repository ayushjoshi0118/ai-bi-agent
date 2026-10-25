"""
Pydantic schemas for Anomaly Detection.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.anomaly import AnomalySeverity, AnomalyStatus


class AnomalyScanRequest(BaseModel):
    dataset_id: uuid.UUID
    metric_column: str
    time_column: Optional[str] = None
    method: str = Field(
        default="z_score",
        description="Detection method: z_score, iqr, moving_average, period_over_period",
    )
    sensitivity: str = Field(
        default="medium",
        description="low, medium, high",
    )
    min_sample_size: int = Field(default=10, ge=3)


class AnomalyResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    dataset_id: uuid.UUID
    metric_name: str
    metric_value: Optional[float]
    expected_value: Optional[float]
    deviation_score: Optional[float]
    severity: AnomalySeverity
    status: AnomalyStatus
    detection_method: str
    dimension_filters: Optional[Dict[str, Any]]
    explanation: Optional[str]
    supporting_data: Optional[Dict[str, Any]]
    detected_at: datetime
    acknowledged_by: Optional[uuid.UUID]
    acknowledged_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class AnomalyStatusUpdate(BaseModel):
    status: AnomalyStatus
