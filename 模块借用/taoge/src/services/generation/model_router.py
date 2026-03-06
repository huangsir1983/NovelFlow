"""
涛割 - 智能模型路由器
根据场景类型、成本、质量需求智能选择最优模型
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

from .base_provider import BaseProvider, ProviderFactory


class SceneType(Enum):
    """场景类型"""
    ACTION = "action"  # 动作戏
    DIALOGUE = "dialogue"  # 对话
    LANDSCAPE = "landscape"  # 风景
    PORTRAIT = "portrait"  # 人像特写
    CROWD = "crowd"  # 群戏
    VFX = "vfx"  # 特效场景


class QualityLevel(Enum):
    """质量等级"""
    DRAFT = "draft"  # 草稿/预览
    STANDARD = "standard"  # 标准
    HIGH = "high"  # 高质量
    PREMIUM = "premium"  # 精品


@dataclass
class RoutingContext:
    """路由上下文"""
    scene_type: SceneType = SceneType.DIALOGUE
    quality_level: QualityLevel = QualityLevel.STANDARD
    budget_limit: float = float('inf')  # 预算限制
    require_consistency: bool = False  # 是否需要角色一致性
    require_first_last_frame: bool = False  # 是否需要首尾帧控制
    prefer_speed: bool = False  # 是否优先速度
    preferred_provider: Optional[str] = None  # 用户偏好的Provider


@dataclass
class RoutingResult:
    """路由结果"""
    provider_name: str
    provider: BaseProvider
    confidence: float  # 推荐置信度 0-1
    estimated_cost: float
    reasons: List[str]  # 选择理由


class ModelRouter:
    """
    智能模型路由器
    实现多模型智能路由策略
    """

    # 模型能力评分矩阵（用于路由决策）
    MODEL_SCORES = {
        "vidu": {
            SceneType.ACTION: 0.85,
            SceneType.DIALOGUE: 0.90,
            SceneType.LANDSCAPE: 0.80,
            SceneType.PORTRAIT: 0.85,
            SceneType.CROWD: 0.70,
            SceneType.VFX: 0.75,
            "quality": 0.85,
            "speed": 0.80,
            "consistency": 0.90,
            "cost_efficiency": 0.75,
        },
        "kling": {
            SceneType.ACTION: 0.90,
            SceneType.DIALOGUE: 0.85,
            SceneType.LANDSCAPE: 0.85,
            SceneType.PORTRAIT: 0.80,
            SceneType.CROWD: 0.80,
            SceneType.VFX: 0.85,
            "quality": 0.90,
            "speed": 0.70,
            "consistency": 0.85,
            "cost_efficiency": 0.65,
        },
        "jimeng": {
            SceneType.ACTION: 0.70,
            SceneType.DIALOGUE: 0.80,
            SceneType.LANDSCAPE: 0.85,
            SceneType.PORTRAIT: 0.75,
            SceneType.CROWD: 0.65,
            SceneType.VFX: 0.70,
            "quality": 0.75,
            "speed": 0.90,
            "consistency": 0.60,
            "cost_efficiency": 0.90,
        },
        "comfyui": {
            SceneType.ACTION: 0.80,
            SceneType.DIALOGUE: 0.85,
            SceneType.LANDSCAPE: 0.90,
            SceneType.PORTRAIT: 0.85,
            SceneType.CROWD: 0.85,
            SceneType.VFX: 0.95,
            "quality": 0.85,
            "speed": 0.60,
            "consistency": 0.95,
            "cost_efficiency": 0.95,
        },
    }

    # 默认成本配置
    MODEL_COSTS = {
        "vidu": {"image": 5.0, "video": 20.0},
        "kling": {"image": 4.0, "video": 25.0},
        "jimeng": {"image": 3.0, "video": 15.0},
        "comfyui": {"image": 2.0, "video": 10.0},
    }

    def __init__(self):
        self._providers: Dict[str, BaseProvider] = {}

    def register_provider(self, name: str, provider: BaseProvider):
        """注册可用的Provider"""
        self._providers[name] = provider

    def unregister_provider(self, name: str):
        """注销Provider"""
        if name in self._providers:
            del self._providers[name]

    def get_available_providers(self) -> List[str]:
        """获取当前可用的Provider列表"""
        return list(self._providers.keys())

    def route(self, context: RoutingContext, operation: str = "video") -> RoutingResult:
        """
        根据上下文智能路由到最优Provider

        Args:
            context: 路由上下文
            operation: 操作类型 ("image" 或 "video")

        Returns:
            RoutingResult: 路由结果
        """
        if not self._providers:
            raise ValueError("No providers registered")

        # 如果用户指定了偏好Provider且可用
        if context.preferred_provider and context.preferred_provider in self._providers:
            provider = self._providers[context.preferred_provider]
            cost = self._estimate_cost(context.preferred_provider, operation)
            return RoutingResult(
                provider_name=context.preferred_provider,
                provider=provider,
                confidence=1.0,
                estimated_cost=cost,
                reasons=["用户指定偏好"]
            )

        # 计算每个Provider的综合得分
        scores: List[Tuple[str, float, float, List[str]]] = []

        for name, provider in self._providers.items():
            score, cost, reasons = self._calculate_score(name, provider, context, operation)
            scores.append((name, score, cost, reasons))

        # 按得分降序排序
        scores.sort(key=lambda x: x[1], reverse=True)

        # 选择最优结果
        best_name, best_score, best_cost, best_reasons = scores[0]

        return RoutingResult(
            provider_name=best_name,
            provider=self._providers[best_name],
            confidence=best_score,
            estimated_cost=best_cost,
            reasons=best_reasons
        )

    def _calculate_score(
        self,
        name: str,
        provider: BaseProvider,
        context: RoutingContext,
        operation: str
    ) -> Tuple[float, float, List[str]]:
        """计算Provider的综合得分"""
        scores = self.MODEL_SCORES.get(name, {})
        reasons = []
        total_score = 0.0
        weight_sum = 0.0

        # 1. 场景类型得分 (权重: 0.3)
        scene_score = scores.get(context.scene_type, 0.5)
        total_score += scene_score * 0.3
        weight_sum += 0.3
        if scene_score >= 0.85:
            reasons.append(f"擅长{context.scene_type.value}场景")

        # 2. 质量得分 (权重根据质量等级调整)
        quality_score = scores.get("quality", 0.5)
        quality_weight = {
            QualityLevel.DRAFT: 0.1,
            QualityLevel.STANDARD: 0.2,
            QualityLevel.HIGH: 0.3,
            QualityLevel.PREMIUM: 0.4,
        }.get(context.quality_level, 0.2)
        total_score += quality_score * quality_weight
        weight_sum += quality_weight

        # 3. 速度得分 (如果优先速度)
        if context.prefer_speed:
            speed_score = scores.get("speed", 0.5)
            total_score += speed_score * 0.2
            weight_sum += 0.2
            if speed_score >= 0.85:
                reasons.append("生成速度快")

        # 4. 一致性得分 (如果需要角色一致性)
        if context.require_consistency:
            consistency_score = scores.get("consistency", 0.5)
            features = provider.supported_features if hasattr(provider, 'supported_features') else {}
            if not features.get("character_consistency", False):
                consistency_score *= 0.5  # 不支持一致性时降低得分
            total_score += consistency_score * 0.25
            weight_sum += 0.25
            if consistency_score >= 0.85:
                reasons.append("角色一致性好")

        # 5. 成本效益得分
        cost = self._estimate_cost(name, operation)
        if cost <= context.budget_limit:
            cost_score = scores.get("cost_efficiency", 0.5)
            total_score += cost_score * 0.15
            weight_sum += 0.15
            if cost_score >= 0.85:
                reasons.append("性价比高")
        else:
            # 超出预算，大幅降低得分
            total_score *= 0.3
            reasons.append("超出预算限制")

        # 归一化得分
        final_score = total_score / weight_sum if weight_sum > 0 else 0.5

        return final_score, cost, reasons

    def _estimate_cost(self, provider_name: str, operation: str) -> float:
        """估算操作成本"""
        costs = self.MODEL_COSTS.get(provider_name, {"image": 5.0, "video": 20.0})
        return costs.get(operation, 10.0)

    def route_batch(
        self,
        contexts: List[RoutingContext],
        operation: str = "video",
        optimize_cost: bool = True
    ) -> List[RoutingResult]:
        """
        批量路由多个场景

        Args:
            contexts: 路由上下文列表
            operation: 操作类型
            optimize_cost: 是否优化总成本

        Returns:
            List[RoutingResult]: 路由结果列表
        """
        results = []

        if optimize_cost:
            # 按场景类型分组，减少模型切换
            from collections import defaultdict
            groups = defaultdict(list)
            for i, ctx in enumerate(contexts):
                groups[ctx.scene_type].append((i, ctx))

            # 为每组选择最优模型
            group_results = {}
            for scene_type, items in groups.items():
                # 使用第一个上下文来确定该组的模型
                _, first_ctx = items[0]
                result = self.route(first_ctx, operation)
                for idx, _ in items:
                    group_results[idx] = result

            # 按原始顺序返回结果
            results = [group_results[i] for i in range(len(contexts))]
        else:
            # 独立路由每个场景
            results = [self.route(ctx, operation) for ctx in contexts]

        return results

    def get_recommendation(self, context: RoutingContext) -> Dict[str, Any]:
        """获取详细的模型推荐报告"""
        if not self._providers:
            return {"error": "No providers available"}

        recommendations = []

        for name in self._providers:
            score, cost, reasons = self._calculate_score(
                name,
                self._providers[name],
                context,
                "video"
            )
            recommendations.append({
                "provider": name,
                "score": round(score, 3),
                "estimated_cost": cost,
                "reasons": reasons,
            })

        recommendations.sort(key=lambda x: x["score"], reverse=True)

        return {
            "context": {
                "scene_type": context.scene_type.value,
                "quality_level": context.quality_level.value,
                "budget_limit": context.budget_limit,
                "require_consistency": context.require_consistency,
            },
            "recommendations": recommendations,
            "best_choice": recommendations[0]["provider"] if recommendations else None,
        }


# 全局路由器实例
_router_instance: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """获取全局模型路由器实例"""
    global _router_instance
    if _router_instance is None:
        _router_instance = ModelRouter()
    return _router_instance
