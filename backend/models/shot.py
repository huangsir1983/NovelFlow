"""Shot model — individual camera shots within a scene."""

import uuid
from sqlalchemy import Column, String, Text, Integer, Float, ForeignKey, JSON

from models.base import Base, TimestampMixin


class Shot(Base, TimestampMixin):
    """Shot table — atomic camera unit within a scene."""

    __tablename__ = "shots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    scene_id = Column(String(36), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False, index=True)
    shot_number = Column(Integer, nullable=False, default=0)
    goal = Column(Text, default="")
    composition = Column(Text, default="")
    camera_angle = Column(String(100), default="")
    camera_movement = Column(String(100), default="")  # static|pan|tilt|dolly|crane|handheld|steadicam|zoom
    framing = Column(String(20), default="")  # ECU|CU|MCU|MS|MLS|FS|WS
    duration_estimate = Column(String(20), default="")  # "2-3s"
    characters_in_frame = Column(JSON, default=lambda: [])
    emotion_target = Column(Text, default="")
    dramatic_intensity = Column(Float, default=0.0)  # -1.0 ~ 1.0
    transition_in = Column(String(100), default="")
    transition_out = Column(String(100), default="")
    description = Column(Text, default="")
    visual_prompt = Column(Text, default="")
    order = Column(Integer, nullable=False, default=0)
    # Shot Card fields (newplan4)
    beat_id = Column(String(36), ForeignKey("beats.id", ondelete="SET NULL"), nullable=True, index=True)
    reference_assets = Column(JSON, default=lambda: [])
    candidates = Column(JSON, default=lambda: [])
    quality_score = Column(JSON, default=lambda: {})
    next_action = Column(String(100), default="")
    status = Column(String(20), default="draft")  # draft | reviewed | approved

    def __repr__(self) -> str:
        return f"<Shot(id={self.id}, scene_id={self.scene_id}, shot_number={self.shot_number}, status={self.status})>"
