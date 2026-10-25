"""
Audit logging service for security, compliance, and query tracking.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.audit import AuditEvent

logger = structlog.get_logger(__name__)


class AuditService:
    @staticmethod
    async def log_event(
        db: AsyncSession,
        org_id: uuid.UUID,
        action: str,
        user_id: Optional[uuid.UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[uuid.UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """
        Record an immutable audit event in the database and structured logger.
        """
        event = AuditEvent(
            org_id=org_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)

        logger.info(
            "audit_event_recorded",
            org_id=str(org_id),
            user_id=str(user_id) if user_id else None,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
        )
        return event
