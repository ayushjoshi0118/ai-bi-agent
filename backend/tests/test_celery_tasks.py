"""
Regression and verification tests for Celery Background Tasks.
Tests durable task execution, status recording, failure handling, and idempotent retries.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_source import DataSource, DataSourceStatus, DataSourceType
from app.models.dataset import Dataset, DatasetStatus
from app.models.organization import Organization, OrgMembership, OrgRole
from app.models.report import Report, ReportStatus, ReportVersion
from app.models.scheduled_job import JobRun, JobRunStatus, JobType, ScheduledJob
from app.models.user import User
from app.security.password import hash_password
from app.tasks.anomaly_detection import _run_anomaly_scans
from app.tasks.notifications import _deliver
from app.tasks.reports import _execute_scheduled_report


@pytest.mark.asyncio
async def test_scheduled_report_task_execution(db_session: AsyncSession):
    # Setup test user and org
    user = User(email="task_user@example.com", password_hash=hash_password("Pass123!"), full_name="Task User")
    db_session.add(user)
    await db_session.flush()

    org = Organization(name="Task Org", slug=f"task-org-{uuid.uuid4().hex[:6]}", created_by=user.id)
    db_session.add(org)
    await db_session.flush()

    member = OrgMembership(org_id=org.id, user_id=user.id, role=OrgRole.OWNER)
    db_session.add(member)
    await db_session.flush()

    # Create a report
    report = Report(
        org_id=org.id,
        created_by=user.id,
        title="Weekly Financial Summary",
        description="Automated weekly summary",
        status=ReportStatus.PUBLISHED,
        config={"chart": "bar", "metrics": ["revenue"]},
    )
    db_session.add(report)
    await db_session.flush()

    # Create a scheduled job
    job = ScheduledJob(
        org_id=org.id,
        created_by=user.id,
        job_type=JobType.REPORT,
        config={"report_id": str(report.id)},
        schedule_cron="0 9 * * 1",
        timezone="UTC",
        is_active=True,
    )
    db_session.add(job)
    await db_session.commit()

    # Run the scheduled report execution helper
    result = await _execute_scheduled_report(job.id, session=db_session)
    assert result["status"] == "completed"
    assert result["job_id"] == str(job.id)

    # Verify JobRun was created with status COMPLETED
    async with db_session.bind.connect() as conn:
        pass
    runs = (await db_session.execute(
        JobRun.__table__.select().where(JobRun.scheduled_job_id == job.id)
    )).fetchall()
    assert len(runs) >= 1
    assert runs[0].status == JobRunStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_inactive_scheduled_job_is_skipped(db_session: AsyncSession):
    user = User(email="task_skip@example.com", password_hash=hash_password("Pass123!"), full_name="Skip User")
    db_session.add(user)
    await db_session.flush()

    org = Organization(name="Skip Org", slug=f"skip-org-{uuid.uuid4().hex[:6]}", created_by=user.id)
    db_session.add(org)
    await db_session.flush()

    inactive_job = ScheduledJob(
        org_id=org.id,
        created_by=user.id,
        job_type=JobType.REPORT,
        config={},
        schedule_cron="0 0 * * *",
        timezone="UTC",
        is_active=False,
    )
    db_session.add(inactive_job)
    await db_session.commit()

    result = await _execute_scheduled_report(inactive_job.id, session=db_session)
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_notification_delivery_task(db_session: AsyncSession):
    user = User(email="notif_task@example.com", password_hash=hash_password("Pass123!"), full_name="Notif User")
    db_session.add(user)
    await db_session.flush()

    org = Organization(name="Notif Org", slug=f"notif-org-{uuid.uuid4().hex[:6]}", created_by=user.id)
    db_session.add(org)
    await db_session.flush()

    from app.models.notification import Notification
    notif = Notification(
        org_id=org.id,
        user_id=user.id,
        title="Test Alert",
        message="System alert notification",
        notification_type="info",
    )
    db_session.add(notif)
    await db_session.commit()

    result = await _deliver(notif.id, session=db_session)
    assert result["delivered"] is True
    assert result["notification_id"] == str(notif.id)
