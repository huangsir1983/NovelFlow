"""Location model."""

import uuid
from sqlalchemy import Column, String, Text, ForeignKey

from models.base import Base, TimestampMixin


class Location(Base, TimestampMixin):
    """Location table — a story location / setting."""

    __tablename__ = "locations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    visual_description = Column(Text, default="")
    mood = Column(String(100), default="")

    def __repr__(self) -> str:
        return f"<Location(id={self.id}, name={self.name})>"
