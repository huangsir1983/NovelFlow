"""
涛割 - PromptGenerator 单元测试
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from services.scene.prompt_generator import PromptGenerator, PromptContext


class TestPromptContext:
    """PromptContext数据类测试"""

    def test_default_values(self):
        ctx = PromptContext()
        assert ctx.scene_tags == []
        assert ctx.character_tags == []
        assert ctx.prop_tags == []
        assert ctx.effect_tags == []
        assert ctx.subtitle_text == ""
        assert ctx.style == "realistic"
        assert ctx.mood == "neutral"

    def test_custom_values(self):
        ctx = PromptContext(
            scene_tags=["森林"],
            character_tags=["勇士"],
            style="anime",
            mood="happy"
        )
        assert ctx.scene_tags == ["森林"]
        assert ctx.character_tags == ["勇士"]
        assert ctx.style == "anime"
        assert ctx.mood == "happy"


class TestImagePromptGeneration:
    """图像Prompt生成测试"""

    def setup_method(self):
        self.generator = PromptGenerator()

    def test_basic_image_prompt(self):
        ctx = PromptContext(
            scene_tags=["森林", "城堡"],
            character_tags=["骑士"],
            subtitle_text="骑士走进了森林",
            style="realistic"
        )
        result = self.generator.generate_image_prompt(ctx)

        assert "prompt" in result
        assert "negative_prompt" in result
        assert len(result["prompt"]) > 0
        assert len(result["negative_prompt"]) > 0

    def test_style_prefix_applied(self):
        for style in ["realistic", "anime", "3d", "cinematic"]:
            ctx = PromptContext(style=style)
            result = self.generator.generate_image_prompt(ctx)
            # 确认Prompt不为空
            assert len(result["prompt"]) > 0

    def test_negative_prompt_varies_by_style(self):
        realistic_ctx = PromptContext(style="realistic")
        anime_ctx = PromptContext(style="anime")

        realistic_result = self.generator.generate_image_prompt(realistic_ctx)
        anime_result = self.generator.generate_image_prompt(anime_ctx)

        # 不同风格的负面提示词应不同
        assert realistic_result["negative_prompt"] != anime_result["negative_prompt"]

    def test_character_descriptions(self):
        ctx = PromptContext(character_tags=["王子"])
        descriptions = ["身穿金色铠甲的年轻王子"]
        result = self.generator.generate_image_prompt(ctx, character_descriptions=descriptions)

        assert len(result["prompt"]) > 0

    def test_empty_context(self):
        ctx = PromptContext()
        result = self.generator.generate_image_prompt(ctx)
        assert "prompt" in result
        assert len(result["prompt"]) > 0


class TestVideoPromptGeneration:
    """视频Prompt生成测试"""

    def setup_method(self):
        self.generator = PromptGenerator()

    def test_basic_video_prompt(self):
        ctx = PromptContext(
            scene_tags=["战场"],
            character_tags=["士兵"],
            subtitle_text="士兵们冲锋陷阵",
        )
        result = self.generator.generate_video_prompt(ctx)

        assert "prompt" in result
        assert "motion_type" in result
        assert "camera_motion" in result
        assert "duration" in result

    def test_auto_motion_type(self):
        ctx = PromptContext(subtitle_text="勇士在奔跑")
        result = self.generator.generate_video_prompt(ctx, motion_type="auto")
        # "跑"应推断为动态
        assert result["motion_type"] == "dynamic"

    def test_subtle_motion(self):
        ctx = PromptContext(subtitle_text="他静静地看着远方")
        result = self.generator.generate_video_prompt(ctx, motion_type="auto")
        assert result["motion_type"] == "subtle"

    def test_custom_camera_motion(self):
        ctx = PromptContext()
        result = self.generator.generate_video_prompt(ctx, camera_motion="zoom_in")
        assert result["camera_motion"] == "zoom_in"


class TestActionInference:
    """动作推断测试"""

    def setup_method(self):
        self.generator = PromptGenerator()

    def test_laugh_action(self):
        result = self.generator._infer_action_from_text("她笑了起来")
        assert "smil" in result.lower()

    def test_cry_action(self):
        result = self.generator._infer_action_from_text("他哭了")
        assert "cry" in result.lower()

    def test_run_action(self):
        result = self.generator._infer_action_from_text("快跑！")
        assert "run" in result.lower()

    def test_empty_text(self):
        result = self.generator._infer_action_from_text("")
        assert result == "Standing naturally"

    def test_no_keyword_match(self):
        result = self.generator._infer_action_from_text("今天天气真好")
        assert result == "Natural pose and expression"


class TestMotionTypeInference:
    """运动类型推断测试"""

    def setup_method(self):
        self.generator = PromptGenerator()

    def test_dynamic_motion(self):
        assert self.generator._infer_motion_type("他在追赶敌人") == "dynamic"
        assert self.generator._infer_motion_type("战斗开始了") == "dynamic"

    def test_moderate_motion(self):
        assert self.generator._infer_motion_type("她慢慢走过来") == "moderate"

    def test_subtle_motion(self):
        assert self.generator._infer_motion_type("他静静地说") == "subtle"

    def test_empty_text(self):
        assert self.generator._infer_motion_type("") == "subtle"


class TestTagAndActionPrompts:
    """标签和动作分析Prompt测试"""

    def setup_method(self):
        self.generator = PromptGenerator()

    def test_tag_analysis_prompt(self):
        result = self.generator.generate_tag_analysis_prompt("骑士骑马穿过森林")
        assert len(result) > 0
        assert "骑士骑马穿过森林" in result

    def test_action_analysis_prompt(self):
        result = self.generator.generate_action_analysis_prompt("他生气地拍了桌子")
        assert len(result) > 0
        assert "他生气地拍了桌子" in result


class TestPlotActionMatching:
    """剧情动作匹配测试"""

    def setup_method(self):
        self.generator = PromptGenerator()

    def test_match_returns_dict_or_none(self):
        result = self.generator.match_action_from_plot("无法匹配的随机内容xyz")
        # 可能返回None或Dict，都是正确的
        assert result is None or isinstance(result, dict)
