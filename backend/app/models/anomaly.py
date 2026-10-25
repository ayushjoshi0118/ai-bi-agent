"""
AnomalyDetection model – tracked anomalies found in datasets.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class AnomalySeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyStatus(str, enum.Enum):
    DETECTED = "detected"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class AnomalyDetection(BaseModel):
    __tablename__ = "anomaly_detections"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    metric_value: Mapped[float | None] = mapped_column(
        Float, nullable=True,
    )
    expected_range_low: Mapped[float | None] = mapped_column(
        Float, nullable=True,
    )
    expected_range_high: Mapped[float | None] = mapped_column(
        Float, nullable=True,
    )
    severity: Mapped[AnomalySeverity] = mapped_column(
        Enum(AnomalySeverity, name="anomaly_severity", native_enum=True),
        nullable=False,
        default=AnomalySeverity.MEDIUM,
    )
    status: Mapped[AnomalyStatus] = mapped_column(
        Enum(AnomalyStatus, name="anomaly_status", native_enum=True),
        nullable=False,
        default=AnomalyStatus.DETECTED,
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    detection_metadata: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Algorithm params, z-score, confidence, etc.",
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    @property
    def explanation(self) -> str | None:
        return self.description

    # ── Relationships ────────────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="anomaly_detections",
    )
    dataset: Mapped["Dataset"] = relationship(
        "Dataset", back_populates="anomaly_detections",
    )

    def __repr__(self) -> str:
        return f"<AnomalyDetection {self.metric_name} severity={self.severity}>"
