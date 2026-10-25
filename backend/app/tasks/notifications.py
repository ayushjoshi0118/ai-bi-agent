"""
Asynchronous notification and webhook delivery tasks.
"""

from app.tasks.celery_app import celery_app
import structlog

logger = structlog.get_logger(__name__)


@celery_app.task(name="app.tasks.notifications.deliver_notification")
def deliver_notification(notification_id_str: str):
    logger.info("delivering_notification", notification_id=notification_id_str)
    return {"delivered": True}
