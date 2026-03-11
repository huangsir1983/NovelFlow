"""ImportTask model — tracks long-running novel import pipeline state."""

import uuid
from sqlalchemy import Column, String, Text, ForeignKey, JSON

from models.base import Base, TimestampMixin


class ImportTask(Base, TimestampMixin):
    """Import task table — tracks async import pipeline progress."""

    __tablename__ = "import_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), default="pending")  # pending | running | completed | failed
    current_phase = Column(String(30), default="segmenting")  # segmenting | scenes | characters | shots | merging | prompts
    progress = Column(JSON, default=lambda: {})  # {"scenes": 5, "characters_found": 3, ...}
    error = Column(Text, nullable=True)
    synopsis = Column(Text, nullable=True)  # cached full-text synopsis for reuse
    full_text = Column(Text, nullable=True)  # original full text for retry
    stream_checkpoint = Column(JSON, nullable=True)  # streaming parser checkpoint data
    style_template_id = Column(String(36), nullable=True)  # FK to style_templates.id

    def __repr__(self) -> str:
        return f"<ImportTask(id={self.id}, project_id={self.project_id}, status={self.status}, phase={self.current_phase})>"
