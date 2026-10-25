"""
AuditEvent model – immutable audit trail for compliance.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class AuditEvent(BaseModel):
    __tablename__ = "audit_events"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
        comment="e.g. user.login, query.execute, report.export",
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="e.g. dataset, query, report",
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    details: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Additional context – IP, user agent, diff, etc.",
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="audit_events",
    )

    def __repr__(self) -> str:
        return f"<AuditEvent {self.action} by user={self.user_id}>"
