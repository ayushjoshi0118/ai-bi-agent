"""
Background anomaly detection worker tasks.
Scans datasets for statistical deviations, creates notification alerts, and updates job logs.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog

from app.database import AsyncSessionLocal
from app.models.dataset import Dataset, DatasetStatus
from app.models.notification import Notification
from app.models.scheduled_job import JobRun, JobRunStatus, JobType, ScheduledJob
from app.services.anomaly_service import AnomalyService
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


async def _run_anomaly_scans() -> dict:
    scanned_count = 0
    anomalies_detected = 0

    async with AsyncSessionLocal() as session:
        # 1. Fetch active scheduled anomaly jobs
        stmt = (
            select(ScheduledJob)
            .where(
                ScheduledJob.job_type == JobType.ANOMALY_SCAN,
                ScheduledJob.is_active == True,
            )
        )
        res = await session.execute(stmt)
        jobs = list(res.scalars().all())

        for job in jobs:
            scanned_count += 1
            run_record = JobRun(
                scheduled_job_id=job.id,
                status=JobRunStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
            )
            session.add(run_record)
            await session.commit()
            await session.refresh(run_record)

            try:
                cfg = job.config or {}
                dataset_id_str = cfg.get("dataset_id")
                metric_col = cfg.get("metric_column")

                if dataset_id_str and metric_col:
                    dataset_id = uuid.UUID(dataset_id_str)
                    anoms = await AnomalyService.run_detection(
                        db=session,
                        org_id=job.org_id,
                        dataset_id=dataset_id,
                        metric_column=metric_col,
                        time_column=cfg.get("time_column"),
                        method=cfg.get("method", "z_score"),
                        sensitivity=cfg.get("sensitivity", "medium"),
                    )
                    anomalies_detected += len(anoms)

                    # Create alert notification if anomalies detected
                    if anoms and job.created_by:
                        notif = Notification(
                            org_id=job.org_id,
                            user_id=job.created_by,
                            title=f"Anomaly Alert: {len(anoms)} anomalies found in {metric_col}",
                            message=f"Statistical deviations detected during automated background scan on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.",
                            notification_type="warning",
                            resource_type="dataset",
                            resource_id=dataset_id,
                        )
                        session.add(notif)

                run_record.status = JobRunStatus.COMPLETED
                run_record.completed_at = datetime.now(timezone.utc)
                run_record.result = {
                    "anomalies_found": len(anoms) if 'anoms' in locals() else 0,
                    "scanned_at": datetime.now(timezone.utc).isoformat(),
                }
                await session.commit()

            except Exception as e:
                await session.rollback()
                run_record.status = JobRunStatus.FAILED
                run_record.completed_at = datetime.now(timezone.utc)
                run_record.error_message = str(e)
                session.add(run_record)
                await session.commit()
                logger.error("anomaly_scan_job_failed", job_id=str(job.id), error=str(e))

    return {
        "status": "completed",
        "jobs_executed": scanned_count,
        "total_anomalies_detected": anomalies_detected,
    }


@celery_app.task(name="app.tasks.anomaly_detection.run_periodic_anomaly_scans")
def run_periodic_anomaly_scans():
    """
    Periodic job invoked by Celery Beat to scan datasets across organizations for anomalies.
    """
    logger.info("running_periodic_anomaly_scans")
    return asyncio.run(_run_anomaly_scans())
