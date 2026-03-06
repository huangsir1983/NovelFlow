"""
涛割 - 生成服务模块
"""

from .base_provider import (
    BaseProvider,
    ProviderType,
    ProviderFactory,
    GenerationRequest,
    ImageGenerationRequest,
    VideoGenerationRequest,
    GenerationResult,
)

from .model_router import (
    ModelRouter,
    SceneType,
    QualityLevel,
    RoutingContext,
    RoutingResult,
    get_model_router,
)

from .closed_source import ViduProvider
from .open_source import ComfyUIProvider

__all__ = [
    # Base
    'BaseProvider',
    'ProviderType',
    'ProviderFactory',
    'GenerationRequest',
    'ImageGenerationRequest',
    'VideoGenerationRequest',
    'GenerationResult',
    # Router
    'ModelRouter',
    'SceneType',
    'QualityLevel',
    'RoutingContext',
    'RoutingResult',
    'get_model_router',
    # Providers
    'ViduProvider',
    'ComfyUIProvider',
]
