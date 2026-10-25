"""
Dataset model – profiled tables/views derived from a data source.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class DatasetStatus(str, enum.Enum):
    """Dataset profiling lifecycle."""
    PENDING = "pending"
    PROFILING = "profiling"
    READY = "ready"
    ERROR = "error"


class Dataset(BaseModel):
    __tablename__ = "datasets"

    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    table_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    schema_metadata: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Column names, types, nullable flags, etc.",
    )
    row_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    null_percentages: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Per-column null percentage",
    )
    sample_data: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Small sample of rows for LLM context",
    )
    profiled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    status: Mapped[DatasetStatus] = mapped_column(
        Enum(DatasetStatus, name="dataset_status", native_enum=True),
        nullable=False,
        default=DatasetStatus.PENDING,
    )

    # ── Relationships ────────────────────────────────────────────────────
    data_source: Mapped["DataSource"] = relationship(
        "DataSource", back_populates="datasets",
    )
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="datasets",
    )
    query_executions: Mapped[list["QueryExecution"]] = relationship(
        "QueryExecution", back_populates="dataset", cascade="all, delete-orphan",
    )
    anomaly_detections: Mapped[list["AnomalyDetection"]] = relationship(
        "AnomalyDetection", back_populates="dataset", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Dataset {self.name} ({self.status})>"
