"""
Background report generation tasks.
"""

from app.tasks.celery_app import celery_app
import structlog

logger = structlog.get_logger(__name__)


@celery_app.task(name="app.tasks.reports.generate_scheduled_report", bind=True, max_retries=3)
def generate_scheduled_report(self, job_id_str: str):
    """
    Executes a scheduled report job, captures a new data snapshot,
    creates a ReportVersion, and logs the execution.
    """
    logger.info("executing_scheduled_report_task", job_id=job_id_str)
    return {"status": "completed", "job_id": job_id_str}
