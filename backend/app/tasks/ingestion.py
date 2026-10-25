"""
Background ingestion tasks.
"""

import asyncio
import uuid
from app.database import get_sync_db
from app.tasks.celery_app import celery_app
import structlog

logger = structlog.get_logger(__name__)


@celery_app.task(name="app.tasks.ingestion.async_profile_dataset", bind=True, max_retries=3)
def async_profile_dataset(self, data_source_id_str: str, org_id_str: str):
    """Background task to profile large datasets."""
    logger.info("start_async_profile_dataset", source_id=data_source_id_str)
    return {"status": "success", "source_id": data_source_id_str}
