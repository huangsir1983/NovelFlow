"""
涛割 - 配置模块测试
"""

import pytest
import os
import tempfile


class TestSettings:
    """设置测试"""

    def test_default_settings(self):
        """测试默认设置"""
        from config.settings import AppSettings

        settings = AppSettings()

        assert settings.app_name == "涛割"
        assert settings.app_version == "1.0.0"
        assert settings.generation is not None
        assert settings.ui.canvas_width == 1920
        assert settings.ui.canvas_height == 1080

    def test_api_config(self):
        """测试API配置"""
        from config.settings import APIConfig

        config = APIConfig()

        assert config.deepseek_api_key == ""
        assert config.vidu_api_key == ""
        assert config.deepseek_base_url == "https://api.deepseek.com"
        assert config.comfyui_server_url == "http://localhost:8188"
        assert config.comfyui_enabled == False

    def test_generation_settings(self):
        """测试生成配置"""
        from config.settings import GenerationSettings

        config = GenerationSettings()

        assert config.retry_count == 3
        assert config.max_concurrent_tasks == 3
        assert config.default_scene_duration == 3.5
        assert config.image_first_workflow == True

    def test_credit_settings(self):
        """测试积分配置"""
        from config.settings import CreditSettings

        config = CreditSettings()

        assert config.balance == 1000.0
        assert config.warning_threshold == 0.8
        assert "vidu_image" in config.cost_per_call
        assert config.cost_per_call["vidu_image"] == 5.0

    def test_export_settings(self):
        """测试导出配置"""
        from config.settings import ExportSettings

        config = ExportSettings()

        assert config.video_fps == 30
        assert config.video_width == 1920
        assert config.video_format == "mp4"

    def test_ui_settings(self):
        """测试UI配置"""
        from config.settings import UISettings

        config = UISettings()

        assert config.theme == "dark"
        assert config.language == "zh_CN"
        assert config.auto_save_interval == 20


class TestSettingsManager:
    """设置管理器测试"""

    def test_get_settings_singleton(self):
        """测试设置单例"""
        from config.settings import get_settings

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_get_settings_manager_singleton(self):
        """测试设置管理器单例"""
        from config.settings import get_settings_manager

        manager1 = get_settings_manager()
        manager2 = get_settings_manager()

        assert manager1 is manager2

    def test_settings_has_required_fields(self):
        """测试设置包含必要字段"""
        from config.settings import get_settings

        settings = get_settings()

        assert hasattr(settings, 'app_name')
        assert hasattr(settings, 'credits')
        assert hasattr(settings, 'api')
        assert hasattr(settings, 'ui')
        assert hasattr(settings, 'export')
        assert hasattr(settings, 'generation')


class TestConstants:
    """常量测试"""

    def test_tag_categories(self):
        """测试标签类别"""
        from config.constants import TAG_CATEGORIES

        assert "场景" in TAG_CATEGORIES
        assert "角色" in TAG_CATEGORIES
        assert "道具" in TAG_CATEGORIES

    def test_expression_library(self):
        """测试表情库"""
        from config.constants import EXPRESSION_LIBRARY

        assert "基础" in EXPRESSION_LIBRARY
        assert len(EXPRESSION_LIBRARY) > 0

    def test_camera_motions(self):
        """测试运镜类型"""
        from config.constants import CAMERA_MOTIONS

        assert "静止" in CAMERA_MOTIONS
        assert "推进" in CAMERA_MOTIONS
        assert "拉远" in CAMERA_MOTIONS

    def test_prompt_templates(self):
        """测试Prompt模板"""
        from config.constants import TAG_GENERATION_PROMPT

        assert TAG_GENERATION_PROMPT is not None
        assert len(TAG_GENERATION_PROMPT) > 0


class TestEnums:
    """枚举测试"""

    def test_model_type_enum(self):
        """测试模型类型枚举"""
        from config.settings import ModelType

        assert ModelType.VIDU.value == "vidu"
        assert ModelType.KLING.value == "kling"
        assert ModelType.COMFYUI.value == "comfyui"

    def test_task_status_enum(self):
        """测试任务状态枚举"""
        from config.settings import TaskStatus

        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"

    def test_generation_mode_enum(self):
        """测试生成模式枚举"""
        from config.settings import GenerationMode

        assert GenerationMode.IMAGE_ONLY.value == "image_only"
        assert GenerationMode.IMAGE_TO_VIDEO.value == "image_to_video"
