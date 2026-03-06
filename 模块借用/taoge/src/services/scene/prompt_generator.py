"""
涛割 - Prompt生成器
负责生成图像和视频的Prompt
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from config.constants import (
    TAG_GENERATION_PROMPT,
    ACTION_ANALYSIS_PROMPT,
    IMAGE_GENERATION_PROMPT,
    VIDEO_GENERATION_PROMPT,
    EXPRESSION_LIBRARY,
    LEFT_HAND_ACTIONS,
    RIGHT_HAND_ACTIONS,
    BOTH_HANDS_ACTIONS,
    PLOT_ACTION_MAPPING,
)


@dataclass
class PromptContext:
    """Prompt生成上下文"""
    scene_tags: List[str] = None
    character_tags: List[str] = None
    prop_tags: List[str] = None
    effect_tags: List[str] = None
    subtitle_text: str = ""
    style: str = "realistic"
    mood: str = "neutral"
    lighting: str = "natural"
    camera_angle: str = "medium shot"

    def __post_init__(self):
        self.scene_tags = self.scene_tags or []
        self.character_tags = self.character_tags or []
        self.prop_tags = self.prop_tags or []
        self.effect_tags = self.effect_tags or []


class PromptGenerator:
    """
    Prompt生成器
    根据场景信息生成高质量的图像/视频Prompt
    """

    # 风格前缀映射
    STYLE_PREFIXES = {
        "realistic": "Photorealistic, highly detailed, 8K resolution,",
        "anime": "Anime style, vibrant colors, clean lines,",
        "3d": "3D rendered, Pixar style, high quality CGI,",
        "illustration": "Digital illustration, artistic, stylized,",
        "cinematic": "Cinematic, movie quality, dramatic lighting,",
        "sketch": "Pencil sketch style, hand-drawn, artistic,",
    }

    # 情绪到光线/氛围的映射
    MOOD_LIGHTING = {
        "happy": ("warm golden light", "cheerful and bright"),
        "sad": ("soft blue light", "melancholic and somber"),
        "tense": ("harsh shadows", "suspenseful and dramatic"),
        "romantic": ("soft pink sunset", "warm and intimate"),
        "mysterious": ("dim atmospheric light", "enigmatic and intriguing"),
        "neutral": ("natural daylight", "balanced and clear"),
        "angry": ("red-tinted harsh light", "intense and aggressive"),
        "peaceful": ("soft diffused light", "calm and serene"),
    }

    def __init__(self):
        self.default_negative_prompt = (
            "blurry, low quality, distorted, deformed, ugly, "
            "bad anatomy, bad proportions, extra limbs, "
            "watermark, signature, text"
        )

    def generate_image_prompt(
        self,
        context: PromptContext,
        character_descriptions: List[str] = None,
        additional_notes: str = ""
    ) -> Dict[str, str]:
        """
        生成图像Prompt

        Args:
            context: Prompt上下文
            character_descriptions: 角色描述列表
            additional_notes: 额外说明

        Returns:
            Dict包含prompt和negative_prompt
        """
        # 获取风格前缀
        style_prefix = self.STYLE_PREFIXES.get(
            context.style,
            self.STYLE_PREFIXES["realistic"]
        )

        # 获取光线和氛围
        lighting, mood_desc = self.MOOD_LIGHTING.get(
            context.mood,
            self.MOOD_LIGHTING["neutral"]
        )

        # 构建场景描述
        scene_desc = self._build_scene_description(context)

        # 构建角色描述
        char_desc = self._build_character_description(
            context.character_tags,
            character_descriptions
        )

        # 构建动作描述（从字幕推断）
        action_desc = self._infer_action_from_text(context.subtitle_text)

        # 组装完整Prompt
        prompt = IMAGE_GENERATION_PROMPT.format(
            style_prefix=style_prefix,
            scene_description=scene_desc,
            character_description=char_desc,
            action_description=action_desc,
            lighting=lighting,
            mood=mood_desc,
            additional_notes=additional_notes
        ).strip()

        # 构建负面Prompt
        negative_prompt = self._build_negative_prompt(context)

        return {
            "prompt": prompt,
            "negative_prompt": negative_prompt
        }

    def generate_video_prompt(
        self,
        context: PromptContext,
        motion_type: str = "subtle",
        camera_motion: str = "static",
        duration: float = 4.0,
        start_frame_desc: str = "",
        end_frame_desc: str = ""
    ) -> Dict[str, str]:
        """
        生成视频Prompt

        Args:
            context: Prompt上下文
            motion_type: 运动类型
            camera_motion: 镜头运动
            duration: 持续时间
            start_frame_desc: 起始帧描述
            end_frame_desc: 结束帧描述

        Returns:
            Dict包含prompt和相关参数
        """
        # 构建图像描述
        image_desc = self._build_scene_description(context)
        if context.character_tags:
            image_desc += f" Characters: {', '.join(context.character_tags)}."

        # 推断运动类型
        if not motion_type or motion_type == "auto":
            motion_type = self._infer_motion_type(context.subtitle_text)

        # 组装视频Prompt
        prompt = VIDEO_GENERATION_PROMPT.format(
            image_description=image_desc,
            motion_type=motion_type,
            camera_motion=camera_motion,
            duration=duration,
            start_frame_description=start_frame_desc or "Initial scene setup",
            end_frame_description=end_frame_desc or "Scene conclusion"
        ).strip()

        return {
            "prompt": prompt,
            "motion_type": motion_type,
            "camera_motion": camera_motion,
            "duration": duration
        }

    def generate_tag_analysis_prompt(self, subtitle_text: str) -> str:
        """生成标签分析Prompt（用于AI标签生成）"""
        return TAG_GENERATION_PROMPT.format(subtitle_text=subtitle_text)

    def generate_action_analysis_prompt(self, dialogue_text: str) -> str:
        """生成动作分析Prompt（用于AI动作推荐）"""
        return ACTION_ANALYSIS_PROMPT.format(
            dialogue_text=dialogue_text,
            expressions=", ".join(EXPRESSION_LIBRARY),
            left_actions=", ".join(LEFT_HAND_ACTIONS),
            right_actions=", ".join(RIGHT_HAND_ACTIONS),
            both_actions=", ".join(BOTH_HANDS_ACTIONS)
        )

    def _build_scene_description(self, context: PromptContext) -> str:
        """构建场景描述"""
        parts = []

        if context.scene_tags:
            parts.append(f"Scene: {', '.join(context.scene_tags)}")

        if context.prop_tags:
            parts.append(f"Props: {', '.join(context.prop_tags)}")

        if context.effect_tags:
            parts.append(f"Effects: {', '.join(context.effect_tags)}")

        if context.camera_angle:
            parts.append(f"Camera: {context.camera_angle}")

        return ". ".join(parts) if parts else "A detailed scene"

    def _build_character_description(
        self,
        character_tags: List[str],
        character_descriptions: List[str] = None
    ) -> str:
        """构建角色描述"""
        if character_descriptions:
            return "; ".join(character_descriptions)
        elif character_tags:
            return f"Characters present: {', '.join(character_tags)}"
        return "No specific characters"

    def _build_negative_prompt(self, context: PromptContext) -> str:
        """构建负面Prompt"""
        negative_parts = [self.default_negative_prompt]

        # 根据风格添加特定的负面词
        if context.style == "realistic":
            negative_parts.append("cartoon, anime, illustration")
        elif context.style == "anime":
            negative_parts.append("photorealistic, 3d render")

        return ", ".join(negative_parts)

    def _infer_action_from_text(self, text: str) -> str:
        """从文本推断动作描述"""
        if not text:
            return "Standing naturally"

        text_lower = text.lower()

        # 简单的关键词匹配
        action_keywords = {
            "笑": "smiling happily",
            "哭": "crying with tears",
            "跑": "running quickly",
            "走": "walking calmly",
            "坐": "sitting down",
            "站": "standing up",
            "说": "speaking expressively",
            "看": "looking attentively",
            "想": "thinking deeply",
            "生气": "showing anger",
            "惊讶": "looking surprised",
            "害怕": "showing fear",
        }

        for keyword, action in action_keywords.items():
            if keyword in text_lower:
                return action

        return "Natural pose and expression"

    def _infer_motion_type(self, text: str) -> str:
        """从文本推断运动类型"""
        if not text:
            return "subtle"

        text_lower = text.lower()

        # 动作强度关键词
        intense_keywords = ["跑", "打", "跳", "冲", "追", "逃", "战斗", "爆炸"]
        moderate_keywords = ["走", "移动", "转身", "挥手", "点头"]
        subtle_keywords = ["说", "想", "看", "听", "等待", "站"]

        for keyword in intense_keywords:
            if keyword in text_lower:
                return "dynamic"

        for keyword in moderate_keywords:
            if keyword in text_lower:
                return "moderate"

        return "subtle"

    def match_action_from_plot(self, plot_description: str) -> Optional[Dict[str, str]]:
        """
        根据剧情描述匹配预设动作

        Args:
            plot_description: 剧情描述

        Returns:
            匹配的动作字典，如 {"left_hand": "摸头", "right_hand": "指点"}
        """
        # 直接匹配
        if plot_description in PLOT_ACTION_MAPPING:
            return PLOT_ACTION_MAPPING[plot_description]

        # 模糊匹配（简单实现）
        plot_lower = plot_description.lower()
        for key, value in PLOT_ACTION_MAPPING.items():
            if any(word in plot_lower for word in key.split()):
                return value

        return None
