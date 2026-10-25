"""
Scheduled jobs and workflow automation API endpoints.
"""

import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_org, get_current_user, get_db, require_role
from app.models.organization import OrgRole, Organization
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.scheduled_job import (
    JobRunResponse,
    ScheduledJobCreate,
    ScheduledJobResponse,
    ScheduledJobUpdate,
)
from app.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/scheduled-jobs", tags=["Scheduled Jobs"])


@router.get("", response_model=List[ScheduledJobResponse])
async def list_scheduled_jobs(
    org_and_role: tuple[Organization, OrgRole] = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    jobs = await SchedulerService.list_jobs(db, org.id)
    out = []
    for j in jobs:
        latest = j.runs[-1] if j.runs else None
        out.append(
            ScheduledJobResponse(
                id=j.id,
                org_id=j.org_id,
                created_by=j.created_by,
                name=j.name,
                job_type=j.job_type,
                config=j.config,
                schedule_cron=j.schedule_cron,
                timezone=j.timezone,
                is_active=j.is_active,
                last_run_at=j.last_run_at,
                next_run_at=j.next_run_at,
                created_at=j.created_at,
                updated_at=j.updated_at,
                latest_run=JobRunResponse.model_validate(latest) if latest else None,
            )
        )
    return out


@router.post("", response_model=ScheduledJobResponse, status_code=status.HTTP_201_CREATED)
async def create_scheduled_job(
    req: ScheduledJobCreate,
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ANALYST)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    job = await SchedulerService.create_job(db, org.id, current_user.id, req)
    return ScheduledJobResponse(
        id=job.id,
        org_id=job.org_id,
        created_by=job.created_by,
        name=job.name,
        job_type=job.job_type,
        config=job.config,
        schedule_cron=job.schedule_cron,
        timezone=job.timezone,
        is_active=job.is_active,
        last_run_at=job.last_run_at,
        next_run_at=job.next_run_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
        latest_run=None,
    )


@router.put("/{job_id}", response_model=ScheduledJobResponse)
async def update_scheduled_job(
    job_id: uuid.UUID,
    req: ScheduledJobUpdate,
    org_and_role: tuple[Organization, OrgRole] = Depends(require_role(OrgRole.ANALYST)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_role
    job = await SchedulerService.update_job(db, org.id, current_user.id, job_id, req)
    latest = job.runs[-1] if job.runs else None
    return ScheduledJobResponse(
        id=job.id,
        org_id=job.org_id,
        created_by=job.created_by,
        name=job.name,
        job_type=job.job_type,
        config=job.config,
        schedule_cron=job.schedule_cron,
        timezone=job.timezone,
        is_active=job.is_active,
        last_run_at=job.last_run_at,
        next_run_at=job.next_run_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
        latest_run=JobRunResponse.model_validate(latest) if latest else None,
    )
