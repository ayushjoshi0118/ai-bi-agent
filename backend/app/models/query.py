"""
QueryExecution model – tracks every SQL query the system generates/runs.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ValidationStatus(str, enum.Enum):
    PENDING = "pending"
    VALID = "valid"
    REJECTED = "rejected"


class ExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class QueryExecution(BaseModel):
    __tablename__ = "query_executions"

    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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
    sql_query: Mapped[str] = mapped_column(
        Text, nullable=False,
    )

    # ── Validation ───────────────────────────────────────────────────────
    validation_status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, name="validation_status", native_enum=True),
        nullable=False,
        default=ValidationStatus.PENDING,
    )
    validation_details: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict,
    )

    # ── Execution ────────────────────────────────────────────────────────
    execution_status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, name="execution_status", native_enum=True),
        nullable=False,
        default=ExecutionStatus.PENDING,
    )
    result_summary: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Aggregated stats about the result set",
    )
    result_data: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Actual query results (truncated to QUERY_MAX_ROWS)",
    )
    row_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    execution_time_ms: Mapped[float | None] = mapped_column(
        Float, nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    message: Mapped["Message | None"] = relationship(
        "Message", back_populates="query_executions",
    )
    dataset: Mapped["Dataset"] = relationship(
        "Dataset", back_populates="query_executions",
    )

    def __repr__(self) -> str:
        return f"<QueryExecution {self.id} status={self.execution_status}>"
