"""
Notification service for user alerts and updates.
"""

from __future__ import annotations

import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


class NotificationService:
    @staticmethod
    async def create_notification(
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        title: str,
        message: str,
        notification_type: str = "info",
        resource_type: Optional[str] = None,
        resource_id: Optional[uuid.UUID] = None,
    ) -> Notification:
        notif = Notification(
            org_id=org_id,
            user_id=user_id,
            title=title.strip(),
            message=message.strip(),
            notification_type=notification_type,
            resource_type=resource_type,
            resource_id=resource_id,
            is_read=False,
        )
        db.add(notif)
        await db.commit()
        await db.refresh(notif)
        return notif

    @staticmethod
    async def list_notifications(
        db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, unread_only: bool = False
    ) -> List[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.org_id == org_id)
            .where((Notification.user_id == user_id) | (Notification.user_id.is_(None)))
        )
        if unread_only:
            stmt = stmt.where(Notification.is_read == False)
        stmt = stmt.order_by(Notification.created_at.desc()).limit(50)

        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def mark_as_read(
        db: AsyncSession, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        stmt = select(Notification).where(
            Notification.id == notification_id,
            (Notification.user_id == user_id) | (Notification.user_id.is_(None)),
        )
        res = await db.execute(stmt)
        notif = res.scalar_one_or_none()
        if notif:
            notif.is_read = True
            await db.commit()
