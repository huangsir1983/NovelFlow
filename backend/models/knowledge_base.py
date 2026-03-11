"""KnowledgeBase model."""

import uuid
from sqlalchemy import Column, String, ForeignKey, JSON

from models.base import Base, TimestampMixin


class KnowledgeBase(Base, TimestampMixin):
    """KnowledgeBase table — project-level world building and style guide."""

    __tablename__ = "knowledge_bases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    world_building = Column(JSON, default=lambda: {})  # {setting, era, rules, tone, ...}
    style_guide = Column(JSON, default=lambda: {})  # {pov, tense, voice, genre, ...}

    def __repr__(self) -> str:
        return f"<KnowledgeBase(id={self.id}, project_id={self.project_id})>"
