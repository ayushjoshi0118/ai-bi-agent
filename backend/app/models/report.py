"""
Report, ReportVersion, and SavedAnalysis models.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ReportStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Report(BaseModel):
    __tablename__ = "reports"

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
    title: Mapped[str] = mapped_column(
        String(500), nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status", native_enum=True),
        nullable=False,
        default=ReportStatus.DRAFT,
    )
    config: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Layout, chart configs, filters, etc.",
    )

    # ── Relationships ────────────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="reports",
    )
    versions: Mapped[list["ReportVersion"]] = relationship(
        "ReportVersion", back_populates="report", cascade="all, delete-orphan",
        order_by="ReportVersion.version_number",
    )

    def __repr__(self) -> str:
        return f"<Report {self.title[:40]}>"


class ReportVersion(BaseModel):
    __tablename__ = "report_versions"

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
    )
    content: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Full report snapshot at this version",
    )
    change_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    report: Mapped["Report"] = relationship(
        "Report", back_populates="versions",
    )

    def __repr__(self) -> str:
        return f"<ReportVersion report={self.report_id} v{self.version_number}>"


class SavedAnalysis(BaseModel):
    __tablename__ = "saved_analyses"

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
    title: Mapped[str] = mapped_column(
        String(500), nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    analysis_data: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Query results, chart configs, insights",
    )
    tags: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=list,
        comment="Searchable tags as a JSON array",
    )
    is_pinned: Mapped[bool] = mapped_column(
        default=False, server_default="false", nullable=False,
    )

    @property
    def user_id(self) -> uuid.UUID | None:
        return self.created_by

    @property
    def query_execution_id(self) -> uuid.UUID | None:
        if self.analysis_data and self.analysis_data.get("query_execution_id"):
            try:
                return uuid.UUID(str(self.analysis_data["query_execution_id"]))
            except (ValueError, TypeError):
                return None
        return None

    @property
    def chart_config(self) -> dict | None:
        return self.analysis_data.get("chart_config") if self.analysis_data else None

    def __repr__(self) -> str:
        return f"<SavedAnalysis {self.title[:40]}>"
