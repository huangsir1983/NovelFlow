"""Celery app with multi-queue routing for P1-1."""

from celery import Celery

from config import settings


celery_app = Celery(
    "unrealmake",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_default_queue=settings.queue_import_name,
    task_routes={
        "tasks.import_tasks.run_import_pipeline": {"queue": settings.queue_import_name},
        "tasks.media_tasks.generate_image_task": {"queue": settings.queue_image_name},
        "tasks.media_tasks.generate_video_task": {"queue": settings.queue_video_name},
        "tasks.export_tasks.export_project_mvp_task": {"queue": settings.queue_export_name},
    },
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
