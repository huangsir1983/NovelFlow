"""ShotGroup model — merged shots forming a VFF segment."""

import uuid
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON, Index

from models.base import Base, TimestampMixin


class ShotGroup(Base, TimestampMixin):
    """ShotGroup table — merged shot segments with VFF script and visual prompts."""

    __tablename__ = "shot_groups"
    __table_args__ = (
        Index("idx_shot_groups_project_scene_order", "project_id", "scene_id", "order"),
    )
    __table_args__ = (
        Index("idx_shot_groups_project_scene_order", "project_id", "scene_id", "order"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    scene_id = Column(String(36), ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True, index=True)
    shot_ids = Column(JSON, default=lambda: [])
    segment_number = Column(Integer, nullable=False, default=0)
    duration = Column(String(20), default="")  # "6s"
    transition_type = Column(String(100), default="")
    emotional_beat = Column(Text, default="")
    continuity = Column(Text, default="")
    vff_body = Column(Text, default="")
    merge_rationale = Column(Text, default="")
    style_metadata = Column(JSON, default=lambda: {})  # {aspect_ratio, mood, ...}
    visual_prompt_positive = Column(Text, default="")
    visual_prompt_negative = Column(Text, default="")
    style_tags = Column(JSON, default=lambda: [])
    order = Column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<ShotGroup(id={self.id}, scene_id={self.scene_id}, segment_number={self.segment_number})>"
