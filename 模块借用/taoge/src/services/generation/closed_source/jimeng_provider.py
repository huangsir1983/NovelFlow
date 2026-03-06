"""
涛割 - Jimeng Provider实现
即梦AI (字节跳动) 图像/视频生成API
"""

import asyncio
import aiohttp
import time
import hmac
import hashlib
import json
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlencode

from ..base_provider import (
    BaseProvider,
    ProviderType,
    ProviderFactory,
    ImageGenerationRequest,
    VideoGenerationRequest,
    GenerationResult,
)


class JimengProvider(BaseProvider):
    """
    Jimeng (即梦) API Provider
    字节跳动AI图像/视频生成服务

    认证方式: API Key (火山引擎签名)
    """

    BASE_URL = "https://visual.volcengineapi.com"

    # 模型选项
    MODELS = {
        "image": "jimeng-2.1",  # 图像生成模型
        "video": "jimeng-video-1.0",  # 视频生成模型
    }

    # 图像尺寸选项
    IMAGE_SIZES = {
        "1:1": (1024, 1024),
        "16:9": (1280, 720),
        "9:16": (720, 1280),
        "4:3": (1024, 768),
        "3:4": (768, 1024),
    }

    def __init__(self, api_key: str = "", secret_key: str = "", base_url: str = ""):
        """
        初始化Jimeng Provider

        Args:
            api_key: 火山引擎 Access Key ID
            secret_key: 火山引擎 Secret Access Key
            base_url: API基础URL
        """
        super().__init__(api_key=api_key, base_url=base_url or self.BASE_URL)
        self.access_key = api_key
        self.secret_key = secret_key
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def provider_name(self) -> str:
        return "jimeng"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.CLOSED_SOURCE

    @property
    def supported_features(self) -> Dict[str, bool]:
        return {
            "image_generation": True,
            "video_generation": True,
            "image_to_video": True,
            "character_consistency": False,
            "first_last_frame": False,
        }

    @property
    def cost_per_operation(self) -> Dict[str, float]:
        return {
            "image": 2.0,  # 约0.03元/张
            "video": 10.0,  # 约0.15元/视频
        }

    def _sign_request(self, method: str, path: str, params: Dict[str, Any],
                      body: str = "", timestamp: str = None) -> Dict[str, str]:
        """
        火山引擎API签名

        返回签名后的请求头
        """
        if timestamp is None:
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

        date = timestamp[:8]

        # 规范化请求
        canonical_uri = path
        canonical_querystring = urlencode(sorted(params.items())) if params else ""

        # 计算body hash
        payload_hash = hashlib.sha256(body.encode('utf-8')).hexdigest()

        # 签名头
        signed_headers = "content-type;host;x-date"
        host = "visual.volcengineapi.com"

        canonical_headers = f"content-type:application/json\nhost:{host}\nx-date:{timestamp}\n"

        canonical_request = f"{method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

        # 计算签名
        credential_scope = f"{date}/cn-north-1/cv/request"
        string_to_sign = f"HMAC-SHA256\n{timestamp}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"

        # 派生签名密钥
        def sign(key, msg):
            return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

        k_date = sign(self.secret_key.encode('utf-8'), date)
        k_region = sign(k_date, "cn-north-1")
        k_service = sign(k_region, "cv")
        k_signing = sign(k_service, "request")

        signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

        # 构建Authorization头
        authorization = f"HMAC-SHA256 Credential={self.access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"

        return {
            "Authorization": authorization,
            "Content-Type": "application/json",
            "Host": host,
            "X-Date": timestamp,
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
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

        使用即梦AI的文生图接口
        """
        if not self.validate_credentials():
            return GenerationResult(
                success=False,
                error_message="API密钥未配置 (需要Access Key和Secret Key)",
                error_code="AUTH_ERROR"
            )

        try:
            session = await self._get_session()

            # 确定图像尺寸
            width, height = self._get_image_size(request.width, request.height)

            # 构建请求体
            body_dict = {
                "req_key": "jimeng_high_aes_general_v21",
                "prompt": request.prompt,
                "width": width,
                "height": height,
                "seed": request.seed if request.seed else -1,
                "use_sr": True,  # 超分辨率
                "return_url": True,
            }

            # 负面提示词
            if request.negative_prompt:
                body_dict["negative_prompt"] = request.negative_prompt

            body = json.dumps(body_dict)

            # 签名请求
            path = "/2022-08-31/high_aes_general_v21"
            params = {"Action": "CVProcess", "Version": "2022-08-31"}
            headers = self._sign_request("POST", path, params, body)

            # 发送请求
            url = f"{self.base_url}{path}?{urlencode(params)}"

            async with session.post(url, data=body, headers=headers) as response:
                result = await response.json()

                if response.status == 200 and result.get("code") == 10000:
                    data = result.get("data", {})
                    image_urls = data.get("image_urls", [])

                    if image_urls:
                        return GenerationResult(
                            success=True,
                            result_url=image_urls[0],
                            status="completed",
                            credits_used=self.cost_per_operation["image"],
                            metadata=result
                        )
                    else:
                        # 异步任务，返回task_id
                        task_id = data.get("task_id")
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
        """
        if not self.validate_credentials():
            return GenerationResult(
                success=False,
                error_message="API密钥未配置",
                error_code="AUTH_ERROR"
            )

        try:
            session = await self._get_session()

            # 构建请求体
            body_dict = {
                "req_key": "jimeng_video_generation",
                "prompt": request.prompt,
                "duration": min(int(request.duration), 6),  # 即梦最长6秒
                "fps": request.fps,
                "return_url": True,
            }

            if request.negative_prompt:
                body_dict["negative_prompt"] = request.negative_prompt

            body = json.dumps(body_dict)

            # 签名请求
            path = "/2022-08-31/video_generation"
            params = {"Action": "CVProcess", "Version": "2022-08-31"}
            headers = self._sign_request("POST", path, params, body)

            url = f"{self.base_url}{path}?{urlencode(params)}"

            async with session.post(url, data=body, headers=headers) as response:
                result = await response.json()

                if response.status == 200 and result.get("code") == 10000:
                    data = result.get("data", {})
                    task_id = data.get("task_id")

                    return GenerationResult(
                        success=True,
                        task_id=task_id,
                        status="processing",
                        credits_used=self.cost_per_operation["video"],
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
                error_message="未提供源图像",
                error_code="INVALID_INPUT"
            )

        try:
            session = await self._get_session()

            # 获取源图像
            source_image = request.source_image or request.start_frame

            # 构建请求体
            body_dict = {
                "req_key": "jimeng_image_to_video",
                "image_url": source_image,
                "prompt": request.prompt,
                "duration": min(int(request.duration), 6),
                "return_url": True,
            }

            if request.negative_prompt:
                body_dict["negative_prompt"] = request.negative_prompt

            # 运动强度
            if request.motion_intensity:
                body_dict["motion_strength"] = request.motion_intensity

            body = json.dumps(body_dict)

            # 签名请求
            path = "/2022-08-31/image_to_video"
            params = {"Action": "CVProcess", "Version": "2022-08-31"}
            headers = self._sign_request("POST", path, params, body)

            url = f"{self.base_url}{path}?{urlencode(params)}"

            async with session.post(url, data=body, headers=headers) as response:
                result = await response.json()

                if response.status == 200 and result.get("code") == 10000:
                    data = result.get("data", {})
                    task_id = data.get("task_id")

                    return GenerationResult(
                        success=True,
                        task_id=task_id,
                        status="processing",
                        credits_used=self.cost_per_operation["video"],
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
        """
        try:
            session = await self._get_session()

            body_dict = {
                "req_key": "jimeng_query_task",
                "task_id": task_id,
            }

            body = json.dumps(body_dict)

            path = "/2022-08-31/query_task"
            params = {"Action": "CVProcess", "Version": "2022-08-31"}
            headers = self._sign_request("POST", path, params, body)

            url = f"{self.base_url}{path}?{urlencode(params)}"

            async with session.post(url, data=body, headers=headers) as response:
                result = await response.json()

                if response.status == 200 and result.get("code") == 10000:
                    data = result.get("data", {})
                    status = data.get("status", "unknown")

                    # 状态映射
                    status_map = {
                        "pending": "pending",
                        "running": "processing",
                        "success": "completed",
                        "failed": "failed",
                    }

                    result_url = None
                    if status == "success":
                        if task_type == "video":
                            result_url = data.get("video_url")
                        else:
                            urls = data.get("image_urls", [])
                            result_url = urls[0] if urls else None

                    return {
                        "status": status_map.get(status, status),
                        "progress": 100 if status == "success" else 50 if status == "running" else 0,
                        "result_url": result_url,
                        "error": data.get("error_msg") if status == "failed" else None,
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

    def _get_image_size(self, width: int, height: int) -> tuple:
        """
        根据请求的宽高返回即梦支持的尺寸
        """
        ratio = width / height

        # 找最接近的比例
        ratios = {
            1.0: "1:1",
            16/9: "16:9",
            9/16: "9:16",
            4/3: "4:3",
            3/4: "3:4",
        }

        closest = min(ratios.keys(), key=lambda x: abs(x - ratio))
        size_key = ratios[closest]

        return self.IMAGE_SIZES.get(size_key, (1024, 1024))


# 注册Provider
ProviderFactory.register("jimeng", JimengProvider)
