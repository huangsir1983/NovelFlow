"""Workflow execution models — tracks chain execution state and step runs."""

import uuid
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, JSON

from models.base import Base, TimestampMixin


class WorkflowExecution(Base, TimestampMixin):
    """A running or completed execution of a chain template against canvas nodes."""

    __tablename__ = "workflow_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_id = Column(
        String(36),
        ForeignKey("canvas_workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id = Column(
        String(36),
        ForeignKey("chain_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_node_ids = Column(JSON, default=lambda: [])
    status = Column(String(20), default="pending")  # pending|queued|running|paused|success|error|cancelled
    parallel_groups = Column(JSON, default=lambda: [])  # [[stepId, ...], ...]
    current_group_index = Column(Integer, default=0)
    concurrency_limit = Column(Integer, default=3)
    total_steps = Column(Integer, default=0)
    completed_steps = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<WorkflowExecution(id={self.id}, status={self.status})>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "projectId": self.project_id,
            "workflowId": self.workflow_id,
            "templateId": self.template_id,
            "targetNodeIds": self.target_node_ids or [],
            "status": self.status,
            "parallelGroups": self.parallel_groups or [],
            "currentGroupIndex": self.current_group_index,
            "concurrencyLimit": self.concurrency_limit,
            "totalSteps": self.total_steps,
            "completedSteps": self.completed_steps,
            "errorMessage": self.error_message,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class WorkflowStepRun(Base, TimestampMixin):
    """Individual step execution record within a workflow execution."""

    __tablename__ = "workflow_step_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(
        String(36),
        ForeignKey("workflow_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_id = Column(String(100), nullable=False)
    step_type = Column(String(50), nullable=False)
    status = Column(String(20), default="pending")  # pending|queued|running|paused|success|error|cancelled
    result_url = Column(Text, nullable=True)
    result_data = Column(JSON, default=lambda: {})
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    progress = Column(Integer, default=0)  # 0-100
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    tokens_used = Column(Integer, default=0)
    model_used = Column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<WorkflowStepRun(id={self.id}, step={self.step_id}, status={self.status})>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "executionId": self.execution_id,
            "stepId": self.step_id,
            "stepType": self.step_type,
            "status": self.status,
            "resultUrl": self.result_url,
            "resultData": self.result_data or {},
            "errorMessage": self.error_message,
            "retryCount": self.retry_count,
            "progress": self.progress,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "tokensUsed": self.tokens_used,
            "modelUsed": self.model_used,
        }
