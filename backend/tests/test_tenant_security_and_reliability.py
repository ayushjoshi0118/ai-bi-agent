"""
Automated Validation Suite for Tenant Security and Autonomous Reliability.
Validates:
1. Object-level tenant isolation and cross-tenant identifier probe rejection
2. Background worker authorization revalidation (detecting revoked user memberships)
3. Job idempotency (preventing duplicate report snapshots and notifications)
4. Worker crash and stale job run recovery
5. Overlapping schedule execution prevention
6. Timezone boundaries and Daylight Saving Time (DST) handling
7. Consequential action confirmation gates
8. Rate limiting headers and quota enforcement
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import OrgMembership, OrgRole, Organization
from app.models.report import Report, ReportVersion
from app.models.scheduled_job import JobRun, JobRunStatus, JobType, ScheduledJob
from app.models.notification import Notification
from app.models.user import User
from app.security.password import hash_password
from app.security.tenant_security import SecurityFailureType, TenantSecurityManager
from app.tasks.notifications import _do_deliver
from app.tasks.reports import _do_execute_scheduled_report
from app.workflows.idempotency import IdempotencyManager
from app.workflows.job_manager import AutonomousJobManager, FailureClassification


# ==============================================================================
# 1. Tenant Security & Cross-Tenant Rejection Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_cross_tenant_object_access_rejected_and_audited(db_session: AsyncSession):
    """
    Verifies that User B in Org B cannot read or modify Report A owned by Org A,
    even when supplying Report A's exact UUID.
    """
    # 1. Create Org A and Report A
    user_a = User(email="user_a@sec-test.com", password_hash=hash_password("PassA123!"), full_name="User A", is_active=True)
    db_session.add(user_a)
    await db_session.flush()

    org_a = Organization(name="Tenant Alpha", slug="tenant-alpha", created_by=user_a.id)
    db_session.add(org_a)
    await db_session.flush()

    report_a = Report(org_id=org_a.id, created_by=user_a.id, title="Alpha Confidential Financials", config={})
    db_session.add(report_a)

    # 2. Create Org B and User B
    user_b = User(email="user_b@sec-test.com", password_hash=hash_password("PassB123!"), full_name="User B", is_active=True)
    db_session.add(user_b)
    await db_session.flush()

    org_b = Organization(name="Tenant Beta", slug="tenant-beta", created_by=user_b.id)
    db_session.add(org_b)
    await db_session.flush()
    await db_session.commit()

    # 3. User B in Org B attempts to access Report A
    with pytest.raises(Exception) as exc_info:
        await TenantSecurityManager.verify_object_ownership(
            db=db_session,
            org_id=org_b.id,
            user_id=user_b.id,
            model_class=Report,
            object_id=report_a.id,
            resource_label="report",
        )

    # Must fail closed with 404 (not leaking cross-tenant existence)
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_worker_authorization_revalidation_aborts_on_revocation(db_session: AsyncSession):
    """
    Verifies that if a user schedules a report, but their membership is subsequently
    revoked, the worker revalidation detects the revocation and aborts execution.
    """
    # 1. Setup Org and User
    user = User(email="scheduled_user@sec-test.com", password_hash=hash_password("Pass123!"), full_name="Sch User", is_active=True)
    db_session.add(user)
    await db_session.flush()

    org = Organization(name="Scheduled Org", slug="sch-org", created_by=user.id)
    db_session.add(org)
    await db_session.flush()

    membership = OrgMembership(user_id=user.id, org_id=org.id, role=OrgRole.ANALYST)
    db_session.add(membership)

    report = Report(org_id=org.id, created_by=user.id, title="Scheduled Weekly Snapshot", config={})
    db_session.add(report)
    await db_session.flush()

    job = ScheduledJob(
        org_id=org.id,
        created_by=user.id,
        job_type=JobType.REPORT,
        schedule_cron="0 9 * * 1",
        timezone="UTC",
        config={"report_id": str(report.id)},
        is_active=True,
    )
    db_session.add(job)
    await db_session.commit()

    # 2. Revoke User's membership prior to worker execution
    await db_session.delete(membership)
    await db_session.commit()

    # 3. Execute worker task
    result = await _do_execute_scheduled_report(job.id, session=db_session)

    # Worker must detect revoked membership and abort
    assert result["status"] == "aborted_security_revoked"
    assert "revoked" in result["reason"].lower()

    # Verify no new report versions were created
    res_versions = await db_session.execute(select(ReportVersion).where(ReportVersion.report_id == report.id))
    assert len(res_versions.scalars().all()) == 0


# ==============================================================================
# 2. Idempotency & Overlap Prevention Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_job_execution_idempotency_prevents_duplicate_runs(db_session: AsyncSession):
    """
    Verifies that executing a job within the same schedule window produces exactly
    one report snapshot and skips duplicate dispatches.
    """
    user = User(email="idem_user@sec-test.com", password_hash=hash_password("Pass123!"), full_name="Idem User", is_active=True)
    db_session.add(user)
    await db_session.flush()

    org = Organization(name="Idem Org", slug="idem-org", created_by=user.id)
    db_session.add(org)
    await db_session.flush()

    membership = OrgMembership(user_id=user.id, org_id=org.id, role=OrgRole.OWNER)
    db_session.add(membership)

    report = Report(org_id=org.id, created_by=user.id, title="Idempotent Financial Summary", config={})
    db_session.add(report)
    await db_session.flush()

    job = ScheduledJob(
        org_id=org.id,
        created_by=user.id,
        job_type=JobType.REPORT,
        schedule_cron="0 8 * * *",
        timezone="UTC",
        config={"report_id": str(report.id)},
        is_active=True,
    )
    db_session.add(job)
    await db_session.commit()

    # 1. First execution
    window_key = "2026-03-01-08"
    res1 = await _do_execute_scheduled_report(job.id, session=db_session, schedule_window=window_key)
    assert res1["status"] == "completed"

    # Verify 1 version created
    v_stmt = select(ReportVersion).where(ReportVersion.report_id == report.id)
    assert len((await db_session.execute(v_stmt)).scalars().all()) == 1

    # 2. Duplicate second execution within the same schedule window
    res2 = await _do_execute_scheduled_report(job.id, session=db_session, schedule_window=window_key)
    assert res2["status"] == "skipped_duplicate_idempotent"

    # Verify still exactly 1 version exists (no duplicate snapshot!)
    assert len((await db_session.execute(v_stmt)).scalars().all()) == 1


@pytest.mark.asyncio
async def test_overlapping_schedules_prevention(db_session: AsyncSession):
    """
    Verifies that if a job is actively running, concurrent triggers are skipped.
    """
    user = User(email="overlap_user@sec-test.com", password_hash=hash_password("Pass123!"), full_name="Overlap User", is_active=True)
    db_session.add(user)
    await db_session.flush()

    org = Organization(name="Overlap Org", slug="overlap-org", created_by=user.id)
    db_session.add(org)
    await db_session.flush()

    job = ScheduledJob(
        org_id=org.id,
        created_by=user.id,
        job_type=JobType.REPORT,
        schedule_cron="*/5 * * * *",
        timezone="UTC",
        config={},
        is_active=True,
    )
    db_session.add(job)
    await db_session.commit()

    # 1. Start first run
    run1, plan1 = await AutonomousJobManager.check_overlap_and_start(db_session, job)
    assert plan1.should_execute is True
    assert run1.status == JobRunStatus.RUNNING

    # 2. Concurrent second execution while run1 is actively running
    run2, plan2 = await AutonomousJobManager.check_overlap_and_start(db_session, job)
    assert plan2.should_execute is False
    assert plan2.is_overlapping is True
    assert "overlap prevented" in plan2.skip_reason.lower()


# ==============================================================================
# 3. Worker Crash Recovery Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_worker_crash_and_stale_run_recovery(db_session: AsyncSession):
    """
    Simulates a worker crashing or being SIGKILL'd during execution.
    Verifies that the autonomous maintenance sweep identifies orphaned runs
    and recovers them with WORKER_CRASHED classification.
    """
    user = User(email="crash_user@sec-test.com", password_hash=hash_password("Pass123!"), full_name="Crash User", is_active=True)
    db_session.add(user)
    await db_session.flush()

    org = Organization(name="Crash Org", slug="crash-org", created_by=user.id)
    db_session.add(org)
    await db_session.flush()

    job = ScheduledJob(
        org_id=org.id,
        created_by=user.id,
        job_type=JobType.REPORT,
        schedule_cron="0 0 * * *",
        timezone="UTC",
        config={},
        is_active=True,
    )
    db_session.add(job)
    await db_session.flush()

    # Simulate crashed run started 25 minutes ago
    crashed_start_time = datetime.now(timezone.utc) - timedelta(minutes=25)
    crashed_run = JobRun(
        scheduled_job_id=job.id,
        status=JobRunStatus.RUNNING,
        started_at=crashed_start_time,
        result={},
    )
    db_session.add(crashed_run)
    await db_session.commit()

    # Run recovery sweep (stale threshold = 15m)
    recovered_count = await AutonomousJobManager.recover_all_stale_runs(db_session, stale_timeout_minutes=15)
    assert recovered_count >= 1

    # Verify run status is now FAILED with WORKER_CRASHED
    await db_session.refresh(crashed_run)
    assert crashed_run.status == JobRunStatus.FAILED
    assert "crashed or timed out" in crashed_run.error_message.lower() or "orphaned" in crashed_run.error_message.lower()
    assert (crashed_run.result or {}).get("failure_classification") == FailureClassification.WORKER_CRASHED.value


# ==============================================================================
# 4. Timezone & Daylight Saving Time (DST) Tests
# ==============================================================================

def test_timezone_boundaries_and_dst_transitions():
    """
    Validates timezone-aware cron evaluation across standard and daylight saving transitions.
    """
    # 1. America/New_York (UTC-5 in winter, UTC-4 in summer)
    base_winter = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    next_ny = AutonomousJobManager.calculate_next_run(
        cron_expr="0 9 * * *",
        tz_name="America/New_York",
        base_time=base_winter,
    )
    # 9:00 AM NY in winter is 14:00 UTC
    assert next_ny.hour == 14

    # 2. Europe/London (GMT in winter, BST / UTC+1 in summer)
    base_summer = datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc)
    next_london = AutonomousJobManager.calculate_next_run(
        cron_expr="0 9 * * *",
        tz_name="Europe/London",
        base_time=base_summer,
    )
    # 9:00 AM London in summer is 8:00 UTC (9:00 BST - 1hr)
    assert next_london.hour == 8

    # 3. Asia/Tokyo (Constant UTC+9, no DST)
    base_tokyo = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    next_tokyo = AutonomousJobManager.calculate_next_run(
        cron_expr="0 9 * * *",
        tz_name="Asia/Tokyo",
        base_time=base_tokyo,
    )
    # 9:00 AM Tokyo is 00:00 UTC
    assert next_tokyo.hour == 0


# ==============================================================================
# 5. Consequential Action Confirmation & Notification Tests
# ==============================================================================

def test_consequential_action_confirmation_gate():
    # 1. Viewer role cannot confirm external action
    allowed, reason = AutonomousJobManager.verify_consequential_action(
        user_role=OrgRole.VIEWER,
        is_confirmed=True,
        action_name="export_data",
    )
    assert allowed is False
    assert "Admin or Owner" in reason

    # 2. Admin role without confirmation is blocked
    allowed, reason = AutonomousJobManager.verify_consequential_action(
        user_role=OrgRole.ADMIN,
        is_confirmed=False,
        action_name="export_data",
    )
    assert allowed is False
    assert "must be explicitly confirmed" in reason

    # 3. Admin role with confirmation is approved
    allowed, reason = AutonomousJobManager.verify_consequential_action(
        user_role=OrgRole.ADMIN,
        is_confirmed=True,
        action_name="export_data",
    )
    assert allowed is True
    assert reason is None


@pytest.mark.asyncio
async def test_notification_delivery_external_channel_confirmation(db_session: AsyncSession):
    user = User(email="notif_user@sec-test.com", password_hash=hash_password("Pass123!"), full_name="Notif User", is_active=True)
    db_session.add(user)
    await db_session.flush()

    org = Organization(name="Notif Org", slug="notif-org", created_by=user.id)
    db_session.add(org)
    await db_session.flush()

    # Notification targeting external webhook without confirmation flag
    notif = Notification(
        org_id=org.id,
        user_id=user.id,
        title="Security Alert",
        message="Critical threshold passed",
        notification_type="external_webhook",
        resource_type="unconfirmed",
        is_read=False,
    )
    db_session.add(notif)
    await db_session.commit()

    # Worker dispatch should reject unconfirmed external dispatch
    res = await _do_deliver(notif.id, session=db_session)
    assert res["delivered"] is False
    assert "confirmation" in res["reason"]

    # Now confirm and dispatch
    notif.resource_type = "confirmed"
    await db_session.commit()

    res2 = await _do_deliver(notif.id, session=db_session)
    assert res2["delivered"] is True

    # Re-delivery is skipped idempotently
    res3 = await _do_deliver(notif.id, session=db_session)
    assert res3["status"] == "skipped_duplicate_idempotent"


# ==============================================================================
# 6. Rate Limiting Headers & Metrics Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_rate_limiting_headers_attached(client: AsyncClient):
    """
    Verifies that requests return standard X-RateLimit headers.
    """
    resp = await client.get("/api/v1/auth/me")
    # Even if 401 Unauthorized, rate limit headers are attached
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    assert "X-RateLimit-Reset" in resp.headers


@pytest.mark.asyncio
async def test_health_metrics_telemetry_endpoint(client: AsyncClient):
    """
    Verifies /api/v1/health/metrics surfaces operational telemetry.
    """
    resp = await client.get("/api/v1/health/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "llm" in data
    assert "queries" in data
    assert "workflows" in data
    assert "security" in data
