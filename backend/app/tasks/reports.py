"""
Background report generation tasks.
Executes scheduled report runs, creates new report snapshots, and records job execution status.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import uuid
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.report import Report, ReportVersion
from app.models.scheduled_job import JobRun, JobRunStatus, ScheduledJob
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


async def _execute_scheduled_report(job_id: uuid.UUID, session: Optional[AsyncSession] = None) -> dict:
    if session is not None:
        return await _do_execute_scheduled_report(job_id, session)
    async with AsyncSessionLocal() as new_session:
        return await _do_execute_scheduled_report(job_id, new_session)


async def _do_execute_scheduled_report(job_id: uuid.UUID, session: AsyncSession) -> dict:
    job = await session.get(ScheduledJob, job_id)
    if not job or not job.is_active:
        logger.warning("scheduled_job_not_found_or_inactive", job_id=str(job_id))
        return {"status": "skipped", "job_id": str(job_id)}

    run_record = JobRun(
        scheduled_job_id=job.id,
        status=JobRunStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
        result={},
    )
    session.add(run_record)
    await session.commit()
    await session.refresh(run_record)

    try:
        report_id_str = (job.config or {}).get("report_id")
        report = None
        if report_id_str:
            report_id = uuid.UUID(report_id_str)
            stmt = select(Report).options(selectinload(Report.versions)).where(Report.id == report_id)
            res = await session.execute(stmt)
            report = res.scalar_one_or_none()

        version_num = (len(report.versions) + 1) if (report and report.versions) else 1
        if report:
            snapshot = {
                "scheduled_run_at": datetime.now(timezone.utc).isoformat(),
                "job_id": str(job.id),
                "config": report.config or {},
            }
            new_version = ReportVersion(
                report_id=report.id,
                version_number=version_num,
                content=snapshot,
                change_summary=f"Automated scheduled report execution v{version_num}",
                created_by=job.created_by,
            )
            session.add(new_version)

        run_record.status = JobRunStatus.COMPLETED
        run_record.completed_at = datetime.now(timezone.utc)
        run_record.result = {
            "report_id": report_id_str,
            "version_generated": version_num if report else None,
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }
        await session.commit()
        return {"status": "completed", "job_id": str(job_id), "run_id": str(run_record.id)}

    except Exception as e:
        await session.rollback()
        run_record.status = JobRunStatus.FAILED
        run_record.completed_at = datetime.now(timezone.utc)
        run_record.error_message = str(e)
        session.add(run_record)
        await session.commit()
        raise e


@celery_app.task(name="app.tasks.reports.generate_scheduled_report", bind=True, max_retries=3, default_retry_delay=15)
def generate_scheduled_report(self, job_id_str: str):
    """
    Executes a scheduled report job, captures a new data snapshot,
    creates a ReportVersion, and logs the execution.
    """
    logger.info("executing_scheduled_report_task", job_id=job_id_str)
    try:
        job_id = uuid.UUID(job_id_str)
        return asyncio.run(_execute_scheduled_report(job_id))
    except Exception as exc:
        logger.error("generate_scheduled_report_failed", job_id=job_id_str, error=str(exc))
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"status": "failed", "job_id": job_id_str, "error": str(exc)}
