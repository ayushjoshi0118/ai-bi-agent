"""
Celery worker and Beat scheduler initialization.
"""

from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "bi_agent_tasks",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    worker_prefetch_multiplier=1,
)

# Celery Beat recurring schedules
celery_app.conf.beat_schedule = {
    "hourly-anomaly-detection": {
        "task": "app.tasks.anomaly_detection.run_periodic_anomaly_scans",
        "schedule": 3600.0,  # Run every hour
    },
}
