"""
涛割 - 道具数据模型
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class Prop(Base):
    """道具模型"""
    __tablename__ = 'props'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)

    # 基础信息
    name = Column(String(255), nullable=False, default="未命名道具")
    description = Column(Text, nullable=True)
    prop_type = Column(String(50), default="object")  # object, vehicle, weapon, food, etc.

    # 视觉信息
    reference_image = Column(String(512), nullable=True)
    prompt_description = Column(Text, nullable=True)  # AI生成用的提示词描述

    # 标记
    is_global = Column(Boolean, default=False)  # 是否全局道具（跨项目可用）
    is_active = Column(Boolean, default=True)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关联关系
    project = relationship("Project", back_populates="props")
    scene_props = relationship("SceneProp", back_populates="prop", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Prop(id={self.id}, name='{self.name}', type='{self.prop_type}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'name': self.name,
            'description': self.description,
            'prop_type': self.prop_type,
            'reference_image': self.reference_image,
            'prompt_description': self.prompt_description,
            'is_global': self.is_global,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class SceneProp(Base):
    """场景-道具关联模型"""
    __tablename__ = 'scene_props'

    id = Column(Integer, primary_key=True, autoincrement=True)
    scene_id = Column(Integer, ForeignKey('scenes.id'), nullable=False)
    prop_id = Column(Integer, ForeignKey('props.id'), nullable=False)

    # 位置信息（用于画布显示）
    position_x = Column(Float, default=0.5)
    position_y = Column(Float, default=0.5)
    scale = Column(Float, default=1.0)

    # 关联
    scene = relationship("Scene", back_populates="scene_props")
    prop = relationship("Prop", back_populates="scene_props")

    def __repr__(self):
        return f"<SceneProp(scene_id={self.scene_id}, prop_id={self.prop_id})>"

    def to_dict(self):
        return {
            'id': self.id,
            'scene_id': self.scene_id,
            'prop_id': self.prop_id,
            'position_x': self.position_x,
            'position_y': self.position_y,
            'scale': self.scale,
        }
