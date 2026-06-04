from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "bella_vladi",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.tasks_analysis",
        "app.workers.tasks_report",
        "app.workers.tasks_broadcast",
        "app.workers.tasks_telegram",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_concurrency=settings.queue_concurrency,
    task_default_queue="default",
    task_routes={
        "app.workers.tasks_analysis.run_analysis_pipeline": {"queue": "analysis"},
        "app.workers.tasks_report.regenerate_report_task": {"queue": "report"},
        "app.workers.tasks_broadcast.send_broadcast_task": {"queue": "telegram"},
        "app.workers.tasks_telegram.*": {"queue": "telegram"},
    },
    task_track_started=True,
    result_expires=settings.celery_result_expires_seconds,
    broker_connection_retry_on_startup=True,
)
