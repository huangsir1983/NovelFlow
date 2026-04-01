"""Scene model."""

import uuid
from sqlalchemy import Column, String, Text, Integer, Float, ForeignKey, JSON, Index

from models.base import Base, TimestampMixin


class Scene(Base, TimestampMixin):
    """Scene table — a visual scene derived from beats."""

    __tablename__ = "scenes"
    __table_args__ = (
        Index("idx_scenes_project_order", "project_id", "order"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    beat_id = Column(String(36), ForeignKey("beats.id", ondelete="SET NULL"), nullable=True, index=True)
    heading = Column(String(500), default="")
    location = Column(String(255), default="")
    time_of_day = Column(String(50), default="")  # day | night | dawn | dusk | ...
    description = Column(Text, default="")
    action = Column(Text, default="")
    dialogue = Column(JSON, default=lambda: [])  # [{character, line}, ...]
    order = Column(Integer, nullable=False, default=0)
    tension_score = Column(Float, default=0.0)  # 0.0 to 1.0
    characters_present = Column(JSON, default=lambda: [])  # in-scene character names
    key_props = Column(JSON, default=lambda: [])  # key props list
    dramatic_purpose = Column(Text, default="")  # narrative function
    window_index = Column(Integer, nullable=True)  # source window index
    # Extended fields for narrative scene enrichment
    core_event = Column(Text, default="")  # core narrative event
    key_dialogue = Column(Text, default="")  # most critical dialogue line
    emotional_peak = Column(Text, default="")  # emotional peak description
    estimated_duration_s = Column(Integer, nullable=True)  # estimated duration in seconds
    visual_reference = Column(Text, default="")  # AI art prompt for the scene
    visual_prompt_negative = Column(Text, default="")  # elements to avoid
    source_text_start = Column(Text, default="")  # start of source text excerpt
    source_text_end = Column(Text, default="")  # end of source text excerpt
    generated_script = Column(Text, nullable=True)  # AI generated script text

    # 短剧增强字段（P_SCENE_ONLY_EXTRACT 输出）
    narrative_mode = Column(String(20), default="mixed")       # action|dialogue|mixed
    hook_type = Column(String(100), default="")                # 开场钩子类型
    cliffhanger = Column(Text, default="")                     # 结尾悬念钩子
    reversal_points = Column(JSON, default=lambda: [])         # 反转点列表
    sweet_spot = Column(Text, default="")                      # 爽点描述
    emotion_beat = Column(String(20), default="")              # 情绪节拍
    dialogue_budget = Column(String(10), default="medium")     # low|medium|high

    # 用户编辑后的原文（优先级高于 source_text_start/end 定位）
    edited_source_text = Column(Text, nullable=True)

    # 结构化剧本JSON（P_SCRIPT_GENERATE 输出）
    generated_script_json = Column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<Scene(id={self.id}, heading={self.heading}, order={self.order})>"
