"""Chapter model."""

import uuid
from sqlalchemy import Column, String, Text, Integer, ForeignKey

from models.base import Base, TimestampMixin


class Chapter(Base, TimestampMixin):
    """Chapter table — a section of an imported novel."""

    __tablename__ = "chapters"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="")
    content = Column(Text, default="")
    order = Column(Integer, nullable=False, default=0)
    word_count = Column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<Chapter(id={self.id}, title={self.title}, order={self.order})>"
