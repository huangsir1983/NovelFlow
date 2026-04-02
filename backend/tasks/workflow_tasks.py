"""Celery tasks for workflow step execution."""

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="tasks.workflow_tasks.execute_workflow_step", bind=True, max_retries=3)
def execute_workflow_step(self, step_run_id: str, execution_id: str):
    """Execute a single workflow step."""
    from database import SessionLocal
    from services.workflow_engine import workflow_engine

    db = SessionLocal()
    try:
        from models.workflow_execution import WorkflowStepRun
        sr = db.query(WorkflowStepRun).get(step_run_id)
        if not sr:
            logger.error(f"StepRun not found: {step_run_id}")
            return

        logger.info(f"Executing step {sr.step_id} (type={sr.step_type})")

        # 根据 step_type 执行不同逻辑
        # TODO: 接入实际的图片/视频生成 API
        # 目前标记为 success 作为骨架
        workflow_engine.update_step_status(
            db, step_run_id,
            status="success",
            progress=100,
        )
    except Exception as e:
        logger.error(f"Step execution failed: {e}")
        workflow_engine.update_step_status(
            db, step_run_id,
            status="error",
            error_message=str(e),
        )
    finally:
        db.close()


@shared_task(name="tasks.workflow_tasks.advance_workflow")
def advance_workflow(execution_id: str):
    """Check current group completion and dispatch next group."""
    from database import SessionLocal
    from services.workflow_engine import workflow_engine

    db = SessionLocal()
    try:
        workflow_engine.advance_execution(db, execution_id)
    finally:
        db.close()
