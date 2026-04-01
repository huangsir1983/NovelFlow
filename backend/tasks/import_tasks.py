"""Import pipeline queue tasks."""

import logging

from database import SessionLocal
from models.import_task import ImportTask
from services.import_pipeline import ImportPipeline
from services.task_quota import QuotaLease, release_quota
from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.import_tasks.run_import_pipeline", bind=True, max_retries=3, default_retry_delay=10)
def run_import_pipeline(
    self,
    task_id: str,
    project_id: str,
    full_text: str,
    mode: str = "full",
    tenant_id: str = "default",
):
    db = SessionLocal()
    lease = QuotaLease(keys=[
        "quota:import:global",
        f"quota:import:tenant:{tenant_id or 'default'}",
        f"quota:import:project:{project_id}",
    ])
    try:
        task = db.query(ImportTask).filter(ImportTask.id == task_id).first()
        if task:
            task.status = "running"
            db.commit()

        pipeline = ImportPipeline(
            task_id=task_id,
            project_id=project_id,
            full_text=full_text,
            db_factory=SessionLocal,
            mode=mode,
        )
        pipeline.run()
        return {"task_id": task_id, "status": "completed"}

    except Exception as e:
        logger.exception("Import queue task failed: %s", task_id)
        try:
            fail_task = db.query(ImportTask).filter(ImportTask.id == task_id).first()
            if fail_task:
                fail_task.status = "failed"
                fail_task.error = str(e)
                db.commit()
        except Exception:
            db.rollback()
        raise
    finally:
        release_quota(lease)
        db.close()
