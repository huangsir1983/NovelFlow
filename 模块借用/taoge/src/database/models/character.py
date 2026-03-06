"""
涛割 - 角色数据模型
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class Character(Base):
    """角色模型 - 用于角色一致性管理"""
    __tablename__ = 'characters'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)  # 可以是全局角色

    # 基础信息
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    character_type = Column(String(50), default="human")  # human, animal, creature, object

    # 角色特征描述（用于生成Prompt）
    appearance = Column(Text, nullable=True)  # 外貌描述
    clothing = Column(Text, nullable=True)  # 服装描述
    personality = Column(Text, nullable=True)  # 性格特征
    voice_style = Column(String(100), nullable=True)  # 声音风格

    # 参考图片
    reference_images = Column(JSON, default=list)  # 角色参考图路径列表
    main_reference_image = Column(String(512), nullable=True)  # 主参考图

    # 一致性相关
    consistency_embedding = Column(Text, nullable=True)  # 一致性向量（如有）
    consistency_model = Column(String(50), nullable=True)  # 使用的一致性模型

    # 动作表情资源（PSD文件或图层路径）
    expression_assets = Column(JSON, default=dict)  # {"开心": "path", "生气": "path"}
    left_hand_assets = Column(JSON, default=dict)
    right_hand_assets = Column(JSON, default=dict)
    body_assets = Column(JSON, default=dict)

    # 状态
    is_global = Column(Boolean, default=False)  # 是否全局角色（跨项目可用）
    is_active = Column(Boolean, default=True)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关联关系
    project = relationship("Project", back_populates="characters")
    scene_characters = relationship("SceneCharacter", back_populates="character", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Character(id={self.id}, name='{self.name}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'name': self.name,
            'description': self.description,
            'character_type': self.character_type,
            'appearance': self.appearance,
            'clothing': self.clothing,
            'personality': self.personality,
            'reference_images': self.reference_images,
            'main_reference_image': self.main_reference_image,
            'is_global': self.is_global,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def get_full_description(self) -> str:
        """获取完整的角色描述（用于Prompt生成）"""
        parts = []
        if self.name:
            parts.append(f"角色名: {self.name}")
        if self.appearance:
            parts.append(f"外貌: {self.appearance}")
        if self.clothing:
            parts.append(f"服装: {self.clothing}")
        if self.personality:
            parts.append(f"性格: {self.personality}")
        return "; ".join(parts)
