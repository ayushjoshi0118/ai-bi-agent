"""
Idempotency and Deduplication Manager for Autonomous Workflows.
Prevents duplicate report generation, multiple webhook deliveries,
and redundant query executions across retries and worker crashes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.scheduled_job import JobRun, JobRunStatus

logger = structlog.get_logger(__name__)


class IdempotencyManager:
    """
    Enforces idempotent execution for background tasks, report snapshots,
    and notification dispatches.
    """

    @classmethod
    def generate_key(
        cls,
        job_id: str,
        schedule_window: str,
        resource_id: Optional[str] = None,
        extra_payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generates a deterministic SHA-256 idempotency key based on job identity,
        schedule window (e.g. '2026-03-01T09:00:00Z'), and target resource.
        """
        raw_components = {
            "job_id": str(job_id),
            "window": str(schedule_window),
            "resource_id": str(resource_id or ""),
            "payload": extra_payload or {},
        }
        serialized = json.dumps(raw_components, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    async def check_and_claim_execution(
        cls,
        db: AsyncSession,
        scheduled_job_id: Any,
        idempotency_key: str,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Checks if a job run with this idempotency key has already completed.
        Returns:
            (is_duplicate: bool, existing_result: Optional[dict])
        """
        # Look for existing runs for this job
        stmt = (
            select(JobRun)
            .where(
                JobRun.scheduled_job_id == scheduled_job_id,
                JobRun.status == JobRunStatus.COMPLETED,
            )
            .order_by(JobRun.created_at.desc())
            .limit(20)
        )
        res = await db.execute(stmt)
        completed_runs = res.scalars().all()

        for run in completed_runs:
            result_data = run.result or {}
            if result_data.get("idempotency_key") == idempotency_key:
                logger.info(
                    "idempotent_execution_skipped_duplicate",
                    job_id=str(scheduled_job_id),
                    idempotency_key=idempotency_key,
                    existing_run_id=str(run.id),
                )
                return True, result_data

        return False, None
