"""Canvas workflow model — stores infinite canvas state per project."""

import uuid
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON

from models.base import Base, TimestampMixin


class CanvasWorkflow(Base, TimestampMixin):
    """Canvas workflow — stores nodes, edges, modules for infinite canvas."""

    __tablename__ = "canvas_workflows"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), default="默认画布")
    status = Column(String(20), default="draft")  # draft | active | archived
    template_id = Column(String(100), nullable=True)
    workflow_json = Column(JSON, default=lambda: {})  # Full canvas state
    node_count = Column(Integer, default=0)
    version = Column(Integer, default=1)

    def __repr__(self) -> str:
        return f"<CanvasWorkflow(id={self.id}, project_id={self.project_id}, status={self.status})>"


class CanvasNodeExecution(Base, TimestampMixin):
    """Record of individual node executions within a canvas workflow."""

    __tablename__ = "canvas_node_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String(36), ForeignKey("canvas_workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id = Column(String(100), nullable=False, index=True)
    node_type = Column(String(50), nullable=False)  # storyboard | image | video
    status = Column(String(20), default="pending")  # pending | running | done | error
    input_snapshot = Column(JSON, default=lambda: {})
    output_snapshot = Column(JSON, default=lambda: {})
    agent_task_type = Column(String(50), nullable=True)
    tokens_used = Column(Integer, default=0)
    model_used = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<CanvasNodeExecution(id={self.id}, node_id={self.node_id}, status={self.status})>"
