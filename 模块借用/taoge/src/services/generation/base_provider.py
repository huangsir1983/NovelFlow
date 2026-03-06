"""
涛割 - 生成服务基类
定义统一的生成服务接口（Strategy模式）
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class ProviderType(Enum):
    """提供者类型"""
    CLOSED_SOURCE = "closed_source"  # 闭源API
    OPEN_SOURCE = "open_source"  # 开源模型


@dataclass
class GenerationRequest:
    """生成请求基类"""
    prompt: str
    negative_prompt: str = ""
    width: int = 1920
    height: int = 1080

    # 参考图
    reference_images: List[str] = field(default_factory=list)

    # 模型参数
    model_params: Dict[str, Any] = field(default_factory=dict)

    # 回调ID（用于跟踪）
    request_id: Optional[str] = None
    scene_id: Optional[int] = None


@dataclass
class ImageGenerationRequest(GenerationRequest):
    """图像生成请求"""
    style: str = "realistic"
    num_images: int = 1
    seed: Optional[int] = None

    # 角色一致性
    character_refs: List[str] = field(default_factory=list)
    maintain_consistency: bool = True


@dataclass
class VideoGenerationRequest(GenerationRequest):
    """视频生成请求"""
    duration: float = 4.0  # 秒
    fps: int = 30

    # 首尾帧控制
    start_frame: Optional[str] = None
    end_frame: Optional[str] = None

    # 运镜控制
    camera_motion: str = "static"
    motion_intensity: float = 0.5

    # I2V模式
    source_image: Optional[str] = None

    # 角色一致性参考图
    character_refs: List[str] = field(default_factory=list)


@dataclass
class GenerationResult:
    """生成结果"""
    success: bool
    result_path: Optional[str] = None
    result_url: Optional[str] = None

    # 任务信息
    task_id: Optional[str] = None
    status: str = "completed"

    # 成本信息
    credits_used: float = 0.0

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 错误信息
    error_message: Optional[str] = None
    error_code: Optional[str] = None


class BaseProvider(ABC):
    """
    生成服务提供者基类
    所有闭源/开源模型Provider都需要实现此接口
    """

    def __init__(self, api_key: str = "", base_url: str = ""):
        self.api_key = api_key
        self.base_url = base_url
        self._client = None

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供者名称"""
        pass

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """提供者类型"""
        pass

    @property
    @abstractmethod
    def supported_features(self) -> Dict[str, bool]:
        """
        支持的功能
        返回格式: {
            "image_generation": True,
            "video_generation": True,
            "image_to_video": True,
            "character_consistency": True,
            "first_last_frame": False,
        }
        """
        pass

    @property
    @abstractmethod
    def cost_per_operation(self) -> Dict[str, float]:
        """
        每次操作的积分消耗
        返回格式: {
            "image": 5.0,
            "video": 20.0,
        }
        """
        pass

    @abstractmethod
    def validate_credentials(self) -> bool:
        """验证API凭证是否有效"""
        pass

    @abstractmethod
    async def generate_image(self, request: ImageGenerationRequest) -> GenerationResult:
        """生成图像"""
        pass

    @abstractmethod
    async def generate_video(self, request: VideoGenerationRequest) -> GenerationResult:
        """生成视频"""
        pass

    @abstractmethod
    async def image_to_video(self, request: VideoGenerationRequest) -> GenerationResult:
        """图像转视频（I2V）"""
        pass

    async def check_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        检查异步任务状态
        返回格式: {
            "status": "pending|processing|completed|failed",
            "progress": 0-100,
            "result_url": "...",
            "error": "..."
        }
        """
        return {"status": "completed", "progress": 100}

    def estimate_cost(self, operation: str, params: Dict[str, Any] = None) -> float:
        """预估操作成本"""
        base_cost = self.cost_per_operation.get(operation, 0)
        # 可以根据参数调整成本
        return base_cost

    def get_capabilities(self) -> Dict[str, Any]:
        """获取完整能力描述"""
        return {
            "name": self.provider_name,
            "type": self.provider_type.value,
            "features": self.supported_features,
            "costs": self.cost_per_operation,
        }


class ProviderFactory:
    """Provider工厂类"""

    _providers: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str, provider_class: type):
        """注册Provider"""
        cls._providers[name] = provider_class

    @classmethod
    def create(cls, name: str, **kwargs) -> BaseProvider:
        """创建Provider实例"""
        if name not in cls._providers:
            raise ValueError(f"Unknown provider: {name}")
        return cls._providers[name](**kwargs)

    @classmethod
    def get_available_providers(cls) -> List[str]:
        """获取所有已注册的Provider"""
        return list(cls._providers.keys())
