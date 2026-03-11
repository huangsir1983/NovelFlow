"""CharacterVariant model — derived appearance variants for characters."""

import uuid
from sqlalchemy import Column, String, Text, ForeignKey, JSON

from models.base import Base, TimestampMixin


class CharacterVariant(Base, TimestampMixin):
    """Character variant table — state/period/style variants of a character."""

    __tablename__ = "character_variants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id = Column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=True, index=True)
    variant_type = Column(String(50), default="")  # childhood|wedding|injured|formal|casual|battle|aged|disguised|emotional_state
    variant_name = Column(String(255), default="")
    tags = Column(JSON, default=lambda: [])
    scene_ids = Column(JSON, default=lambda: [])
    trigger = Column(Text, default="")  # when/where this variant appears
    appearance_delta = Column(JSON, default=lambda: {})  # {face, body, hair, distinguishing_features}
    costume_override = Column(JSON, default=lambda: {})  # {outfit, color_palette}
    visual_reference = Column(Text, default="")  # English AI art prompt for this variant
    visual_prompt_negative = Column(Text, default="")  # elements to AVOID for this variant
    emotional_tone = Column(Text, default="")

    def __repr__(self) -> str:
        return f"<CharacterVariant(id={self.id}, variant_name={self.variant_name})>"
