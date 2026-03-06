"""
涛割 - Geek Provider 实现
支持 gemini 图片生成（谷歌异步格式）

图片生成流程:
  POST https://api.geekapi.io/v1/images
  请求头: Authorization: Bearer {API_KEY}
  请求体: {contents: [{role: "user", parts: [{text: "..."}]}],
           generationConfig: {responseModalities: ["IMAGE", "TEXT"],
                              imageConfig: {aspectRatio: "16:9", imageSize: "1024x1024"}}}
  响应: {candidates: [{content: {parts: [{inlineData: {mimeType, data}}]}}]}
"""

import aiohttp
import base64
import json
import os
from typing import Dict, Any, Optional

from ..base_provider import (
    BaseProvider,
    ProviderType,
    ImageGenerationRequest,
    VideoGenerationRequest,
    GenerationResult,
)


class GeekProvider(BaseProvider):
    """
    Geek API Provider (geekapi.io)
    支持:
    - 图片生成: gemini 系列模型（谷歌异步格式 POST /v1/images）
    """

    IMAGE_MODEL = "gemini-3-pro-image-preview"

    def __init__(self, api_key: str = "", base_url: str = "https://www.geeknow.top/v1"):
        super().__init__(api_key, base_url or "https://www.geeknow.top/v1")
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def provider_name(self) -> str:
        return "geek"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.CLOSED_SOURCE

    @property
    def supported_features(self) -> Dict[str, bool]:
        return {
            "image_generation": True,
            "video_generation": False,
            "image_to_video": False,
            "character_consistency": False,
            "first_last_frame": False,
        }

    @property
    def cost_per_operation(self) -> Dict[str, float]:
        return {
            "image": 3.0,
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def validate_credentials(self) -> bool:
        return bool(self.api_key)

    # ================================================================
    #  图片生成 — 谷歌异步格式 POST /v1/images
    # ================================================================

    async def generate_image(self, request: ImageGenerationRequest) -> GenerationResult:
        """
        使用 Geek API 生成图片（Gemini 原生格式）

        端点: POST {base_url}/v1beta/models/gemini-3-pro-image-preview:generateContent
        认证: Authorization: Bearer {API_KEY}
        请求体: contents + generationConfig（含 imageConfig）
        响应: candidates[].content.parts[].inlineData (base64 图片)
        """
        if not self.validate_credentials():
            return GenerationResult(
                success=False,
                error_message="未配置 Geek API 密钥"
            )

        # 构建请求体
        # imageConfig 中 aspectRatio 和 imageSize 均为 required
        aspect_ratio = request.model_params.get('aspect_ratio', '') or '1:1'
        if not aspect_ratio and request.width and request.height:
            aspect_ratio = self._size_to_aspect_ratio(request.width, request.height)

        image_size = request.model_params.get('image_size', '') or '1024x1024'

        generation_config: Dict[str, Any] = {
            "responseModalities": ["IMAGE", "TEXT"],
            "imageConfig": {
                "aspectRatio": aspect_ratio,
                "imageSize": image_size,
            },
        }

        body: Dict[str, Any] = {
            "model": "gemini-3-pro-image-preview",
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

        url = f"{self.base_url}/images"
        print(f"[涛割] Geek 请求 URL: {url}")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            session = await self._get_session()
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

        return self._parse_response(data)

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

    def _parse_response(self, data: dict) -> GenerationResult:
        """解析 Gemini 格式响应，提取 base64 图片"""
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

        image_paths = []
        description = ""

        for part in parts:
            if "inlineData" in part:
                inline = part["inlineData"]
                mime_type = inline.get("mimeType", "image/png")
                b64_data = inline.get("data", "")

                if b64_data:
                    ext = ".png"
                    if "jpeg" in mime_type or "jpg" in mime_type:
                        ext = ".jpg"
                    elif "webp" in mime_type:
                        ext = ".webp"

                    output_dir = os.path.join("generated", "images")
                    os.makedirs(output_dir, exist_ok=True)

                    import uuid
                    filename = f"geek_{uuid.uuid4().hex[:8]}{ext}"
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

    async def generate_video(self, request: VideoGenerationRequest) -> GenerationResult:
        return GenerationResult(success=False, error_message="Geek 渠道暂不支持视频生成")

    async def image_to_video(self, request: VideoGenerationRequest) -> GenerationResult:
        return GenerationResult(success=False, error_message="Geek 渠道暂不支持图生视频")

    @staticmethod
    def _size_to_aspect_ratio(width: int, height: int) -> str:
        """从宽高像素推断最接近的标准宽高比"""
        if not width or not height:
            return ""
        ratio = width / height
        candidates = [
            (1.0, "1:1"), (1.5, "3:2"), (2 / 3, "2:3"),
            (0.75, "3:4"), (4 / 3, "4:3"), (0.8, "4:5"),
            (1.25, "5:4"), (9 / 16, "9:16"), (16 / 9, "16:9"),
            (21 / 9, "21:9"),
        ]
        best = min(candidates, key=lambda c: abs(c[0] - ratio))
        return best[1]
