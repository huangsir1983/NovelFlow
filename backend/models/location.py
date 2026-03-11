"""Location model."""

import uuid
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON

from models.base import Base, TimestampMixin


class Location(Base, TimestampMixin):
    """Location table — a story location / setting with visual asset data."""

    __tablename__ = "locations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    visual_description = Column(Text, default="")
    mood = Column(String(100), default="")
    sensory = Column(Text, default="")  # sound, smell, temperature, texture
    narrative_function = Column(Text, default="")  # dramatic role in story
    # Extended fields for location asset cards
    type = Column(String(50), default="")  # interior|exterior|mixed
    era_style = Column(Text, default="")  # architectural era and style
    visual_reference = Column(Text, default="")  # English AI art prompt
    visual_prompt_negative = Column(Text, default="")  # elements to AVOID when generating
    atmosphere = Column(Text, default="")  # atmosphere keywords
    color_palette = Column(JSON, default=lambda: [])  # ["主色调1", "主色调2", "主色调3"]
    lighting = Column(Text, default="")  # lighting characteristics
    key_features = Column(JSON, default=lambda: [])  # landmark visual elements
    narrative_scene_ids = Column(JSON, default=lambda: [])  # ["scene_001", ...]
    scene_count = Column(Integer, default=0)
    time_variations = Column(JSON, default=lambda: [])  # ["day", "night"]
    emotional_range = Column(Text, default="")  # emotional span across scenes

    def __repr__(self) -> str:
        return f"<Location(id={self.id}, name={self.name})>"
