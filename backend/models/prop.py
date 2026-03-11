"""Prop model — visual asset card for story props."""

import uuid
from sqlalchemy import Column, String, Text, Integer, Boolean, ForeignKey, JSON

from models.base import Base, TimestampMixin


class Prop(Base, TimestampMixin):
    """Prop table — a narrative prop with visual asset data."""

    __tablename__ = "props"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(50), default="")  # costume|weapon|furniture|document|food|container|symbolic|jewelry|stationery|medical
    description = Column(Text, default="")
    visual_reference = Column(Text, default="")  # English AI art prompt
    visual_prompt_negative = Column(Text, default="")  # elements to AVOID when generating
    narrative_function = Column(Text, default="")
    is_motif = Column(Boolean, default=False)
    is_major = Column(Boolean, default=False)  # appears >= 3 times
    scenes_present = Column(JSON, default=lambda: [])  # ["scene_001", ...]
    appearance_count = Column(Integer, default=0)
    emotional_association = Column(Text, default="")

    def __repr__(self) -> str:
        return f"<Prop(id={self.id}, name={self.name}, major={self.is_major})>"
