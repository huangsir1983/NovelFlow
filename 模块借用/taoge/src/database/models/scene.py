"""
涛割 - 场景数据模型
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class Scene(Base):
    """场景模型"""
    __tablename__ = 'scenes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    act_id = Column(Integer, ForeignKey('acts.id'), nullable=True)  # 所属场次

    # 基础信息
    scene_index = Column(Integer, nullable=False)  # 场景序号
    name = Column(String(255), nullable=True)
    scene_type = Column(String(50), default="normal")  # 画面类型: normal/flashback/transition/montage
    shot_label = Column(String(50), nullable=True)  # 节奏标签

    # 时间信息
    start_time = Column(String(20), nullable=True)  # SRT格式时间
    end_time = Column(String(20), nullable=True)
    start_microseconds = Column(Integer, default=0)
    end_microseconds = Column(Integer, default=0)
    duration = Column(Float, default=0.0)  # 持续时间（秒）

    # 字幕内容
    subtitle_text = Column(Text, nullable=True)
    subtitle_segments = Column(JSON, default=list)  # 存储多条字幕

    # AI标签
    ai_tags = Column(JSON, default=dict)  # {"场景": [], "角色": [], "道具": [], "特效": []}

    # 图像相关
    image_prompt = Column(Text, nullable=True)
    reference_images = Column(JSON, default=list)  # 参考图路径列表
    generated_image_path = Column(String(512), nullable=True)
    composite_image_path = Column(String(512), nullable=True)

    # 首尾帧控制
    start_frame_path = Column(String(512), nullable=True)
    end_frame_path = Column(String(512), nullable=True)
    start_frame_description = Column(Text, nullable=True)
    end_frame_description = Column(Text, nullable=True)

    # 视频相关
    video_prompt = Column(Text, nullable=True)
    generated_video_path = Column(String(512), nullable=True)
    generated_audio_path = Column(String(512), nullable=True)
    camera_motion = Column(String(50), default="静止")  # 运镜类型
    motion_intensity = Column(Float, default=0.5)  # 运动强度 0-1

    # 生成设置
    model_used = Column(String(50), nullable=True)
    generation_params = Column(JSON, default=dict)

    # 结构化提示词
    visual_prompt_struct = Column(JSON, nullable=True)  # {subject, action, environment, camera, style}
    audio_config = Column(JSON, nullable=True)  # {dialogue, narration, sfx}

    # 连贯性辅助数据
    eye_focus = Column(JSON, nullable=True)          # {"x": float, "y": float} 视线落点
    motion_vectors = Column(JSON, nullable=True)      # [{x1,y1,x2,y2,cx1,cy1,cx2,cy2}] 动势引导线
    use_prev_end_frame = Column(Boolean, default=False)  # 是否继承上一镜尾帧
    end_frame_source = Column(String(512), nullable=True)  # 尾帧来源（视频提取/自定义）
    continuity_notes = Column(JSON, nullable=True)    # 连贯性备注

    # ── 增强分镜信息（v1.2） ──
    scene_environment = Column(String(255), nullable=True)  # 场景标识（如 "场景_雪夜山道"）
    shot_size = Column(String(20), nullable=True)           # 景别：特写/近景/中景/全景/远景
    character_actions = Column(JSON, nullable=True)          # [{"character": "林冲", "action": "...", "expression": "...", "dialogue": "..."}]
    atmosphere = Column(String(255), nullable=True)          # 整体氛围
    interaction_desc = Column(Text, nullable=True)           # 角色间互动描述
    is_empty_shot = Column(Boolean, default=False)           # 是否空镜（无人物）

    # 资产绑定（替代旧 SceneCharacter/SceneProp 关联表）
    bound_assets = Column(JSON, default=list)  # [{"asset_id": 1, "type": "character", "variant_type": "costume_variant", ...}]

    # 状态
    status = Column(String(50), default="pending")  # pending, image_generated, video_generated, completed, failed
    error_message = Column(Text, nullable=True)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关联关系
    project = relationship("Project", back_populates="scenes")
    act = relationship("Act", back_populates="scenes")
    scene_characters = relationship("SceneCharacter", back_populates="scene", cascade="all, delete-orphan")
    scene_props = relationship("SceneProp", back_populates="scene", cascade="all, delete-orphan")
    layers = relationship("Layer", back_populates="scene", cascade="all, delete-orphan", order_by="Layer.z_order")

    def __repr__(self):
        return f"<Scene(id={self.id}, index={self.scene_index}, status='{self.status}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'act_id': self.act_id,
            'scene_index': self.scene_index,
            'name': self.name,
            'scene_type': self.scene_type,
            'shot_label': self.shot_label,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration,
            'subtitle_text': self.subtitle_text,
            'subtitle_segments': self.subtitle_segments,
            'ai_tags': self.ai_tags,
            'image_prompt': self.image_prompt,
            'reference_images': self.reference_images,
            'generated_image_path': self.generated_image_path,
            'start_frame_path': self.start_frame_path,
            'end_frame_path': self.end_frame_path,
            'generated_video_path': self.generated_video_path,
            'generated_audio_path': self.generated_audio_path,
            'video_prompt': self.video_prompt,
            'camera_motion': self.camera_motion,
            'motion_intensity': self.motion_intensity,
            'generation_params': self.generation_params,
            'visual_prompt_struct': self.visual_prompt_struct,
            'audio_config': self.audio_config,
            'model_used': self.model_used,
            'status': self.status,
            'eye_focus': self.eye_focus,
            'motion_vectors': self.motion_vectors,
            'use_prev_end_frame': self.use_prev_end_frame,
            'end_frame_source': self.end_frame_source,
            'continuity_notes': self.continuity_notes,
            # v1.2 增强分镜信息
            'scene_environment': self.scene_environment,
            'shot_size': self.shot_size,
            'character_actions': self.character_actions,
            'atmosphere': self.atmosphere,
            'interaction_desc': self.interaction_desc,
            'is_empty_shot': self.is_empty_shot,
            'bound_assets': self.bound_assets,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SceneCharacter(Base):
    """场景-角色关联模型（包含动作表情）"""
    __tablename__ = 'scene_characters'

    id = Column(Integer, primary_key=True, autoincrement=True)
    scene_id = Column(Integer, ForeignKey('scenes.id'), nullable=False)
    character_id = Column(Integer, ForeignKey('characters.id'), nullable=False)

    # 在该场景中的动作表情
    expression = Column(String(50), default="基础")
    left_hand_action = Column(String(50), default="基础")
    right_hand_action = Column(String(50), default="基础")
    body_action = Column(String(100), nullable=True)

    # 位置信息（用于合成）
    position_x = Column(Float, default=0.5)  # 相对位置 0-1
    position_y = Column(Float, default=0.5)
    scale = Column(Float, default=1.0)
    z_order = Column(Integer, default=0)  # 层级顺序

    # 关联
    scene = relationship("Scene", back_populates="scene_characters")
    character = relationship("Character", back_populates="scene_characters")

    def __repr__(self):
        return f"<SceneCharacter(scene_id={self.scene_id}, character_id={self.character_id})>"

    def to_dict(self):
        return {
            'id': self.id,
            'scene_id': self.scene_id,
            'character_id': self.character_id,
            'expression': self.expression,
            'left_hand_action': self.left_hand_action,
            'right_hand_action': self.right_hand_action,
            'body_action': self.body_action,
            'position_x': self.position_x,
            'position_y': self.position_y,
            'scale': self.scale,
            'z_order': self.z_order,
        }
