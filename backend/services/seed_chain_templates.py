"""Seed builtin chain templates into the database on startup."""

import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from models.chain_template import ChainTemplate

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Builtin chain templates — checked by id for idempotent upsert.
# ------------------------------------------------------------------
BUILTIN_TEMPLATES = [
    {
        "id": "tpl_grid9",
        "name": "九宫格生图流",
        "description": "先生成九宫格参考图，从中选取最佳帧，再用九宫格生视频",
        "icon": "⊞",
        "color": "#534AB7",
        "tags": ["精细", "多选", "高质量"],
        "video_provider": "jimeng",
        "estimated_minutes": 8,
        "steps": [
            {
                "id": "s1",
                "name": "生成九宫格参考图",
                "type": "generate-grid9",
                "description": "用同一提示词生成9张候选图，排列为3×3网格",
                "params": {"grid": 3, "style": "cinematic", "seed_variance": True},
                "optional": False,
                "uiHint": "将生成9张候选，你可以框选最满意的一张",
            },
            {
                "id": "s2",
                "name": "用户选帧",
                "type": "user-select-frame",
                "description": "从九宫格中选择最佳帧作为视频首帧",
                "params": {"require_user_confirm": True},
                "optional": False,
                "uiHint": "需要人工确认，系统会暂停等待你点击选择",
                "dependsOn": ["s1"],
            },
            {
                "id": "s3",
                "name": "九宫格生视频",
                "type": "grid9-to-video",
                "description": "将九宫格整体作为参考，生成连贯视频",
                "params": {"use_grid_as_reference": True, "motion_strength": 0.6},
                "optional": False,
                "uiHint": "即梦 API，以九宫格整体作为参考增强一致性",
                "dependsOn": ["s2"],
            },
        ],
    },
    {
        "id": "tpl_asset_compose",
        "name": "资产合成流",
        "description": "从资产库取场景图 → 换角度 → 角色换动作/表情/角度 → 去背景 → 合图 → 溶图优化 → 视频首帧",
        "icon": "◈",
        "color": "#1D9E75",
        "tags": ["资产库", "高一致性", "精细合成"],
        "video_provider": "kling",
        "estimated_minutes": 12,
        "steps": [
            {
                "id": "s1",
                "name": "场景角度变换",
                "type": "scene-angle-transform",
                "description": "从资产库取场景参考图，AI生成指定角度的新视角",
                "params": {"source": "asset-library", "angle_mode": "auto-from-storyboard"},
                "optional": False,
                "uiHint": "自动从分镜文本推断所需镜头角度",
            },
            {
                "id": "s2",
                "name": "角色动作/表情/角度调整",
                "type": "character-pose-adjust",
                "description": "从资产库取角色参考图，按分镜描述调整姿态、表情、角度",
                "params": {"source": "asset-library", "ref_weight": 0.85, "preserve_face": True},
                "optional": False,
                "uiHint": "高参考权重(0.85)保持角色一致性",
            },
            {
                "id": "s3",
                "name": "角色去背景",
                "type": "remove-background",
                "description": "AI精确抠图，保留透明通道",
                "params": {"method": "ai-matting", "edge_refine": True, "feather": 1.5},
                "optional": False,
                "dependsOn": ["s2"],
            },
            {
                "id": "s4",
                "name": "场景+角色合成",
                "type": "composite-layers",
                "description": "将去背角色合入场景，自动匹配光线/阴影/色温",
                "params": {"auto_shadow": True, "color_match": True, "depth_blend": True},
                "optional": False,
                "uiHint": "自动匹配光线色温，使角色融入场景",
                "dependsOn": ["s1", "s3"],
            },
            {
                "id": "s5",
                "name": "溶图优化",
                "type": "blend-refine",
                "description": "对合成边缘进行溶图处理，消除穿帮感",
                "params": {"blend_radius": 8, "frequency_match": True},
                "optional": False,
                "uiHint": "频率匹配技术消除合成边缘",
                "dependsOn": ["s4"],
            },
            {
                "id": "s6",
                "name": "视频首帧确认",
                "type": "set-video-keyframe",
                "description": "将溶图结果设为视频生成的锁定首帧",
                "params": {"lock_first_frame": True},
                "optional": False,
                "dependsOn": ["s5"],
            },
        ],
    },
    {
        "id": "tpl_direct",
        "name": "直出提示词流",
        "description": "最简流程：分镜提示词 → 直接生图 → 生视频。速度最快，适合快速出样",
        "icon": "→",
        "color": "#378ADD",
        "tags": ["快速", "简单", "批量"],
        "video_provider": "jimeng",
        "estimated_minutes": 3,
        "steps": [
            {
                "id": "s1",
                "name": "直接生成图片",
                "type": "generate-image-direct",
                "description": "直接用 imagePrompt 生成图片，无额外合成步骤",
                "params": {"style": "cinematic", "quality": "standard"},
                "optional": False,
            },
            {
                "id": "s2",
                "name": "直接生成视频",
                "type": "generate-video-direct",
                "description": "图片直接作为首帧生成视频",
                "params": {"provider": "jimeng", "duration": 5},
                "optional": False,
                "dependsOn": ["s1"],
            },
        ],
    },
    {
        "id": "tpl_emotion_portrait",
        "name": "情感特写流",
        "description": "专为情感/内心戏设计：柔焦背景 + 面部特写 + 慢速推镜视频",
        "icon": "◉",
        "color": "#D4537E",
        "tags": ["情感", "特写", "慢镜"],
        "video_provider": "kling",
        "estimated_minutes": 10,
        "steps": [
            {
                "id": "s1",
                "name": "生成柔焦背景",
                "type": "generate-background",
                "description": "大光圈柔焦虚化背景，突出主体",
                "params": {"bokeh": True, "abstraction": 0.4, "style": "emotional"},
                "optional": False,
            },
            {
                "id": "s2",
                "name": "生成面部特写",
                "type": "character-pose-adjust",
                "description": "特写角度，重点刻画表情细节",
                "params": {"angle": "close-up", "expression_intensity": 0.85, "preserve_face": True},
                "optional": False,
            },
            {
                "id": "s3",
                "name": "去背合成",
                "type": "remove-background",
                "description": "软边缘镂空，与柔焦背景自然融合",
                "params": {"method": "ai-matting", "edge_refine": True, "feather": 3},
                "optional": False,
                "dependsOn": ["s2"],
            },
            {
                "id": "s4",
                "name": "情感滤镜",
                "type": "apply-filter",
                "description": "根据情绪施加色调：悲伤→冷蓝/温馨→暖金",
                "params": {"filter": "emotion-auto", "halation": 0.12},
                "optional": False,
                "dependsOn": ["s1", "s3"],
            },
            {
                "id": "s5",
                "name": "慢速推镜视频",
                "type": "generate-video-direct",
                "description": "可灵慢速推进，配合情感节奏",
                "params": {"provider": "kling", "motion": "slow-push", "duration": 6},
                "optional": False,
                "dependsOn": ["s4"],
            },
        ],
    },
]


def seed_chain_templates(db: Session) -> None:
    """Insert or update builtin chain templates. Idempotent."""
    for cfg in BUILTIN_TEMPLATES:
        existing = db.query(ChainTemplate).filter(ChainTemplate.id == cfg["id"]).first()
        if existing:
            changed = False
            for field in ("name", "description", "icon", "color", "tags", "steps",
                          "video_provider", "estimated_minutes"):
                db_val = getattr(existing, field)
                cfg_val = cfg[field]
                if db_val != cfg_val:
                    setattr(existing, field, cfg_val)
                    changed = True
            if changed:
                existing.version = (existing.version or 1) + 1
                logger.info("Updated builtin chain template: %s", cfg["name"])
            else:
                logger.debug("Chain template '%s' already up-to-date.", cfg["name"])
            continue

        template = ChainTemplate(
            id=cfg["id"],
            project_id=None,
            name=cfg["name"],
            description=cfg["description"],
            icon=cfg["icon"],
            color=cfg["color"],
            tags=cfg["tags"],
            is_builtin=True,
            steps=cfg["steps"],
            video_provider=cfg["video_provider"],
            estimated_minutes=cfg["estimated_minutes"],
            version=1,
            share_mode="global",
        )
        db.add(template)
        logger.info("Seeded builtin chain template: %s", cfg["name"])

    db.commit()
