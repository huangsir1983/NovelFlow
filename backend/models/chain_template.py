"""Chain template model — reusable workflow chain definitions for canvas nodes."""

import uuid
from sqlalchemy import Column, String, Text, Integer, Boolean, ForeignKey, JSON

from models.base import Base, TimestampMixin


class ChainTemplate(Base, TimestampMixin):
    """Reusable chain template for canvas workflow execution.

    Builtin templates have is_builtin=True and project_id=None.
    User-created templates are scoped to a project.
    """

    __tablename__ = "chain_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    icon = Column(String(10), default="◆")
    color = Column(String(10), default="#378ADD")
    tags = Column(JSON, default=lambda: [])
    is_builtin = Column(Boolean, default=False)
    steps = Column(JSON, default=lambda: [])  # ChainStep[]
    video_provider = Column(String(20), default="jimeng")
    estimated_minutes = Column(Integer, default=5)
    version = Column(Integer, default=1)
    share_mode = Column(String(20), default="private")  # private | project | global

    def __repr__(self) -> str:
        return f"<ChainTemplate(id={self.id}, name={self.name}, builtin={self.is_builtin})>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "projectId": self.project_id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "color": self.color,
            "tags": self.tags or [],
            "isBuiltin": self.is_builtin,
            "steps": self.steps or [],
            "videoProvider": self.video_provider,
            "estimatedMinutes": self.estimated_minutes,
            "version": self.version,
            "shareMode": self.share_mode,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
