"""
涛割 - 项目数据模型
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class Project(Base):
    """项目模型"""
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, default="未命名项目")
    description = Column(Text, nullable=True)

    # 源文件信息
    source_type = Column(String(50), default="srt")  # srt, script, video
    source_path = Column(String(512), nullable=True)
    source_content = Column(Text, nullable=True)

    # 项目设置
    canvas_width = Column(Integer, default=1920)
    canvas_height = Column(Integer, default=1080)
    fps = Column(Integer, default=30)
    total_duration = Column(Float, default=0.0)  # 总时长（秒）

    # 生成设置
    generation_mode = Column(String(50), default="image_to_video")
    default_model = Column(String(50), default="vidu")

    # 状态和时间
    status = Column(String(50), default="draft")  # draft, processing, completed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 统计信息
    total_scenes = Column(Integer, default=0)
    completed_scenes = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)

    # Animatic 设置
    animatic_settings = Column(JSON, nullable=True)  # {bgm_path, default_duration, transition_type}

    # ── 视觉圣经（项目级设置 v1.2） ──
    lighting_bible = Column(JSON, nullable=True)
    # {
    #   "color_palette": [{"name": "主色", "hex": "#F5E8C7"}, ...],
    #   "default_lighting": "暖金色柔光",
    #   "lighting_presets": [{"name": "室内日间", "desc": "..."}],
    #   "lut_description": "..."
    # }

    cinematography_guide = Column(JSON, nullable=True)
    # {
    #   "default_camera_style": "50mm 手持",
    #   "pace_rules": {"emotion": "慢推镜", "action": "高速切"},
    #   "reference_films": ["寄生虫", "盗梦空间"],
    #   "camera_presets": [{"name": "紧张追逐", "movement": "...", "shake": 0.7}]
    # }

    continuity_bible = Column(JSON, nullable=True)
    # {
    #   "state_tracking": [{"scene_index": 3, "note": "角色受伤戴绷带"}],
    #   "transition_rules": "从上一段结束姿态自然延续",
    #   "last_frame_archive": true
    # }

    # 关联关系
    scenes = relationship("Scene", back_populates="project", cascade="all, delete-orphan")
    acts = relationship("Act", back_populates="project", cascade="all, delete-orphan", order_by="Act.act_index")
    characters = relationship("Character", back_populates="project", cascade="all, delete-orphan")
    props = relationship("Prop", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    costs = relationship("CostRecord", back_populates="project", cascade="all, delete-orphan")
    assets = relationship("Asset", back_populates="project", cascade="all, delete-orphan")
    asset_requirements = relationship("AssetRequirement", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', status='{self.status}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'source_type': self.source_type,
            'source_path': self.source_path,
            'canvas_width': self.canvas_width,
            'canvas_height': self.canvas_height,
            'fps': self.fps,
            'total_duration': self.total_duration,
            'generation_mode': self.generation_mode,
            'default_model': self.default_model,
            'status': self.status,
            'total_scenes': self.total_scenes,
            'completed_scenes': self.completed_scenes,
            'total_cost': self.total_cost,
            'animatic_settings': self.animatic_settings,
            'lighting_bible': self.lighting_bible,
            'cinematography_guide': self.cinematography_guide,
            'continuity_bible': self.continuity_bible,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
