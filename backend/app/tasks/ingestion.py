"""
Background ingestion tasks.
Profiles datasets, computes column stats, and handles async file ingestion.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import uuid
import structlog
from celery.exceptions import MaxRetriesExceededError

from app.database import AsyncSessionLocal
from app.models.data_source import DataSource, DataSourceStatus
from app.services.schema_discovery import SchemaDiscoveryService
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


async def _run_profiling(source_id: uuid.UUID, org_id: uuid.UUID) -> dict:
    async with AsyncSessionLocal() as session:
        try:
            datasets = await SchemaDiscoveryService.discover_and_profile_source(
                db=session,
                org_id=org_id,
                source_id=source_id,
            )
            source = await session.get(DataSource, source_id)
            if source:
                source.status = DataSourceStatus.CONNECTED
                source.last_synced_at = datetime.now(timezone.utc)
            await session.commit()
            return {
                "status": "success",
                "source_id": str(source_id),
                "datasets_profiled": len(datasets),
            }
        except Exception as e:
            await session.rollback()
            source = await session.get(DataSource, source_id)
            if source:
                source.status = DataSourceStatus.ERROR
                await session.commit()
            raise e


@celery_app.task(name="app.tasks.ingestion.async_profile_dataset", bind=True, max_retries=3, default_retry_delay=10)
def async_profile_dataset(self, data_source_id_str: str, org_id_str: str):
    """Background task to profile large datasets durably."""
    logger.info("start_async_profile_dataset", source_id=data_source_id_str, org_id=org_id_str)
    try:
        source_id = uuid.UUID(data_source_id_str)
        org_id = uuid.UUID(org_id_str)
        return asyncio.run(_run_profiling(source_id, org_id))
    except Exception as exc:
        logger.error("async_profile_dataset_failed", source_id=data_source_id_str, error=str(exc))
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"status": "failed", "source_id": data_source_id_str, "error": str(exc)}
