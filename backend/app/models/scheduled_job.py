"""
ScheduledJob and JobRun models – recurring tasks (reports, anomaly scans).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class JobType(str, enum.Enum):
    REPORT = "report"
    ANOMALY_SCAN = "anomaly_scan"


class JobRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScheduledJob(BaseModel):
    __tablename__ = "scheduled_jobs"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    job_type: Mapped[JobType] = mapped_column(
        Enum(JobType, name="job_type", native_enum=True),
        nullable=False,
    )
    config: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Job-specific configuration payload",
    )
    schedule_cron: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Standard 5-field cron expression",
    )
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="UTC",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False,
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="scheduled_jobs",
    )
    runs: Mapped[list["JobRun"]] = relationship(
        "JobRun", back_populates="scheduled_job", cascade="all, delete-orphan",
        order_by="JobRun.created_at.desc()",
    )

    def __repr__(self) -> str:
        return f"<ScheduledJob {self.job_type} cron={self.schedule_cron}>"


class JobRun(BaseModel):
    __tablename__ = "job_runs"

    scheduled_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheduled_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[JobRunStatus] = mapped_column(
        Enum(JobRunStatus, name="job_run_status", native_enum=True),
        nullable=False,
        default=JobRunStatus.PENDING,
    )
    result: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    scheduled_job: Mapped["ScheduledJob"] = relationship(
        "ScheduledJob", back_populates="runs",
    )

    def __repr__(self) -> str:
        return f"<JobRun {self.id} status={self.status}>"
