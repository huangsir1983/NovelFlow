"""Image/video queue task placeholders for P1-1 queue split."""

from tasks.celery_app import celery_app


@celery_app.task(name="tasks.media_tasks.generate_image_task")
def generate_image_task(payload: dict):
    """Placeholder task for queue routing; API remains synchronous for now."""
    return {"accepted": True, "queue": "image", "payload": payload}


@celery_app.task(name="tasks.media_tasks.generate_video_task")
def generate_video_task(payload: dict):
    """Placeholder task for queue routing; API remains synchronous for now."""
    return {"accepted": True, "queue": "video", "payload": payload}
