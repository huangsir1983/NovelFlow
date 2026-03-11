"""Project model."""

import uuid
from sqlalchemy import Column, String, Text

from models.base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    """Project table — core entity."""

    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    import_source = Column(String(20), nullable=False, default="novel")  # novel | script | blank
    edition = Column(String(20), nullable=False, default="normal")       # normal | canvas | hidden | ultimate
    stage = Column(String(30), nullable=False, default="import")         # import | knowledge | beat_sheet | script | storyboard | visual_prompt | generation | complete
    current_phase = Column(String(20), nullable=False, default="workbench")  # workbench | board | preview

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name}, stage={self.stage}, phase={self.current_phase})>"
