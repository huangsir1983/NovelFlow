"""Export queue task placeholder for P1-1 queue split."""

from tasks.celery_app import celery_app


@celery_app.task(name="tasks.export_tasks.export_project_mvp_task")
def export_project_mvp_task(project_id: str):
    """Placeholder; current export still handled by API synchronously."""
    return {"accepted": True, "queue": "export", "project_id": project_id}
