"""
Notification model – in-app notifications for users.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Notification(BaseModel):
    __tablename__ = "notifications"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500), nullable=False,
    )
    message: Mapped[str] = mapped_column(
        Text, nullable=False,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False,
    )
    notification_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="info",
        comment="info | warning | error | success | anomaly | report",
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="e.g. report, anomaly, dataset",
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(
        "User", back_populates="notifications",
    )
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="notifications",
    )

    def __repr__(self) -> str:
        return f"<Notification {self.title[:40]} read={self.is_read}>"
