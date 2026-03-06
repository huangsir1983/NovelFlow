"""Scene model."""

import uuid
from sqlalchemy import Column, String, Text, Integer, Float, ForeignKey, JSON

from models.base import Base, TimestampMixin


class Scene(Base, TimestampMixin):
    """Scene table — a visual scene derived from beats."""

    __tablename__ = "scenes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    beat_id = Column(String(36), ForeignKey("beats.id", ondelete="SET NULL"), nullable=True, index=True)
    heading = Column(String(500), default="")
    location = Column(String(255), default="")
    time_of_day = Column(String(50), default="")  # day | night | dawn | dusk | ...
    description = Column(Text, default="")
    action = Column(Text, default="")
    dialogue = Column(JSON, default=list)  # [{character, line}, ...]
    order = Column(Integer, nullable=False, default=0)
    tension_score = Column(Float, default=0.0)  # 0.0 to 1.0

    def __repr__(self) -> str:
        return f"<Scene(id={self.id}, heading={self.heading}, order={self.order})>"
