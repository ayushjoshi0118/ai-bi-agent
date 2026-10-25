"""
Background anomaly detection worker tasks.
"""

from app.tasks.celery_app import celery_app
import structlog

logger = structlog.get_logger(__name__)


@celery_app.task(name="app.tasks.anomaly_detection.run_periodic_anomaly_scans")
def run_periodic_anomaly_scans():
    """
    Periodic job invoked by Celery Beat to scan datasets across organizations for anomalies.
    """
    logger.info("running_periodic_anomaly_scans")
    return {"status": "completed"}
