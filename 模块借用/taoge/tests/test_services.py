"""
涛割 - 服务层测试
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock


class TestSceneProcessor:
    """场景处理器测试"""

    def test_parse_srt(self):
        """测试SRT内容解析"""
        from services.scene.processor import SceneProcessor

        srt_content = """1
00:00:00,000 --> 00:00:02,500
第一条字幕

2
00:00:02,500 --> 00:00:05,000
第二条字幕

3
00:00:05,000 --> 00:00:08,000
第三条字幕
"""
        processor = SceneProcessor()
        segments = processor.parse_srt(srt_content)

        assert len(segments) == 3
        assert segments[0].text == "第一条字幕"
        assert segments[0].index == 1
        assert segments[1].start == "00:00:02,500"
        assert segments[2].end == "00:00:08,000"

    def test_group_segments_by_duration(self):
        """测试按时长分组"""
        from services.scene.processor import SceneProcessor, SubtitleSegment

        segments = [
            SubtitleSegment(1, "00:00:00,000", "00:00:02,000", "字幕1", 0, 2000000),
            SubtitleSegment(2, "00:00:02,000", "00:00:04,000", "字幕2", 2000000, 4000000),
            SubtitleSegment(3, "00:00:04,000", "00:00:06,000", "字幕3", 4000000, 6000000),
            SubtitleSegment(4, "00:00:10,000", "00:00:12,000", "字幕4", 10000000, 12000000),
        ]

        processor = SceneProcessor(default_scene_duration=3.5, max_scene_duration=8.0)
        groups = processor.group_segments(segments, strategy="duration")

        assert len(groups) >= 1
        assert groups[0].full_text is not None

    def test_srt_time_to_microseconds(self):
        """测试时间转微秒"""
        from services.scene.processor import SceneProcessor

        # 测试基本转换
        result = SceneProcessor.srt_time_to_microseconds("00:00:01,000")
        assert result == 1000000

        result = SceneProcessor.srt_time_to_microseconds("00:01:00,000")
        assert result == 60000000

        result = SceneProcessor.srt_time_to_microseconds("01:00:00,000")
        assert result == 3600000000

    def test_microseconds_to_srt_time(self):
        """测试微秒转时间"""
        from services.scene.processor import SceneProcessor

        result = SceneProcessor.microseconds_to_srt_time(1000000)
        assert result == "00:00:01,000"

        result = SceneProcessor.microseconds_to_srt_time(61500000)
        assert result == "00:01:01,500"

    def test_subtitle_segment_duration(self):
        """测试字幕段落时长计算"""
        from services.scene.processor import SubtitleSegment

        segment = SubtitleSegment(
            index=1,
            start="00:00:00,000",
            end="00:00:05,000",
            text="测试",
            start_microseconds=0,
            end_microseconds=5000000
        )

        assert segment.duration == 5.0

    def test_scene_group_properties(self):
        """测试场景分组属性"""
        from services.scene.processor import SceneGroup, SubtitleSegment

        segments = [
            SubtitleSegment(1, "00:00:00,000", "00:00:02,000", "字幕1", 0, 2000000),
            SubtitleSegment(2, "00:00:02,000", "00:00:05,000", "字幕2", 2000000, 5000000),
        ]

        group = SceneGroup(segments=segments)

        assert group.start_time == "00:00:00,000"
        assert group.end_time == "00:00:05,000"
        assert group.duration == 5.0
        assert "字幕1" in group.full_text
        assert "字幕2" in group.full_text


class TestBaseProvider:
    """基础Provider测试"""

    def test_provider_factory_register(self):
        """测试Provider工厂注册"""
        from services.generation.base_provider import ProviderFactory, BaseProvider, ProviderType

        class MockProvider(BaseProvider):
            @property
            def provider_name(self):
                return "mock"

            @property
            def provider_type(self):
                return ProviderType.CLOSED_SOURCE

            @property
            def supported_features(self):
                return {"image_generation": True}

            @property
            def cost_per_operation(self):
                return {"image": 1.0}

            def validate_credentials(self):
                return True

            async def generate_image(self, request):
                pass

            async def generate_video(self, request):
                pass

            async def image_to_video(self, request):
                pass

        ProviderFactory.register("mock_test", MockProvider)
        assert "mock_test" in ProviderFactory.get_available_providers()

    def test_generation_request_defaults(self):
        """测试生成请求默认值"""
        from services.generation.base_provider import ImageGenerationRequest

        request = ImageGenerationRequest(prompt="test prompt")

        assert request.prompt == "test prompt"
        assert request.width == 1920
        assert request.height == 1080
        assert request.negative_prompt == ""
        assert request.num_images == 1

    def test_video_generation_request(self):
        """测试视频生成请求"""
        from services.generation.base_provider import VideoGenerationRequest

        request = VideoGenerationRequest(
            prompt="test video",
            duration=8.0,
            fps=30,
            camera_motion="push_in",
            source_image="/path/to/image.png"
        )

        assert request.duration == 8.0
        assert request.fps == 30
        assert request.camera_motion == "push_in"
        assert request.source_image == "/path/to/image.png"

    def test_generation_result(self):
        """测试生成结果"""
        from services.generation.base_provider import GenerationResult

        result = GenerationResult(
            success=True,
            result_path="/output/image.png",
            task_id="task_123",
            credits_used=5.0
        )

        assert result.success == True
        assert result.result_path == "/output/image.png"
        assert result.credits_used == 5.0


class TestComfyUIProvider:
    """ComfyUI Provider测试"""

    def test_provider_properties(self):
        """测试Provider属性"""
        from services.generation.open_source.comfyui_provider import ComfyUIProvider
        from services.generation.base_provider import ProviderType

        provider = ComfyUIProvider(base_url="http://localhost:8188")

        assert provider.provider_name == "ComfyUI"
        assert provider.provider_type == ProviderType.OPEN_SOURCE
        assert provider.supported_features["image_generation"] == True
        assert provider.cost_per_operation["image"] == 0.0

    def test_build_image_workflow(self):
        """测试构建图片工作流"""
        from services.generation.open_source.comfyui_provider import ComfyUIProvider
        from services.generation.base_provider import ImageGenerationRequest

        provider = ComfyUIProvider()
        request = ImageGenerationRequest(
            prompt="a beautiful landscape",
            negative_prompt="ugly, blurry",
            width=1024,
            height=768,
            seed=12345
        )

        workflow = provider._build_image_workflow(request)

        assert workflow["6"]["inputs"]["text"] == "a beautiful landscape"
        assert workflow["7"]["inputs"]["text"] == "ugly, blurry"
        assert workflow["5"]["inputs"]["width"] == 1024
        assert workflow["5"]["inputs"]["height"] == 768
        assert workflow["3"]["inputs"]["seed"] == 12345

    @pytest.mark.asyncio
    async def test_check_server_status_offline(self):
        """测试服务器离线状态检查"""
        from services.generation.open_source.comfyui_provider import ComfyUIProvider

        provider = ComfyUIProvider(base_url="http://localhost:9999")
        status = await provider.check_server_status()

        assert status["online"] == False

    def test_validate_credentials_offline(self):
        """测试离线时凭证验证"""
        from services.generation.open_source.comfyui_provider import ComfyUIProvider

        provider = ComfyUIProvider(base_url="http://localhost:9999")
        result = provider.validate_credentials()

        assert result == False


class TestModelRouter:
    """模型路由测试"""

    def test_get_model_router_singleton(self):
        """测试模型路由单例"""
        from services.generation.model_router import get_model_router

        router1 = get_model_router()
        router2 = get_model_router()

        assert router1 is router2

    def test_scene_type_enum(self):
        """测试场景类型枚举"""
        from services.generation.model_router import SceneType

        assert SceneType.DIALOGUE is not None
        assert SceneType.ACTION is not None

    def test_quality_level_enum(self):
        """测试质量级别枚举"""
        from services.generation.model_router import QualityLevel

        assert QualityLevel.DRAFT is not None
        assert QualityLevel.STANDARD is not None
        assert QualityLevel.HIGH is not None
        assert QualityLevel.PREMIUM is not None
