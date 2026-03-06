"""
涛割 - 场次(Act)数据模型
大场景/场次层级，介于 Project 和 Scene 之间
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class Act(Base):
    """场次模型 - 大场景/情节段落"""
    __tablename__ = 'acts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)

    # 排序与标识
    act_index = Column(Integer, nullable=False, default=0)  # 排序序号
    title = Column(String(255), nullable=True)  # 场次标题

    # AI 摘要与原文引用
    summary = Column(Text, nullable=True)  # AI 摘要（可编辑）
    source_text_range = Column(JSON, nullable=True)  # [start_char, end_char] 原文引用偏移

    # 标签与节奏
    tags = Column(JSON, default=list)  # 侧边标签 ["钩子","高潮"]
    rhythm_label = Column(String(50), nullable=True)  # 节奏标签: 钩子/铺垫/高潮/收束

    # 时长与控制
    target_duration = Column(Float, default=0.0)  # 目标时长（秒）
    is_skipped = Column(Boolean, default=False)  # 是否跳过

    # 状态
    status = Column(String(50), default="draft")  # draft/analyzed/ready

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关联关系
    project = relationship("Project", back_populates="acts")
    scenes = relationship("Scene", back_populates="act", order_by="Scene.scene_index")

    def __repr__(self):
        return f"<Act(id={self.id}, index={self.act_index}, title='{self.title}', status='{self.status}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'act_index': self.act_index,
            'title': self.title,
            'summary': self.summary,
            'source_text_range': self.source_text_range,
            'tags': self.tags or [],
            'rhythm_label': self.rhythm_label,
            'target_duration': self.target_duration,
            'is_skipped': self.is_skipped,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
