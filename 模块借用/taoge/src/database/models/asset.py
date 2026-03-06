"""
涛割 - 资产数据模型
统一资产模型（Asset）涵盖角色/场景/道具/照明参考四种类型
角色支持衍生形象（costume_variant / age_variant / appearance_variant）
资产需求模型（AssetRequirement）从分镜文本中提取的资产需求项
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class Asset(Base):
    """统一资产模型 — 涵盖角色/场景/道具/照明参考四种类型，角色支持衍生形象"""
    __tablename__ = 'assets'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)

    asset_type = Column(String(20), nullable=False)  # character / scene_bg / prop / lighting_ref
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # 视觉属性（JSON，按类型存不同结构）
    # character: {age, age_group, gender, hairstyle, hair_color, body_type, skin_tone, ...}
    # scene_bg: {location, time_of_day, weather, era, mood, ...}
    # prop: {material, size, color, usage, ...}
    visual_attributes = Column(JSON, default=dict)

    # 标签
    tags = Column(JSON, default=list)  # ["主角", "古风", ...]
    era = Column(String(50), nullable=True)  # 时代：古代/现代/未来/...

    # 参考图
    reference_images = Column(JSON, default=list)  # [path1, path2, ...]
    main_reference_image = Column(String(512), nullable=True)
    prompt_description = Column(Text, nullable=True)  # AI 生成用提示词

    # 一致性
    consistency_embedding = Column(Text, nullable=True)

    # ── 角色专用扩展 ──
    visual_anchors = Column(JSON, default=list)    # ["左眼下方小痣", "银色手表左腕"] 视觉锚点
    sora_id = Column(String(255), nullable=True)   # SORA-2 角色 ID
    age_group = Column(String(20), nullable=True)   # 儿童/少年/青年/中年/老年
    gender = Column(String(10), nullable=True)

    # ── 衍生形象扩展 ──
    owner_asset_id = Column(Integer, ForeignKey('assets.id'), nullable=True)  # 衍生角色→基础角色
    variant_type = Column(String(50), nullable=True)  # costume_variant / age_variant / appearance_variant
    variant_description = Column(String(255), nullable=True)  # 衍生描述
    state_variants = Column(JSON, default=list)    # [{"state": "干净", "image": "path"}, ...]

    # ── 通用扩展 ──
    multi_angle_images = Column(JSON, default=list)  # [{"angle": "正面", "path": "xx"}, ...]
    establishing_shot = Column(String(512), nullable=True)  # 建立镜头模板图像（场景用）

    # 状态
    is_global = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    project = relationship("Project", back_populates="assets")
    requirements = relationship("AssetRequirement", back_populates="bound_asset")
    owner_asset = relationship("Asset", remote_side=[id], foreign_keys=[owner_asset_id])
    derived_variants = relationship("Asset", foreign_keys=[owner_asset_id], viewonly=True)

    def __repr__(self):
        return f"<Asset(id={self.id}, type='{self.asset_type}', name='{self.name}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'asset_type': self.asset_type,
            'name': self.name,
            'description': self.description,
            'visual_attributes': self.visual_attributes or {},
            'tags': self.tags or [],
            'era': self.era,
            'reference_images': self.reference_images or [],
            'main_reference_image': self.main_reference_image,
            'prompt_description': self.prompt_description,
            'visual_anchors': self.visual_anchors or [],
            'sora_id': self.sora_id,
            'age_group': self.age_group,
            'gender': self.gender,
            'owner_asset_id': self.owner_asset_id,
            'variant_type': self.variant_type,
            'variant_description': self.variant_description,
            'state_variants': self.state_variants or [],
            'multi_angle_images': self.multi_angle_images or [],
            'establishing_shot': self.establishing_shot,
            'is_global': self.is_global,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class AssetRequirement(Base):
    """资产需求 — 从分镜文本中提取的资产需求项"""
    __tablename__ = 'asset_requirements'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)

    requirement_type = Column(String(20), nullable=False)  # character / scene_bg / prop / lighting_ref
    name = Column(String(255), nullable=False)

    # 从源文本中提取的详细属性（JSON）
    # character: {age, age_group, gender, hairstyle, hair_color, clothing_style,
    #             clothing_color, body_type, role_tag, personality, ...}
    # scene_bg: {location, time, weather, mood, lighting, ...}
    # prop: {material, size, color, usage, owner, ...}
    attributes = Column(JSON, default=dict)

    # 出现的分镜索引列表（去重后记录该需求在哪些分镜中被需要）
    scene_indices = Column(JSON, default=list)  # [0, 3, 7, 12]
    source_text_excerpts = Column(JSON, default=list)  # 源文本中的相关片段

    # 绑定状态
    bound_asset_id = Column(Integer, ForeignKey('assets.id'), nullable=True)
    is_fulfilled = Column(Boolean, default=False)

    # 生成的图片
    generated_image_path = Column(String(512), nullable=True)

    # 卡片位置（画布坐标持久化）
    card_pos_x = Column(Float, nullable=True)
    card_pos_y = Column(Float, nullable=True)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    project = relationship("Project", back_populates="asset_requirements")
    bound_asset = relationship("Asset", back_populates="requirements")

    def __repr__(self):
        return f"<AssetRequirement(id={self.id}, type='{self.requirement_type}', name='{self.name}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'requirement_type': self.requirement_type,
            'name': self.name,
            'attributes': self.attributes or {},
            'scene_indices': self.scene_indices or [],
            'source_text_excerpts': self.source_text_excerpts or [],
            'bound_asset_id': self.bound_asset_id,
            'is_fulfilled': self.is_fulfilled,
            'generated_image_path': self.generated_image_path,
            'card_pos_x': self.card_pos_x,
            'card_pos_y': self.card_pos_y,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
