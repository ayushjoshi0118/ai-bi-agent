"""
DataSource model – external database / file connections.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class SourceType(str, enum.Enum):
    """Supported data-source types."""
    CSV = "csv"
    XLSX = "xlsx"
    POSTGRESQL = "postgresql"

DataSourceType = SourceType



class DataSourceStatus(str, enum.Enum):
    """Connection lifecycle states."""
    PENDING = "pending"
    CONNECTED = "connected"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class DataSource(BaseModel):
    __tablename__ = "data_sources"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type", native_enum=False, length=50),
        nullable=False,
    )
    encrypted_credentials: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True,
    )
    connection_config: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict,
    )
    status: Mapped[DataSourceStatus] = mapped_column(
        Enum(DataSourceStatus, name="data_source_status", native_enum=False, length=50),
        nullable=False,
        default=DataSourceStatus.PENDING,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="data_sources",
    )
    datasets: Mapped[list["Dataset"]] = relationship(
        "Dataset", back_populates="data_source", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DataSource {self.name} ({self.source_type})>"
