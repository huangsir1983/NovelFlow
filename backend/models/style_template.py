"""StyleTemplate model — predefined visual style templates for image generation."""

import uuid
from sqlalchemy import Column, String, Text, Integer, Boolean, JSON

from models.base import Base, TimestampMixin


class StyleTemplate(Base, TimestampMixin):
    """Style template table — built-in or user-defined visual style presets.

    Each template contains positive style tags and negative prompts that are
    automatically applied to all asset visual prompts within a project.
    """

    __tablename__ = "style_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)          # "中国3D国漫"
    name_en = Column(String(100), default="")            # "Chinese 3D Animation"
    description = Column(Text, default="")               # template description
    style_tags = Column(JSON, default=lambda: [])        # ["3d_render", "chinese_animation", ...]
    style_negative = Column(Text, default="")            # "low quality, blurry, deformed, ..."
    preview_image_url = Column(String(500), default="")  # preview image URL
    category = Column(String(50), default="")            # "animation" / "realistic" / "illustration"
    is_builtin = Column(Boolean, default=True)           # built-in vs user-defined
    sort_order = Column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<StyleTemplate(id={self.id}, name={self.name}, category={self.category})>"
