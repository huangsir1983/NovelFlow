"""
涛割 - 云雾 Provider 实现
支持 gemini-3-pro-image-preview 图片生成 和 sora-2 视频生成

图片生成流程（Gemini 原生 API 格式）:
  POST https://yunwu.ai/v1beta/models/gemini-3-pro-image-preview:generateContent?key={API_KEY}
  请求体: {contents: [{role: "user", parts: [{text: "..."}]}],
           generationConfig: {responseModalities: ["IMAGE", "TEXT"],
                              imageConfig: {aspectRatio: "16:9"}}}
  响应: {candidates: [{content: {parts: [{inlineData: {mimeType, data}}]}}]}
"""

import asyncio
import aiohttp
import base64
import json
import os
import tempfile
from typing import Dict, Any, Optional, List

from ..base_provider import (
    BaseProvider,
    ProviderType,
    ImageGenerationRequest,
    VideoGenerationRequest,
    GenerationResult,
)


class YunwuProvider(BaseProvider):
    """
    云雾 API Provider (yunwu.ai)
    统一密钥，支持:
    - 图片生成: gemini-3-pro-image-preview (Gemini 原生 API)
    - 视频生成: sora-2 / sora-2-pro (POST /v1/video/create)
    """

    # 图片生成模型
    IMAGE_MODEL = "gemini-3-pro-image-preview"

    def __init__(self, api_key: str = "", base_url: str = "https://yunwu.ai"):
        super().__init__(api_key, base_url or "https://yunwu.ai")
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def provider_name(self) -> str:
        return "yunwu"

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
            "image": 3.0,
            "video": 15.0,
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取 HTTP session"""
        if self._session is None or self._session.closed:
            headers = {
                "Content-Type": "application/json",
            }
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def validate_credentials(self) -> bool:
        return bool(self.api_key)

    # ================================================================
    #  图片生成 — Gemini 原生 API
    # ================================================================

    async def generate_image(self, request: ImageGenerationRequest) -> GenerationResult:
        """
        使用 gemini-3-pro-image-preview 生成图片（Gemini 原生 API 格式）

        端点: POST /v1beta/models/gemini-3-pro-image-preview:generateContent?key={API_KEY}
        认证: query param key + Bearer token
        请求体: Gemini contents 格式 + imageConfig 控制宽高比
        响应: candidates[].content.parts[].inlineData (base64 图片)
        """
        if not self.validate_credentials():
            return GenerationResult(
                success=False,
                error_message="未配置云雾API密钥"
            )

        # 构建 Gemini 原生格式请求体
        generation_config: Dict[str, Any] = {
            "responseModalities": ["IMAGE", "TEXT"],
        }

        # 从 model_params 或 width/height 推断宽高比
        aspect_ratio = request.model_params.get('aspect_ratio', '')
        if not aspect_ratio and request.width and request.height:
            aspect_ratio = self._size_to_aspect_ratio(request.width, request.height)
        if aspect_ratio:
            generation_config["imageConfig"] = {"aspectRatio": aspect_ratio}

        body: Dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": self._build_content_parts(request)
                }
            ],
            "generationConfig": generation_config,
        }

        # 系统指令（分镜组图等场景使用 Gemini systemInstruction 字段）
        sys_instr = request.model_params.get('system_instruction', '')
        if sys_instr:
            body["systemInstruction"] = {
                "parts": [{"text": sys_instr}]
            }

        # 端点 URL: key 作为 query parameter
        url = (
            f"{self.base_url}/v1beta/models/{self.IMAGE_MODEL}:generateContent"
            f"?key={self.api_key}"
        )

        try:
            session = await self._get_session()
            # 额外传 Bearer token（云雾 securitySchemes 要求）
            headers = {"Authorization": f"Bearer {self.api_key}"}

            async with session.post(url, json=body, headers=headers) as resp:
                resp_text = await resp.text()
                if resp.status != 200:
                    return GenerationResult(
                        success=False,
                        error_message=f"图片生成失败 HTTP {resp.status}: {resp_text}"
                    )

                data = json.loads(resp_text)

        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=f"请求失败: {str(e)}"
            )

        # 解析响应，提取 base64 图片
        return self._parse_gemini_image_response(data)

    @staticmethod
    def _build_content_parts(request: 'ImageGenerationRequest') -> list:
        """构建 Gemini contents.parts 列表，支持图片编辑模式"""
        import base64 as b64_mod
        parts = []

        # 如果有参考图（图片编辑模式）：先放图片再放文字
        if request.reference_images:
            for img_path in request.reference_images:
                try:
                    with open(img_path, 'rb') as f:
                        b64_data = b64_mod.b64encode(f.read()).decode()
                    mime = 'image/png'
                    if img_path.lower().endswith(('.jpg', '.jpeg')):
                        mime = 'image/jpeg'
                    elif img_path.lower().endswith('.webp'):
                        mime = 'image/webp'
                    parts.append({
                        "inlineData": {"mimeType": mime, "data": b64_data}
                    })
                except Exception:
                    pass  # 跳过无法读取的图片

        parts.append({"text": request.prompt})
        return parts

    @staticmethod
    def _size_to_aspect_ratio(width: int, height: int) -> str:
        """从宽高像素推断最接近的标准宽高比"""
        if not width or not height:
            return ""
        ratio = width / height
        # 支持的宽高比: 1:1, 3:2, 2:3, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9
        candidates = [
            (1.0, "1:1"), (1.5, "3:2"), (2/3, "2:3"),
            (0.75, "3:4"), (4/3, "4:3"), (0.8, "4:5"),
            (1.25, "5:4"), (9/16, "9:16"), (16/9, "16:9"),
            (21/9, "21:9"),
        ]
        best = min(candidates, key=lambda c: abs(c[0] - ratio))
        return best[1]

    def _parse_gemini_image_response(self, data: dict) -> GenerationResult:
        """
        解析 Gemini 图片生成响应
        格式: {candidates: [{content: {parts: [{inlineData: {mimeType, data}}, {text: "..."}]}}]}
        """
        candidates = data.get("candidates", [])
        if not candidates:
            error = data.get("error", {})
            if error:
                return GenerationResult(
                    success=False,
                    error_message=f"API 错误: {error.get('message', json.dumps(error, ensure_ascii=False))}"
                )
            return GenerationResult(
                success=False,
                error_message=f"API 返回无 candidates: {json.dumps(data, ensure_ascii=False)[:500]}"
            )

        parts = candidates[0].get("content", {}).get("parts", [])

        # 查找 inlineData（base64 图片）
        image_paths = []
        description = ""

        for part in parts:
            if "inlineData" in part:
                inline = part["inlineData"]
                mime_type = inline.get("mimeType", "image/png")
                b64_data = inline.get("data", "")

                if b64_data:
                    # 保存 base64 到临时文件
                    ext = ".png"
                    if "jpeg" in mime_type or "jpg" in mime_type:
                        ext = ".jpg"
                    elif "webp" in mime_type:
                        ext = ".webp"

                    output_dir = os.path.join("generated", "images")
                    os.makedirs(output_dir, exist_ok=True)

                    import uuid
                    filename = f"gemini_{uuid.uuid4().hex[:8]}{ext}"
                    filepath = os.path.join(output_dir, filename)

                    try:
                        img_bytes = base64.b64decode(b64_data)
                        with open(filepath, "wb") as f:
                            f.write(img_bytes)
                        image_paths.append(filepath)
                        print(f"[涛割] 图片已保存: {filepath} ({len(img_bytes)} bytes)")
                    except Exception as e:
                        print(f"[涛割] base64 解码/保存失败: {e}")

            elif "text" in part:
                description += part["text"]

        if image_paths:
            return GenerationResult(
                success=True,
                result_path=image_paths[0],
                metadata={
                    "all_images": image_paths,
                    "description": description,
                },
            )

        return GenerationResult(
            success=False,
            error_message=f"响应中未找到图片数据，文本内容: {description[:200]}"
        )

    # ================================================================
    #  视频生成 — sora-2 (POST /v1/videos)
    # ================================================================

    async def generate_video(self, request: VideoGenerationRequest) -> GenerationResult:
        """
        使用 sora-2 模型生成视频
        POST {base_url}/v1/videos
        遵循 OpenAI 标准 Video API 格式
        """
        if not self.validate_credentials():
            return GenerationResult(
                success=False,
                error_message="未配置云雾API密钥"
            )

        model = request.model_params.get('model', 'sora-2-all')
        orientation = request.model_params.get('orientation', 'landscape')
        size = request.model_params.get('size', 'large')
        duration = int(request.duration) if request.duration else 10

        # 构建 OpenAI 标准 Video API 请求体
        body: Dict[str, Any] = {
            "model": model,
            "prompt": request.prompt,
        }

        # 尺寸参数：优先使用 size 字段，也支持 orientation 推断
        if size:
            body["size"] = size

        # 时长：OpenAI 格式用字符串 seconds 字段
        body["seconds"] = str(duration)

        # 参考图列表（I2V）
        images = list(request.model_params.get('images', []))
        if request.source_image:
            images = [request.source_image] + images
        if images:
            body["images"] = images

        # 可选参数
        if request.model_params.get('watermark') is not None:
            body["watermark"] = request.model_params.get('watermark', False)
        if 'private' in request.model_params:
            body["private"] = request.model_params['private']

        url = f"{self.base_url}/v1/videos"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            session = await self._get_session()
            async with session.post(url, json=body, headers=headers) as resp:
                resp_text = await resp.text()
                if resp.status == 200:
                    data = json.loads(resp_text)
                    video_id = data.get("id", "")
                    status = data.get("status", "")

                    # 如果已经完成（不太可能，但兼容处理）
                    if status in ("completed", "succeeded", "success"):
                        video_url = (
                            data.get("video_url")
                            or data.get("url")
                            or data.get("result", {}).get("url", "")
                        )
                        return GenerationResult(
                            success=True,
                            result_url=video_url,
                            task_id=video_id,
                            metadata={"model": model},
                        )
                    elif video_id:
                        # 正常情况：返回 video_id + queued/in_progress 状态，开始轮询
                        print(f"[涛割] 视频任务已提交: id={video_id}, status={status}")
                        result = await self._poll_video_task(video_id)
                        return result
                    else:
                        return GenerationResult(
                            success=False,
                            error_message=f"API 返回异常: {resp_text[:500]}",
                        )
                else:
                    return GenerationResult(
                        success=False,
                        error_message=f"HTTP {resp.status}: {resp_text[:500]}",
                    )
        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=f"请求失败: {str(e)}",
            )

    async def image_to_video(self, request: VideoGenerationRequest) -> GenerationResult:
        """图生视频 — 通过 source_image 参数传入图片 URL"""
        return await self.generate_video(request)

    async def _poll_video_task(
        self, video_id: str,
        max_retries: int = 120,
        interval: float = 5.0,
    ) -> GenerationResult:
        """
        轮询视频生成任务状态
        GET {base_url}/v1/videos/{video_id}
        """
        url = f"{self.base_url}/v1/videos/{video_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        for attempt in range(max_retries):
            try:
                session = await self._get_session()
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        status = data.get("status", "")
                        progress = data.get("progress", "")
                        if progress:
                            print(f"[涛割] 视频生成进度: {progress}% (attempt={attempt+1})")

                        if status in ("completed", "succeeded", "success"):
                            # 尝试从响应中直接获取 URL
                            video_url = (
                                data.get("video_url")
                                or data.get("url")
                                or data.get("result", {}).get("url", "")
                            )

                            # OpenAI 标准格式: 需要通过 /content 端点下载
                            if not video_url:
                                video_url = await self._download_video_content(video_id)

                            return GenerationResult(
                                success=True,
                                result_url=video_url,
                                task_id=video_id,
                                status="completed",
                            )
                        elif status in ("failed", "error", "cancelled"):
                            return GenerationResult(
                                success=False,
                                task_id=video_id,
                                error_message=data.get("error", "视频生成失败"),
                            )
                        # 其他状态（queued, in_progress）继续轮询
                    else:
                        error_text = await resp.text()
                        # 404 可能是路径问题，打印详细信息便于调试
                        print(f"[涛割] 轮询视频状态 HTTP {resp.status}: {error_text[:200]}")
                        # 非 200 状态：如果是 4xx 客户端错误则不重试
                        if 400 <= resp.status < 500:
                            return GenerationResult(
                                success=False,
                                error_message=f"轮询失败 HTTP {resp.status}: {error_text[:500]}",
                            )
            except Exception as e:
                print(f"[涛割] 轮询视频任务异常: {e}")

            await asyncio.sleep(interval)

        return GenerationResult(
            success=False,
            task_id=video_id,
            error_message="视频生成超时",
        )

    async def _download_video_content(self, video_id: str) -> str:
        """
        通过 /content 端点下载视频文件，保存到本地并返回路径。
        GET {base_url}/v1/videos/{video_id}/content
        """
        url = f"{self.base_url}/v1/videos/{video_id}/content"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            session = await self._get_session()
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get('Content-Type', '')
                    ext = ".mp4"
                    if "webm" in content_type:
                        ext = ".webm"

                    output_dir = os.path.join("generated", "videos")
                    os.makedirs(output_dir, exist_ok=True)

                    import uuid
                    filename = f"sora_{video_id[:12]}_{uuid.uuid4().hex[:6]}{ext}"
                    filepath = os.path.join(output_dir, filename)

                    data = await resp.read()
                    with open(filepath, "wb") as f:
                        f.write(data)
                    print(f"[涛割] 视频已下载: {filepath} ({len(data)} bytes)")
                    return filepath
                else:
                    # /content 端点不可用，返回轮询 URL 作为 fallback
                    print(f"[涛割] 下载视频内容失败 HTTP {resp.status}")
                    return f"{self.base_url}/v1/videos/{video_id}/content"
        except Exception as e:
            print(f"[涛割] 下载视频异常: {e}")
            return ""

    async def check_task_status(self, task_id: str) -> Dict[str, Any]:
        """检查异步任务状态"""
        url = f"{self.base_url}/v1/videos/{task_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            session = await self._get_session()
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}
        return {"status": "unknown"}
