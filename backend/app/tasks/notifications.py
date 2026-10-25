"""
Asynchronous notification and webhook delivery tasks.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import uuid
import structlog
from celery.exceptions import MaxRetriesExceededError

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.notification import Notification
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


async def _deliver(notif_id: uuid.UUID, session: Optional[AsyncSession] = None) -> dict:
    if session is not None:
        return await _do_deliver(notif_id, session)
    async with AsyncSessionLocal() as new_session:
        return await _do_deliver(notif_id, new_session)


async def _do_deliver(notif_id: uuid.UUID, session: AsyncSession) -> dict:
    notif = await session.get(Notification, notif_id)
    if not notif:
        logger.warning("notification_not_found_for_delivery", notification_id=str(notif_id))
        return {"delivered": False, "reason": "not_found"}

    logger.info(
        "notification_dispatched",
        notification_id=str(notif.id),
        user_id=str(notif.user_id),
        title=notif.title,
    )
    return {
        "delivered": True,
        "notification_id": str(notif.id),
        "user_id": str(notif.user_id),
        "dispatched_at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task(name="app.tasks.notifications.deliver_notification", bind=True, max_retries=3, default_retry_delay=5)
def deliver_notification(self, notification_id_str: str):
    logger.info("delivering_notification", notification_id=notification_id_str)
    try:
        notif_id = uuid.UUID(notification_id_str)
        return asyncio.run(_deliver(notif_id))
    except Exception as exc:
        logger.error("deliver_notification_failed", notification_id=notification_id_str, error=str(exc))
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"delivered": False, "error": str(exc)}
