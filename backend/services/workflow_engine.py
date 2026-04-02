"""Core WorkflowEngine — orchestrates chain template execution with parallel groups."""

import logging
import uuid
from datetime import datetime
from collections import defaultdict, deque
from sqlalchemy.orm import Session

from models.chain_template import ChainTemplate
from models.workflow_execution import WorkflowExecution, WorkflowStepRun
from models.canvas_workflow import CanvasNodeExecution

logger = logging.getLogger(__name__)


class WorkflowEngine:
    MAX_RETRIES = 3
    RETRY_DELAYS = [5, 30, 120]  # 秒

    # Step type → Celery queue 映射
    STEP_QUEUE_MAP = {
        'generate-grid9': 'image_queue',
        'generate-background': 'image_queue',
        'generate-character': 'image_queue',
        'generate-image-direct': 'image_queue',
        'scene-angle-transform': 'image_queue',
        'character-pose-adjust': 'image_queue',
        'remove-background': 'image_queue',
        'composite-layers': 'image_queue',
        'apply-filter': 'image_queue',
        'adjust-lighting': 'image_queue',
        'add-props': 'image_queue',
        'motion-blur': 'image_queue',
        'color-grade': 'image_queue',
        'blend-refine': 'image_queue',
        'set-video-keyframe': 'image_queue',
        'generate-video-direct': 'video_queue',
        'grid9-to-video': 'video_queue',
        'user-select-frame': None,  # 人工门，不入队列
    }

    def instantiate(self, db: Session, template_id: str, target_node_ids: list,
                    project_id: str, workflow_id: str, concurrency_limit: int = 3) -> WorkflowExecution:
        """从链模板创建执行实例。"""
        template = db.query(ChainTemplate).get(template_id)
        if not template:
            raise ValueError(f"Chain template not found: {template_id}")

        steps = template.steps or []
        parallel_groups = self.build_parallel_groups(steps)

        execution = WorkflowExecution(
            id=str(uuid.uuid4()),
            project_id=project_id,
            workflow_id=workflow_id,
            template_id=template_id,
            target_node_ids=target_node_ids,
            status="pending",
            parallel_groups=parallel_groups,
            current_group_index=0,
            concurrency_limit=concurrency_limit,
            total_steps=len(steps),
            completed_steps=0,
        )
        db.add(execution)

        # 为每个步骤创建 StepRun
        for step in steps:
            step_run = WorkflowStepRun(
                id=str(uuid.uuid4()),
                execution_id=execution.id,
                step_id=step["id"],
                step_type=step["type"],
                status="pending",
            )
            db.add(step_run)

        db.commit()
        db.refresh(execution)
        return execution

    def build_parallel_groups(self, steps: list) -> list:
        """Kahn 拓扑排序，将步骤按依赖层级分组。"""
        if not steps:
            return []

        step_ids = [s["id"] for s in steps]
        deps = {}
        for s in steps:
            deps[s["id"]] = [d for d in (s.get("dependsOn") or []) if d in step_ids]

        in_degree = {sid: 0 for sid in step_ids}
        adj = defaultdict(list)
        for sid, dep_list in deps.items():
            in_degree[sid] = len(dep_list)
            for d in dep_list:
                adj[d].append(sid)

        groups = []
        queue = deque([sid for sid in step_ids if in_degree[sid] == 0])

        while queue:
            group = list(queue)
            groups.append(group)
            next_queue = deque()
            for sid in group:
                for neighbor in adj[sid]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_queue.append(neighbor)
            queue = next_queue

        return groups

    def start_execution(self, db: Session, execution_id: str) -> WorkflowExecution:
        """启动执行：状态 pending → running，dispatch 第一组。"""
        execution = db.query(WorkflowExecution).get(execution_id)
        if not execution:
            raise ValueError(f"Execution not found: {execution_id}")
        if execution.status != "pending":
            raise ValueError(f"Cannot start execution in status: {execution.status}")

        execution.status = "running"
        execution.started_at = datetime.utcnow()
        db.commit()

        self._dispatch_current_group(db, execution)
        return execution

    def advance_execution(self, db: Session, execution_id: str) -> WorkflowExecution:
        """检查当前组完成情况，推进到下一组或结束。"""
        execution = db.query(WorkflowExecution).get(execution_id)
        if not execution or execution.status not in ("running", "paused"):
            return execution

        step_runs = db.query(WorkflowStepRun).filter(
            WorkflowStepRun.execution_id == execution_id
        ).all()
        step_map = {sr.step_id: sr for sr in step_runs}

        current_group = execution.parallel_groups[execution.current_group_index] if execution.current_group_index < len(execution.parallel_groups) else []
        group_runs = [step_map[sid] for sid in current_group if sid in step_map]

        # 检查是否有人工门暂停
        if any(sr.status == "paused" for sr in group_runs):
            execution.status = "paused"
            db.commit()
            return execution

        # 检查是否有错误
        failed = [sr for sr in group_runs if sr.status == "error"]
        if failed:
            retryable = [sr for sr in failed if sr.retry_count < self.MAX_RETRIES]
            if not retryable:
                execution.status = "error"
                execution.error_message = f"Step {failed[0].step_id} failed after {self.MAX_RETRIES} retries: {failed[0].error_message}"
                execution.completed_at = datetime.utcnow()
                db.commit()
                return execution
            # 还有可重试的，暂不推进
            return execution

        # 检查当前组是否全部成功
        if all(sr.status == "success" for sr in group_runs):
            execution.completed_steps = sum(1 for sr in step_runs if sr.status == "success")
            execution.current_group_index += 1

            if execution.current_group_index >= len(execution.parallel_groups):
                execution.status = "success"
                execution.completed_at = datetime.utcnow()
                db.commit()
                return execution

            db.commit()
            self._dispatch_current_group(db, execution)

        return execution

    def cancel_execution(self, db: Session, execution_id: str) -> WorkflowExecution:
        """取消执行。"""
        execution = db.query(WorkflowExecution).get(execution_id)
        if not execution:
            raise ValueError(f"Execution not found: {execution_id}")
        if execution.status in ("success", "cancelled"):
            return execution

        execution.status = "cancelled"
        execution.completed_at = datetime.utcnow()

        # 取消所有 pending/queued/running 的步骤
        pending_runs = db.query(WorkflowStepRun).filter(
            WorkflowStepRun.execution_id == execution_id,
            WorkflowStepRun.status.in_(["pending", "queued", "running"])
        ).all()
        for sr in pending_runs:
            sr.status = "cancelled"

        db.commit()
        return execution

    def retry_from_failed(self, db: Session, execution_id: str) -> WorkflowExecution:
        """从失败步骤重试。"""
        execution = db.query(WorkflowExecution).get(execution_id)
        if not execution or execution.status != "error":
            raise ValueError("Can only retry errored executions")

        failed_runs = db.query(WorkflowStepRun).filter(
            WorkflowStepRun.execution_id == execution_id,
            WorkflowStepRun.status == "error"
        ).all()

        for sr in failed_runs:
            sr.retry_count += 1
            sr.status = "pending"
            sr.error_message = None

        execution.status = "running"
        execution.error_message = None
        db.commit()

        self._dispatch_current_group(db, execution)
        return execution

    def resume_execution(self, db: Session, execution_id: str) -> WorkflowExecution:
        """恢复人工门暂停的执行。"""
        execution = db.query(WorkflowExecution).get(execution_id)
        if not execution or execution.status != "paused":
            raise ValueError("Can only resume paused executions")

        paused_runs = db.query(WorkflowStepRun).filter(
            WorkflowStepRun.execution_id == execution_id,
            WorkflowStepRun.status == "paused"
        ).all()

        for sr in paused_runs:
            sr.status = "success"  # 人工选帧完成
            sr.completed_at = datetime.utcnow()

        execution.status = "running"
        db.commit()

        return self.advance_execution(db, execution_id)

    def _dispatch_current_group(self, db: Session, execution: WorkflowExecution):
        """Dispatch 当前 group 的所有步骤。"""
        if execution.current_group_index >= len(execution.parallel_groups):
            return

        current_group = execution.parallel_groups[execution.current_group_index]
        step_runs = db.query(WorkflowStepRun).filter(
            WorkflowStepRun.execution_id == execution.id,
            WorkflowStepRun.step_id.in_(current_group)
        ).all()

        for sr in step_runs:
            if sr.status not in ("pending",):
                continue

            if sr.step_type == "user-select-frame":
                sr.status = "paused"
                sr.started_at = datetime.utcnow()
                logger.info(f"Step {sr.step_id} paused for user selection")
            else:
                sr.status = "queued"
                sr.started_at = datetime.utcnow()
                logger.info(f"Step {sr.step_id} queued for execution (type={sr.step_type})")
                # TODO: 实际 Celery task dispatch
                # queue = self.STEP_QUEUE_MAP.get(sr.step_type, 'image_queue')
                # from tasks.workflow_tasks import execute_workflow_step
                # execute_workflow_step.apply_async(
                #     args=[sr.id, execution.id],
                #     queue=queue,
                #     countdown=0
                # )

                # For now, simulate immediate success for non-video steps
                # In production, this would be handled by Celery callback
                sr.status = "running"

            # 创建对应的 CanvasNodeExecution 审计记录
            for node_id in (execution.target_node_ids or []):
                audit = CanvasNodeExecution(
                    id=str(uuid.uuid4()),
                    workflow_id=execution.workflow_id,
                    node_id=node_id,
                    node_type=sr.step_type,
                    status="running",
                    agent_task_type=f"chain_step_{sr.step_type}",
                )
                db.add(audit)

        db.commit()

    def update_step_status(self, db: Session, step_run_id: str,
                           status: str, result_url: str = None,
                           result_data: dict = None, error_message: str = None,
                           progress: int = None, tokens_used: int = 0,
                           model_used: str = None):
        """外部回调更新步骤状态。"""
        sr = db.query(WorkflowStepRun).get(step_run_id)
        if not sr:
            return

        sr.status = status
        if result_url:
            sr.result_url = result_url
        if result_data:
            sr.result_data = result_data
        if error_message:
            sr.error_message = error_message
        if progress is not None:
            sr.progress = progress
        if tokens_used:
            sr.tokens_used = tokens_used
        if model_used:
            sr.model_used = model_used

        if status in ("success", "error"):
            sr.completed_at = datetime.utcnow()

        db.commit()

        # 自动推进执行
        self.advance_execution(db, sr.execution_id)


# 全局单例
workflow_engine = WorkflowEngine()
