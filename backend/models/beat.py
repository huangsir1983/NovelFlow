"""Beat model."""

import uuid
from sqlalchemy import Column, String, Text, Integer, Float, ForeignKey

from models.base import Base, TimestampMixin


class Beat(Base, TimestampMixin):
    """Beat table — a narrative beat in the story structure."""

    __tablename__ = "beats"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False, default="")
    description = Column(Text, default="")
    beat_type = Column(String(50), default="event")  # event | dialogue | action | transition | revelation
    emotional_value = Column(Float, default=0.0)  # -1.0 to 1.0
    order = Column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<Beat(id={self.id}, title={self.title}, type={self.beat_type})>"
