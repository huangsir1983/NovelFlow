"""Character model."""

import uuid
from sqlalchemy import Column, String, Text, ForeignKey, JSON

from models.base import Base, TimestampMixin


class Character(Base, TimestampMixin):
    """Character table — a character extracted from the story."""

    __tablename__ = "characters"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    aliases = Column(JSON, default=list)  # ["nickname", ...]
    role = Column(String(50), default="supporting")  # protagonist | antagonist | supporting | minor
    description = Column(Text, default="")
    personality = Column(Text, default="")
    arc = Column(Text, default="")
    relationships = Column(JSON, default=list)  # [{character_id, type, description}, ...]

    def __repr__(self) -> str:
        return f"<Character(id={self.id}, name={self.name}, role={self.role})>"
