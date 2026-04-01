"""ImportTask model — tracks long-running novel import pipeline state."""

import uuid
from sqlalchemy import Column, String, Text, ForeignKey, JSON, Integer, Index

from models.base import Base, TimestampMixin


class ImportTask(Base, TimestampMixin):
    """Import task table — tracks async import pipeline progress."""

    __tablename__ = "import_tasks"
    __table_args__ = (
        Index("idx_import_tasks_project_created", "project_id", "created_at"),
    )
    __table_args__ = (
        Index("idx_import_tasks_project_created", "project_id", "created_at"),
    )

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
    novel_analysis = Column(Text, nullable=True)  # AI analysis report text (human-readable)
    novel_analysis_json = Column(JSON, nullable=True)  # structured director's baseline from analysis
    story_bible_overrides = Column(JSON, nullable=True)  # user overrides for story bible parameters

    # Source file metadata (P0-3)
    source_file_name = Column(String(255), nullable=True)
    source_storage_provider = Column(String(20), nullable=True)
    source_storage_key = Column(String(512), nullable=True)
    source_storage_uri = Column(Text, nullable=True)
    source_file_size = Column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<ImportTask(id={self.id}, project_id={self.project_id}, status={self.status}, phase={self.current_phase})>"
