"""
涛割 - Kling Provider实现
可灵AI视频生成API
"""

import asyncio
import aiohttp
import time
import jwt
import hashlib
import base64
from typing import Dict, Any, Optional

from ..base_provider import (
    BaseProvider,
    ProviderType,
    ProviderFactory,
    ImageGenerationRequest,
    VideoGenerationRequest,
    GenerationResult,
)


class KlingProvider(BaseProvider):
    """
    Kling (可灵) API Provider
    支持图像生成、视频生成和I2V

    认证方式: Access Key + Secret Key → JWT Token
    API文档: https://docs.qingque.cn/d/home/eZQDPMvNX5pVD3VvKkDwwMpoG
    """

    BASE_URL = "https://api.klingai.com"

    # 模型选项
    MODELS = {
        "image": "kling-v1",
        "video": "kling-v1",
        "video_pro": "kling-v1-5"
    }

    # 视频时长选项 (秒)
    DURATION_OPTIONS = [5, 10]

    def __init__(self, access_key: str = "", secret_key: str = "", base_url: str = ""):
        super().__init__(api_key=access_key, base_url=base_url or self.BASE_URL)
        self.access_key = access_key
        self.secret_key = secret_key
        self._session: Optional[aiohttp.ClientSession] = None
        self._token_cache: Optional[str] = None
        self._token_expire: float = 0

    @property
    def provider_name(self) -> str:
        return "kling"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.CLOSED_SOURCE

    @property
    def supported_features(self) -> Dict[str, bool]:
        return {
            "image_generation": True,
            "video_generation": True,
            "image_to_video": True,
            "character_consistency": False,  # Kling暂不支持角色一致性
            "first_last_frame": True,  # 支持首尾帧控制
        }

    @property
    def cost_per_operation(self) -> Dict[str, float]:
        return {
            "image": 1.0,  # 约0.014元/张
            "video_5s": 3.5,  # 约0.049元/5秒
            "video_10s": 7.0,  # 约0.098元/10秒
            "video": 3.5,  # 默认5秒
        }

    def _generate_jwt_token(self) -> str:
        """
        生成JWT Token用于API认证
        Token有效期30分钟，提前5分钟刷新
        """
        current_time = time.time()

        # 检查缓存的token是否有效
        if self._token_cache and current_time < self._token_expire - 300:
            return self._token_cache

        # 生成新token
        headers = {
            "alg": "HS256",
            "typ": "JWT"
        }

        payload = {
            "iss": self.access_key,
            "exp": int(current_time) + 1800,  # 30分钟有效期
            "nbf": int(current_time) - 5  # 允许5秒时钟偏差
        }

        token = jwt.encode(payload, self.secret_key, algorithm="HS256", headers=headers)

        # 缓存token
        self._token_cache = token
        self._token_expire = payload["exp"]

        return token

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self._session is None or self._session.closed:
            token = self._generate_jwt_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            self._session = aiohttp.ClientSession(headers=headers)
        else:
            # 更新token（如果需要）
            token = self._generate_jwt_token()
            self._session._default_headers["Authorization"] = f"Bearer {token}"
        return self._session

    async def close(self):
        """关闭HTTP会话"""
        if self._session and not self._session.closed:
            await self._session.close()

    def validate_credentials(self) -> bool:
        """验证API凭证"""
        return bool(self.access_key and self.secret_key)

    async def generate_image(self, request: ImageGenerationRequest) -> GenerationResult:
        """
        生成图像

        API: POST /v1/images/generations
        """
        if not self.validate_credentials():
            return GenerationResult(
                success=False,
                error_message="API密钥未配置 (需要Access Key和Secret Key)",
                error_code="AUTH_ERROR"
            )

        try:
            session = await self._get_session()

            # 构建请求参数
            payload = {
                "model": self.MODELS["image"],
                "prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "image_count": request.num_images,
                "aspect_ratio": self._get_aspect_ratio(request.width, request.height),
            }

            # 参考图（图生图模式）
            if request.reference_images:
                payload["image"] = request.reference_images[0]

            # 发送请求
            async with session.post(
                f"{self.base_url}/v1/images/generations",
                json=payload
            ) as response:
                result = await response.json()

                if response.status == 200 and result.get("code") == 0:
                    task_id = result.get("data", {}).get("task_id")
                    return GenerationResult(
                        success=True,
                        task_id=task_id,
                        status="processing",
                        credits_used=self.cost_per_operation["image"],
                        metadata=result
                    )
                else:
                    return GenerationResult(
                        success=False,
                        error_message=result.get("message", f"API错误: {response.status}"),
                        error_code=str(result.get("code", response.status))
                    )

        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=str(e),
                error_code="EXCEPTION"
            )

    async def generate_video(self, request: VideoGenerationRequest) -> GenerationResult:
        """
        文本生成视频 (T2V)

        API: POST /v1/videos/text2video
        """
        if not self.validate_credentials():
            return GenerationResult(
                success=False,
                error_message="API密钥未配置",
                error_code="AUTH_ERROR"
            )

        try:
            session = await self._get_session()

            # 确定视频时长
            duration = "5" if request.duration <= 5 else "10"

            payload = {
                "model": self.MODELS["video"],
                "prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "duration": duration,
                "aspect_ratio": self._get_aspect_ratio(request.width, request.height),
                "cfg_scale": request.model_params.get("cfg_scale", 0.5),
            }

            # 运镜控制
            if request.camera_motion and request.camera_motion != "static":
                payload["camera_control"] = {
                    "type": self._map_camera_motion(request.camera_motion),
                }

            async with session.post(
                f"{self.base_url}/v1/videos/text2video",
                json=payload
            ) as response:
                result = await response.json()

                if response.status == 200 and result.get("code") == 0:
                    task_id = result.get("data", {}).get("task_id")
                    cost_key = f"video_{duration}s"
                    return GenerationResult(
                        success=True,
                        task_id=task_id,
                        status="processing",
                        credits_used=self.cost_per_operation.get(cost_key, self.cost_per_operation["video"]),
                        metadata=result
                    )
                else:
                    return GenerationResult(
                        success=False,
                        error_message=result.get("message", f"API错误: {response.status}"),
                        error_code=str(result.get("code", response.status))
                    )

        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=str(e),
                error_code="EXCEPTION"
            )

    async def image_to_video(self, request: VideoGenerationRequest) -> GenerationResult:
        """
        图像转视频 (I2V)

        API: POST /v1/videos/image2video
        支持首帧图、尾帧图控制
        """
        if not self.validate_credentials():
            return GenerationResult(
                success=False,
                error_message="API密钥未配置",
                error_code="AUTH_ERROR"
            )

        if not request.source_image and not request.start_frame:
            return GenerationResult(
                success=False,
                error_message="未提供源图像或首帧图",
                error_code="INVALID_INPUT"
            )

        try:
            session = await self._get_session()

            # 确定视频时长
            duration = "5" if request.duration <= 5 else "10"

            payload = {
                "model": self.MODELS["video"],
                "prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "duration": duration,
                "cfg_scale": request.model_params.get("cfg_scale", 0.5),
            }

            # 首帧图（必需）
            if request.start_frame:
                payload["image"] = request.start_frame
            elif request.source_image:
                payload["image"] = request.source_image

            # 尾帧图（可选，Kling特色功能）
            if request.end_frame:
                payload["image_tail"] = request.end_frame

            # 运镜控制
            if request.camera_motion and request.camera_motion != "static":
                payload["camera_control"] = {
                    "type": self._map_camera_motion(request.camera_motion),
                }

            async with session.post(
                f"{self.base_url}/v1/videos/image2video",
                json=payload
            ) as response:
                result = await response.json()

                if response.status == 200 and result.get("code") == 0:
                    task_id = result.get("data", {}).get("task_id")
                    cost_key = f"video_{duration}s"
                    return GenerationResult(
                        success=True,
                        task_id=task_id,
                        status="processing",
                        credits_used=self.cost_per_operation.get(cost_key, self.cost_per_operation["video"]),
                        metadata=result
                    )
                else:
                    return GenerationResult(
                        success=False,
                        error_message=result.get("message", f"API错误: {response.status}"),
                        error_code=str(result.get("code", response.status))
                    )

        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=str(e),
                error_code="EXCEPTION"
            )

    async def check_task_status(self, task_id: str, task_type: str = "image") -> Dict[str, Any]:
        """
        检查任务状态

        task_type: "image" 或 "video"
        """
        try:
            session = await self._get_session()

            # 根据任务类型选择不同的查询接口
            if task_type == "image":
                url = f"{self.base_url}/v1/images/generations/{task_id}"
            else:
                url = f"{self.base_url}/v1/videos/image2video/{task_id}"

            async with session.get(url) as response:
                result = await response.json()

                if response.status == 200 and result.get("code") == 0:
                    data = result.get("data", {})
                    task_status = data.get("task_status", "unknown")

                    # 映射状态
                    status_map = {
                        "submitted": "pending",
                        "processing": "processing",
                        "succeed": "completed",
                        "failed": "failed",
                    }

                    # 获取结果
                    result_url = None
                    if task_status == "succeed":
                        works = data.get("task_result", {}).get("videos" if task_type == "video" else "images", [])
                        if works:
                            result_url = works[0].get("url")

                    return {
                        "status": status_map.get(task_status, task_status),
                        "progress": 100 if task_status == "succeed" else 50 if task_status == "processing" else 0,
                        "result_url": result_url,
                        "error": data.get("task_status_msg") if task_status == "failed" else None,
                        "raw_data": data
                    }
                else:
                    return {
                        "status": "error",
                        "error": result.get("message", f"HTTP {response.status}")
                    }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def wait_for_result(self, task_id: str, task_type: str = "image",
                              timeout: int = 300, poll_interval: int = 5) -> GenerationResult:
        """
        等待任务完成并返回结果

        Args:
            task_id: 任务ID
            task_type: 任务类型 ("image" 或 "video")
            timeout: 超时时间（秒）
            poll_interval: 轮询间隔（秒）
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = await self.check_task_status(task_id, task_type)

            if status["status"] == "completed":
                return GenerationResult(
                    success=True,
                    result_url=status.get("result_url"),
                    task_id=task_id,
                    status="completed",
                    metadata=status.get("raw_data", {})
                )
            elif status["status"] == "failed":
                return GenerationResult(
                    success=False,
                    task_id=task_id,
                    status="failed",
                    error_message=status.get("error", "任务失败"),
                    error_code="TASK_FAILED"
                )
            elif status["status"] == "error":
                return GenerationResult(
                    success=False,
                    task_id=task_id,
                    status="error",
                    error_message=status.get("error", "查询失败"),
                    error_code="QUERY_ERROR"
                )

            await asyncio.sleep(poll_interval)

        return GenerationResult(
            success=False,
            task_id=task_id,
            status="timeout",
            error_message=f"任务超时 ({timeout}秒)",
            error_code="TIMEOUT"
        )

    def _get_aspect_ratio(self, width: int, height: int) -> str:
        """
        根据宽高计算宽高比
        Kling支持: 1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3
        """
        ratio = width / height

        # 常见比例映射
        ratios = {
            1.0: "1:1",
            16/9: "16:9",
            9/16: "9:16",
            4/3: "4:3",
            3/4: "3:4",
            3/2: "3:2",
            2/3: "2:3",
        }

        # 找最接近的比例
        closest = min(ratios.keys(), key=lambda x: abs(x - ratio))
        return ratios[closest]

    def _map_camera_motion(self, motion: str) -> str:
        """
        映射运镜类型到Kling API格式
        """
        motion_map = {
            "zoom_in": "zoom_in",
            "zoom_out": "zoom_out",
            "pan_left": "pan_left",
            "pan_right": "pan_right",
            "tilt_up": "tilt_up",
            "tilt_down": "tilt_down",
            "rotate_cw": "rotate_clockwise",
            "rotate_ccw": "rotate_counter_clockwise",
        }
        return motion_map.get(motion, "simple")


# 注册Provider
ProviderFactory.register("kling", KlingProvider)
