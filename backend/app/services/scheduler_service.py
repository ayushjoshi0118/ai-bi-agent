"""
Scheduled Jobs and Automated Workflows service.
Manages cron-scheduled reports and recurring anomaly scans, tracks job runs, and enforces per-org limits.
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.scheduled_job import JobRun, JobRunStatus, JobType, ScheduledJob
from app.schemas.scheduled_job import ScheduledJobCreate, ScheduledJobUpdate
from app.security.tenant_security import TenantSecurityManager
from app.services.audit_service import AuditService

MAX_JOBS_PER_ORG = 20


class SchedulerService:
    @staticmethod
    async def create_job(
        db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, req: ScheduledJobCreate
    ) -> ScheduledJob:
        # Check per-org quota
        count_stmt = select(ScheduledJob).where(ScheduledJob.org_id == org_id, ScheduledJob.is_active == True)
        active_count = len((await db.execute(count_stmt)).scalars().all())
        if active_count >= MAX_JOBS_PER_ORG:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Organization active scheduled job limit of {MAX_JOBS_PER_ORG} reached",
            )

        job = ScheduledJob(
            org_id=org_id,
            created_by=user_id,
            job_type=req.job_type,
            name=req.name.strip(),
            schedule_cron=req.schedule_cron.strip(),
            timezone=req.timezone or "UTC",
            config=req.config or {},
            is_active=True,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        await AuditService.log_event(
            db,
            org_id=org_id,
            user_id=user_id,
            action="job.create",
            resource_type="scheduled_job",
            resource_id=job.id,
            details={"name": req.name, "cron": req.schedule_cron, "type": req.job_type.value},
        )
        return job

    @staticmethod
    async def list_jobs(db: AsyncSession, org_id: uuid.UUID) -> List[ScheduledJob]:
        stmt = (
            select(ScheduledJob)
            .options(selectinload(ScheduledJob.runs))
            .where(ScheduledJob.org_id == org_id)
            .order_by(ScheduledJob.created_at.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_job(db: AsyncSession, org_id: uuid.UUID, job_id: uuid.UUID) -> ScheduledJob:
        stmt = (
            select(ScheduledJob)
            .options(selectinload(ScheduledJob.runs))
            .where(ScheduledJob.id == job_id, ScheduledJob.org_id == org_id)
        )
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            await TenantSecurityManager.verify_object_ownership(
                db=db,
                org_id=org_id,
                user_id=uuid.uuid4(),
                model_class=ScheduledJob,
                object_id=job_id,
                resource_label="scheduled job",
            )
        return job

    @staticmethod
    async def update_job(
        db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, job_id: uuid.UUID, req: ScheduledJobUpdate
    ) -> ScheduledJob:
        job = await SchedulerService.get_job(db, org_id, job_id)
        if req.name is not None:
            job.name = req.name.strip()
        if req.schedule_cron is not None:
            job.schedule_cron = req.schedule_cron.strip()
        if req.timezone is not None:
            job.timezone = req.timezone
        if req.config is not None:
            job.config = req.config
        if req.is_active is not None:
            job.is_active = req.is_active

        await db.commit()
        await db.refresh(job)

        await AuditService.log_event(
            db,
            org_id=org_id,
            user_id=user_id,
            action="job.update",
            resource_type="scheduled_job",
            resource_id=job.id,
        )
        return job

    @staticmethod
    async def record_job_run(
        db: AsyncSession,
        job_id: uuid.UUID,
        status_val: JobRunStatus,
        result: Optional[dict] = None,
        error_message: Optional[str] = None,
        duration_seconds: Optional[float] = None,
    ) -> JobRun:
        run = JobRun(
            scheduled_job_id=job_id,
            status=status_val,
            result=result or {},
            error_message=error_message,
            duration_seconds=duration_seconds,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db.add(run)

        # Update last run on job
        stmt = select(ScheduledJob).where(ScheduledJob.id == job_id)
        job = (await db.execute(stmt)).scalar_one_or_none()
        if job:
            job.last_run_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(run)
        return run
