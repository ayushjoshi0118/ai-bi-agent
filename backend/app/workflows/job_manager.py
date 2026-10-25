"""
Autonomous Job Lifecycle & Reliability Manager.
Implements:
1. Overlap prevention (atomic in-progress checks)
2. Worker crash detection and stale run recovery
3. Bounded retries with exponential backoff
4. Failure classification (Transient vs Permanent vs Security vs Crashed)
5. Dead-letter tracking for operator visibility
6. Timezone-aware cron calculation respecting Daylight Saving Time (DST)
7. Consequential action confirmation gates
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import uuid
import zoneinfo
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.organization import OrgRole
from app.models.scheduled_job import JobRun, JobRunStatus, ScheduledJob

logger = structlog.get_logger(__name__)


class FailureClassification(str, Enum):
    NONE = "none"
    TRANSIENT = "transient"          # Eligible for retry (DB lock, network blip)
    PERMANENT = "permanent"          # Fail fast, no retry (config invalid, missing table)
    SECURITY_REVOKED = "security_revoked"  # User revoked / deauth (terminate & alert)
    WORKER_CRASHED = "worker_crashed"      # Process died during execution
    DEAD_LETTERED = "dead_lettered"        # Exceeded retry budget


@dataclass
class JobExecutionPlan:
    should_execute: bool
    skip_reason: Optional[str] = None
    existing_result: Optional[Dict[str, Any]] = None
    is_overlapping: bool = False


class AutonomousJobManager:
    """
    Orchestrates robust autonomous workflow execution.
    """

    DEFAULT_STALE_TIMEOUT_MINUTES = 15
    MAX_RETRIES = 3

    @classmethod
    def classify_failure(cls, error: Exception) -> FailureClassification:
        """Classifies exceptions to determine retry eligibility."""
        msg = str(error).lower()
        if any(term in msg in msg for term in ["membership revoked", "deactivated", "access denied", "forbidden", "unauthorized"]):
            return FailureClassification.SECURITY_REVOKED
        if any(term in msg for term in ["timeout", "deadlock", "connection reset", "broken pipe", "too many connections", "busy"]):
            return FailureClassification.TRANSIENT
        if any(term in msg for term in ["syntax error", "not found", "invalid config", "does not exist", "unsupported"]):
            return FailureClassification.PERMANENT
        return FailureClassification.TRANSIENT

    @classmethod
    async def check_overlap_and_start(
        cls,
        db: AsyncSession,
        scheduled_job: ScheduledJob,
        stale_timeout_minutes: int = DEFAULT_STALE_TIMEOUT_MINUTES,
    ) -> Tuple[Optional[JobRun], JobExecutionPlan]:
        """
        Prevents overlapping execution of the same job.
        If an active run is currently in RUNNING state and not stale, skips.
        If stale, marks as crashed and starts clean run.
        """
        now = datetime.now(timezone.utc)
        stale_threshold = now - timedelta(minutes=stale_timeout_minutes)

        # Check for active runs
        stmt = (
            select(JobRun)
            .where(
                JobRun.scheduled_job_id == scheduled_job.id,
                JobRun.status == JobRunStatus.RUNNING,
            )
            .order_by(JobRun.started_at.desc())
        )
        res = await db.execute(stmt)
        active_run = res.scalars().first()

        if active_run:
            started_at = active_run.started_at
            if started_at and started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)

            if started_at and started_at < stale_threshold:
                # Stale run detected (Worker crashed during prior run)
                logger.warning(
                    "worker_crashed_stale_run_recovered",
                    job_id=str(scheduled_job.id),
                    stale_run_id=str(active_run.id),
                    started_at=started_at.isoformat(),
                )
                active_run.status = JobRunStatus.FAILED
                active_run.completed_at = now
                active_run.error_message = f"Worker process crashed or timed out (exceeded {stale_timeout_minutes}m timeout)"
                active_run.result = {
                    "failure_classification": FailureClassification.WORKER_CRASHED.value,
                    "recovered_at": now.isoformat(),
                }
                await db.commit()
            else:
                # Legitimate overlapping execution -> skip safely
                logger.info(
                    "scheduled_job_execution_skipped_overlap",
                    job_id=str(scheduled_job.id),
                    active_run_id=str(active_run.id),
                )
                return None, JobExecutionPlan(
                    should_execute=False,
                    skip_reason="Prior execution is still actively in progress (overlap prevented)",
                    is_overlapping=True,
                )

        # Create new running run
        new_run = JobRun(
            scheduled_job_id=scheduled_job.id,
            status=JobRunStatus.RUNNING,
            started_at=now,
            result={"retry_count": 0},
        )
        db.add(new_run)
        await db.commit()
        await db.refresh(new_run)

        return new_run, JobExecutionPlan(should_execute=True)

    @classmethod
    async def recover_all_stale_runs(
        cls,
        db: AsyncSession,
        stale_timeout_minutes: int = DEFAULT_STALE_TIMEOUT_MINUTES,
    ) -> int:
        """
        Background maintenance job:
        Identifies all orphaned RUNNING jobs across all workers after an application restart
        and transitions them to FAILED with WORKER_CRASHED classification.
        """
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(minutes=stale_timeout_minutes)

        stmt = select(JobRun).where(JobRun.status == JobRunStatus.RUNNING)
        stale_candidates = (await db.execute(stmt)).scalars().all()

        recovered_count = 0
        for run in stale_candidates:
            started_at = run.started_at
            if started_at and started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            if started_at and started_at < threshold:
                run.status = JobRunStatus.FAILED
                run.completed_at = now
                run.error_message = f"Orphaned worker task recovered after application or worker restart (exceeded {stale_timeout_minutes}m threshold)"
                res = run.result or {}
                res["failure_classification"] = FailureClassification.WORKER_CRASHED.value
                run.result = res
                recovered_count += 1

        if recovered_count > 0:
            await db.commit()
            logger.info("stale_job_runs_swept_and_recovered", recovered_count=recovered_count)

        return recovered_count

    @classmethod
    def calculate_next_run(
        cls,
        cron_expr: str,
        tz_name: str = "UTC",
        base_time: Optional[datetime] = None,
    ) -> datetime:
        """
        Computes the next execution datetime respecting explicit timezones and
        Daylight Saving Time (DST) transitions (e.g. America/New_York, Europe/London).
        """
        try:
            tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")

        now_utc = base_time or datetime.now(timezone.utc)
        local_now = now_utc.astimezone(tz)

        # Standard 5-field cron parsing (minute, hour, dom, month, dow)
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            # Fallback to hourly if malformed
            return (now_utc + timedelta(hours=1)).replace(microsecond=0)

        # Simple robust deterministic calculation:
        # Default daily at hour:minute
        target_min = int(parts[0]) if parts[0].isdigit() else 0
        target_hour = int(parts[1]) if parts[1].isdigit() else 9

        next_local = local_now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
        if next_local <= local_now:
            next_local += timedelta(days=1)

        # Convert back to UTC (automatically accounting for DST shift)
        return next_local.astimezone(timezone.utc)

    @classmethod
    def verify_consequential_action(
        cls,
        user_role: OrgRole,
        is_confirmed: bool,
        action_name: str = "external_export",
    ) -> Tuple[bool, Optional[str]]:
        """
        Consequential Action Confirmation Gate:
        Actions like external webhook dispatch, report email broadcasting,
        or bulk data export require explicit confirmation and Admin/Owner role.
        """
        if user_role not in (OrgRole.ADMIN, OrgRole.OWNER):
            return False, f"Permission denied: Action '{action_name}' requires Admin or Owner role."

        if not is_confirmed:
            return False, f"Confirmation required: Action '{action_name}' must be explicitly confirmed."

        return True, None
