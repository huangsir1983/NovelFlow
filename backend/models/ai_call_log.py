"""AI Call Log model — tracks AI API usage and cost."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey

from models.base import Base


class AICallLog(Base):
    """Tracks every AI API call for cost analysis and budgeting."""

    __tablename__ = "ai_call_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    provider = Column(String(100), nullable=False, default="")
    model = Column(String(100), nullable=False, default="")
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)  # USD
    operation_type = Column(String(50), default="")  # import_pipeline, ai_operate, generate_beats, etc.
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<AICallLog(id={self.id}, provider={self.provider}, model={self.model}, cost={self.estimated_cost})>"
