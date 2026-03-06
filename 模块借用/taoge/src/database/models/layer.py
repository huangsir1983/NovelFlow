"""
涛割 - 图层数据模型
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class Layer(Base):
    """图层模型 - 场景内的独立可编辑图层"""
    __tablename__ = 'layers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    scene_id = Column(Integer, ForeignKey('scenes.id'), nullable=False)

    # 层属性
    name = Column(String(255), default="Layer")
    layer_type = Column(String(50), nullable=False)  # character/background/prop/foreground/effect/reference
    z_order = Column(Integer, default=0)
    is_visible = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    is_reference = Column(Boolean, default=False)  # 洋葱皮参考层
    color_label = Column(String(20), nullable=True)  # 颜色标签

    # 图片资源
    image_path = Column(String(512), nullable=True)  # 基础图路径
    original_image_path = Column(String(512), nullable=True)  # 资产原始图路径（视角转换时不覆盖）
    mask_path = Column(String(512), nullable=True)   # 蒙版路径

    # 变换参数
    transform = Column(JSON, default=dict)  # {x, y, rotation, scale_x, scale_y, flip_h, flip_v}

    # 混合模式 & 透明度
    blend_mode = Column(String(30), default='normal')  # normal/multiply/screen/overlay/...
    opacity = Column(Float, default=1.0)  # 0.0 ~ 1.0

    # AI 相关
    prompt_history = Column(JSON, default=list)  # [{prompt, timestamp, model}]
    character_id = Column(Integer, ForeignKey('characters.id'), nullable=True)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关联
    scene = relationship("Scene", back_populates="layers")
    character = relationship("Character")

    def __repr__(self):
        return f"<Layer(id={self.id}, scene_id={self.scene_id}, type='{self.layer_type}', name='{self.name}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'scene_id': self.scene_id,
            'name': self.name,
            'layer_type': self.layer_type,
            'z_order': self.z_order,
            'is_visible': self.is_visible,
            'is_locked': self.is_locked,
            'is_reference': self.is_reference,
            'color_label': self.color_label,
            'image_path': self.image_path,
            'original_image_path': self.original_image_path,
            'mask_path': self.mask_path,
            'transform': self.transform or {},
            'blend_mode': self.blend_mode or 'normal',
            'opacity': self.opacity if self.opacity is not None else 1.0,
            'prompt_history': self.prompt_history or [],
            'character_id': self.character_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
