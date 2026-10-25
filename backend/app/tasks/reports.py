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
from app.security.tenant_security import TenantSecurityManager
from app.tasks.celery_app import celery_app
from app.workflows.idempotency import IdempotencyManager
from app.workflows.job_manager import AutonomousJobManager, FailureClassification

logger = structlog.get_logger(__name__)


async def _execute_scheduled_report(
    job_id: uuid.UUID,
    session: Optional[AsyncSession] = None,
    schedule_window: Optional[str] = None,
) -> dict:
    if session is not None:
        return await _do_execute_scheduled_report(job_id, session, schedule_window)
    async with AsyncSessionLocal() as new_session:
        return await _do_execute_scheduled_report(job_id, new_session, schedule_window)


async def _do_execute_scheduled_report(
    job_id: uuid.UUID,
    session: AsyncSession,
    schedule_window: Optional[str] = None,
) -> dict:
    job = await session.get(ScheduledJob, job_id)
    if not job or not job.is_active:
        logger.warning("scheduled_job_not_found_or_inactive", job_id=str(job_id))
        return {"status": "skipped", "job_id": str(job_id)}

    report_id_str = (job.config or {}).get("report_id")
    target_report_id = uuid.UUID(report_id_str) if report_id_str else None

    # 1. Revalidate Tenant Security & Authorization at Worker Runtime
    auth_check = await TenantSecurityManager.revalidate_worker_context(
        db=session,
        org_id=job.org_id,
        user_id=job.created_by,
        resource_type="report" if target_report_id else "scheduled_job",
        resource_id=target_report_id or job.id,
    )
    if not auth_check.authorized:
        logger.error(
            "scheduled_job_aborted_security_revocation",
            job_id=str(job_id),
            reason=auth_check.reason,
        )
        return {
            "status": "aborted_security_revoked",
            "job_id": str(job_id),
            "reason": auth_check.reason,
        }

    # 2. Idempotency Check: Prevent duplicate runs within same window
    window_key = schedule_window or datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
    idem_key = IdempotencyManager.generate_key(str(job_id), window_key, report_id_str)
    is_dupe, existing_result = await IdempotencyManager.check_and_claim_execution(
        session, job.id, idem_key
    )
    if is_dupe and existing_result:
        return {
            "status": "skipped_duplicate_idempotent",
            "job_id": str(job_id),
            "existing_result": existing_result,
        }

    # 3. Overlap Prevention & Atomic Run Claim
    run_record, plan = await AutonomousJobManager.check_overlap_and_start(session, job)
    if not plan.should_execute or not run_record:
        return {"status": "skipped_overlap", "reason": plan.skip_reason}

    try:
        report = None
        if target_report_id:
            stmt = select(Report).options(selectinload(Report.versions)).where(
                Report.id == target_report_id,
                Report.org_id == job.org_id,
            )
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

        # Update next run time respecting DST
        job.last_run_at = datetime.now(timezone.utc)
        job.next_run_at = AutonomousJobManager.calculate_next_run(job.schedule_cron, job.timezone)

        run_record.status = JobRunStatus.COMPLETED
        run_record.completed_at = datetime.now(timezone.utc)
        run_record.result = {
            "report_id": report_id_str,
            "version_generated": version_num if report else None,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "idempotency_key": idem_key,
            "schedule_window": window_key,
        }
        await session.commit()
        return {"status": "completed", "job_id": str(job_id), "run_id": str(run_record.id)}

    except Exception as e:
        await session.rollback()
        failure_type = AutonomousJobManager.classify_failure(e)
        run_record.status = JobRunStatus.FAILED
        run_record.completed_at = datetime.now(timezone.utc)
        run_record.error_message = str(e)
        run_record.result = {
            "failure_classification": failure_type.value,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
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
