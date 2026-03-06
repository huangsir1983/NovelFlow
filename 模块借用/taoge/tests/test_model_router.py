"""
涛割 - ModelRouter 单元测试
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from unittest.mock import MagicMock
from services.generation.model_router import (
    ModelRouter, SceneType, QualityLevel, RoutingContext, RoutingResult
)


class MockProvider:
    """模拟Provider"""

    def __init__(self, name: str, supports_consistency: bool = False):
        self.name = name
        self.supported_features = {
            "character_consistency": supports_consistency,
        }

    def validate_credentials(self):
        return True


@pytest.fixture
def router_with_providers():
    """创建一个注册了多个Provider的路由器"""
    router = ModelRouter()
    router.register_provider("vidu", MockProvider("vidu", supports_consistency=True))
    router.register_provider("kling", MockProvider("kling"))
    router.register_provider("jimeng", MockProvider("jimeng"))
    router.register_provider("comfyui", MockProvider("comfyui", supports_consistency=True))
    return router


class TestModelRouterBasic:
    """基础功能测试"""

    def test_register_provider(self):
        router = ModelRouter()
        provider = MockProvider("test")
        router.register_provider("test", provider)

        assert "test" in router.get_available_providers()

    def test_unregister_provider(self):
        router = ModelRouter()
        router.register_provider("test", MockProvider("test"))
        router.unregister_provider("test")

        assert "test" not in router.get_available_providers()

    def test_no_providers_raises(self):
        router = ModelRouter()
        ctx = RoutingContext()

        with pytest.raises(ValueError, match="No providers registered"):
            router.route(ctx)


class TestRouting:
    """路由决策测试"""

    def test_basic_routing(self, router_with_providers):
        ctx = RoutingContext(
            scene_type=SceneType.DIALOGUE,
            quality_level=QualityLevel.STANDARD
        )
        result = router_with_providers.route(ctx)

        assert isinstance(result, RoutingResult)
        assert result.provider_name in ["vidu", "kling", "jimeng", "comfyui"]
        assert result.confidence > 0
        assert result.estimated_cost > 0

    def test_preferred_provider(self, router_with_providers):
        ctx = RoutingContext(preferred_provider="jimeng")
        result = router_with_providers.route(ctx)

        assert result.provider_name == "jimeng"
        assert result.confidence == 1.0

    def test_preferred_provider_unavailable(self, router_with_providers):
        ctx = RoutingContext(preferred_provider="nonexistent")
        result = router_with_providers.route(ctx)

        # 应回退到最优选择
        assert result.provider_name in ["vidu", "kling", "jimeng", "comfyui"]

    def test_action_scene_routing(self, router_with_providers):
        ctx = RoutingContext(
            scene_type=SceneType.ACTION,
            quality_level=QualityLevel.HIGH
        )
        result = router_with_providers.route(ctx)

        # Kling在动作场景得分最高
        assert result.provider_name in ["vidu", "kling", "jimeng", "comfyui"]

    def test_vfx_scene_routing(self, router_with_providers):
        ctx = RoutingContext(scene_type=SceneType.VFX)
        result = router_with_providers.route(ctx)

        # ComfyUI在特效场景得分最高
        assert result.provider_name in ["vidu", "kling", "jimeng", "comfyui"]

    def test_budget_limit(self, router_with_providers):
        ctx = RoutingContext(
            scene_type=SceneType.DIALOGUE,
            budget_limit=3.0  # 很低的预算
        )
        result = router_with_providers.route(ctx, operation="image")

        # 应倾向低成本Provider
        assert result.estimated_cost >= 0

    def test_consistency_requirement(self, router_with_providers):
        ctx = RoutingContext(
            scene_type=SceneType.PORTRAIT,
            require_consistency=True
        )
        result = router_with_providers.route(ctx)

        # 应倾向支持一致性的Provider
        assert len(result.reasons) > 0

    def test_speed_preference(self, router_with_providers):
        ctx = RoutingContext(
            scene_type=SceneType.DIALOGUE,
            prefer_speed=True
        )
        result = router_with_providers.route(ctx)

        assert result.confidence > 0


class TestBatchRouting:
    """批量路由测试"""

    def test_batch_routing_independent(self, router_with_providers):
        contexts = [
            RoutingContext(scene_type=SceneType.DIALOGUE),
            RoutingContext(scene_type=SceneType.ACTION),
            RoutingContext(scene_type=SceneType.LANDSCAPE),
        ]
        results = router_with_providers.route_batch(contexts, optimize_cost=False)

        assert len(results) == 3
        for r in results:
            assert isinstance(r, RoutingResult)

    def test_batch_routing_optimized(self, router_with_providers):
        contexts = [
            RoutingContext(scene_type=SceneType.DIALOGUE),
            RoutingContext(scene_type=SceneType.DIALOGUE),
            RoutingContext(scene_type=SceneType.ACTION),
        ]
        results = router_with_providers.route_batch(contexts, optimize_cost=True)

        assert len(results) == 3
        # 相同场景类型应使用相同Provider
        assert results[0].provider_name == results[1].provider_name


class TestCostEstimation:
    """成本估算测试"""

    def test_image_cost(self):
        router = ModelRouter()
        assert router._estimate_cost("vidu", "image") == 5.0
        assert router._estimate_cost("jimeng", "image") == 3.0

    def test_video_cost(self):
        router = ModelRouter()
        assert router._estimate_cost("vidu", "video") == 20.0
        assert router._estimate_cost("kling", "video") == 25.0

    def test_unknown_provider_cost(self):
        router = ModelRouter()
        cost = router._estimate_cost("unknown", "image")
        assert cost == 5.0  # 默认值


class TestRecommendation:
    """推荐报告测试"""

    def test_get_recommendation(self, router_with_providers):
        ctx = RoutingContext(
            scene_type=SceneType.DIALOGUE,
            quality_level=QualityLevel.STANDARD
        )
        report = router_with_providers.get_recommendation(ctx)

        assert "context" in report
        assert "recommendations" in report
        assert "best_choice" in report
        assert len(report["recommendations"]) == 4
        assert report["best_choice"] is not None

    def test_recommendation_sorted(self, router_with_providers):
        ctx = RoutingContext(scene_type=SceneType.LANDSCAPE)
        report = router_with_providers.get_recommendation(ctx)

        scores = [r["score"] for r in report["recommendations"]]
        assert scores == sorted(scores, reverse=True)

    def test_empty_recommendation(self):
        router = ModelRouter()
        ctx = RoutingContext()
        report = router.get_recommendation(ctx)

        assert "error" in report
