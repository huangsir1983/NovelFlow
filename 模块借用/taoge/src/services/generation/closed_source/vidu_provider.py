"""
涛割 - Vidu Provider实现
"""

import asyncio
import aiohttp
from typing import Dict, Any, Optional

from ..base_provider import (
    BaseProvider,
    ProviderType,
    ProviderFactory,
    ImageGenerationRequest,
    VideoGenerationRequest,
    GenerationResult,
)


class ViduProvider(BaseProvider):
    """
    Vidu API Provider
    支持图像生成、视频生成和I2V
    """

    def __init__(self, api_key: str = "", base_url: str = ""):
        super().__init__(api_key, base_url)
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def provider_name(self) -> str:
        return "vidu"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.CLOSED_SOURCE

    @property
    def supported_features(self) -> Dict[str, bool]:
        return {
            "image_generation": True,
            "video_generation": True,
            "image_to_video": True,
            "character_consistency": True,
            "first_last_frame": False,  # Vidu暂不支持首尾帧
        }

    @property
    def cost_per_operation(self) -> Dict[str, float]:
        return {
            "image": 5.0,
            "video": 20.0,
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self._session is None or self._session.closed:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def close(self):
        """关闭HTTP会话"""
        if self._session and not self._session.closed:
            await self._session.close()

    def validate_credentials(self) -> bool:
        """验证API凭证"""
        return bool(self.api_key)

    async def generate_image(self, request: ImageGenerationRequest) -> GenerationResult:
        """
        生成图像

        注意：这是Vidu API的示例实现
        实际实现需要根据Vidu的API文档调整
        """
        if not self.validate_credentials():
            return GenerationResult(
                success=False,
                error_message="API密钥未配置",
                error_code="AUTH_ERROR"
            )

        try:
            session = await self._get_session()

            # 构建请求参数
            payload = {
                "prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "width": request.width,
                "height": request.height,
                "style": request.style,
                "num_images": request.num_images,
            }

            if request.seed:
                payload["seed"] = request.seed

            if request.character_refs:
                payload["reference_images"] = request.character_refs

            # 发送请求
            # 注意：实际URL需要根据Vidu API文档确定
            async with session.post(
                f"{self.base_url}/v1/images/generations",
                json=payload
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return GenerationResult(
                        success=True,
                        result_url=result.get("data", [{}])[0].get("url"),
                        task_id=result.get("task_id"),
                        credits_used=self.cost_per_operation["image"],
                        metadata=result
                    )
                else:
                    error_text = await response.text()
                    return GenerationResult(
                        success=False,
                        error_message=f"API错误: {error_text}",
                        error_code=str(response.status)
                    )

        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=str(e),
                error_code="EXCEPTION"
            )

    async def generate_video(self, request: VideoGenerationRequest) -> GenerationResult:
        """生成视频（纯文本到视频）"""
        if not self.validate_credentials():
            return GenerationResult(
                success=False,
                error_message="API密钥未配置",
                error_code="AUTH_ERROR"
            )

        try:
            session = await self._get_session()

            payload = {
                "prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "duration": request.duration,
                "width": request.width,
                "height": request.height,
                "fps": request.fps,
            }

            # 发送请求
            async with session.post(
                f"{self.base_url}/v1/videos/generations",
                json=payload
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return GenerationResult(
                        success=True,
                        task_id=result.get("task_id"),
                        status="processing",  # 视频生成通常是异步的
                        credits_used=self.cost_per_operation["video"],
                        metadata=result
                    )
                else:
                    error_text = await response.text()
                    return GenerationResult(
                        success=False,
                        error_message=f"API错误: {error_text}",
                        error_code=str(response.status)
                    )

        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=str(e),
                error_code="EXCEPTION"
            )

    async def image_to_video(self, request: VideoGenerationRequest) -> GenerationResult:
        """图像转视频（I2V）"""
        if not self.validate_credentials():
            return GenerationResult(
                success=False,
                error_message="API密钥未配置",
                error_code="AUTH_ERROR"
            )

        if not request.source_image:
            return GenerationResult(
                success=False,
                error_message="未提供源图像",
                error_code="INVALID_INPUT"
            )

        try:
            session = await self._get_session()

            payload = {
                "prompt": request.prompt,
                "image": request.source_image,
                "duration": request.duration,
                "motion": request.camera_motion,
                "motion_intensity": request.motion_intensity,
            }

            async with session.post(
                f"{self.base_url}/v1/videos/img2video",
                json=payload
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return GenerationResult(
                        success=True,
                        task_id=result.get("task_id"),
                        status="processing",
                        credits_used=self.cost_per_operation["video"],
                        metadata=result
                    )
                else:
                    error_text = await response.text()
                    return GenerationResult(
                        success=False,
                        error_message=f"API错误: {error_text}",
                        error_code=str(response.status)
                    )

        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=str(e),
                error_code="EXCEPTION"
            )

    async def check_task_status(self, task_id: str) -> Dict[str, Any]:
        """检查任务状态"""
        try:
            session = await self._get_session()

            async with session.get(
                f"{self.base_url}/v1/tasks/{task_id}"
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "status": result.get("status", "unknown"),
                        "progress": result.get("progress", 0),
                        "result_url": result.get("result_url"),
                        "error": result.get("error"),
                    }
                else:
                    return {
                        "status": "error",
                        "error": f"HTTP {response.status}"
                    }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }


# 注册Provider
ProviderFactory.register("vidu", ViduProvider)
