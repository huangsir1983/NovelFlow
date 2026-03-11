"""Character model."""

import uuid
from sqlalchemy import Column, String, Text, ForeignKey, JSON, Float

from models.base import Base, TimestampMixin


class Character(Base, TimestampMixin):
    """Character table — a character extracted from the story."""

    __tablename__ = "characters"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    aliases = Column(JSON, default=lambda: [])  # ["nickname", ...]
    role = Column(String(50), default="supporting")  # protagonist | antagonist | supporting | minor
    description = Column(Text, default="")
    personality = Column(Text, default="")
    arc = Column(Text, default="")
    relationships = Column(JSON, default=lambda: [])  # [{target, type, dynamic, function}, ...]
    # Extended fields
    age_range = Column(String(50), default="")  # e.g. "18-22"
    appearance = Column(JSON, default=lambda: {})  # {face, body, hair, distinguishing_features}
    costume = Column(JSON, default=lambda: {})  # {typical_outfit, color_palette, texture_keywords}
    casting_tags = Column(JSON, default=lambda: [])  # ["冷艳", "文弱书生", ...]
    visual_reference = Column(Text, default="")  # English AI art prompt
    visual_prompt_negative = Column(Text, default="")  # elements to AVOID when generating
    desire = Column(Text, default="")  # core desire
    flaw = Column(Text, default="")  # fatal flaw

    def __repr__(self) -> str:
        return f"<Character(id={self.id}, name={self.name}, role={self.role})>"
