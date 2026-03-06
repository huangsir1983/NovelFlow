"""
涛割 - ComfyUI Provider
支持通过ComfyUI API进行图片和视频生成
"""

import os
import json
import uuid
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# websockets是可选依赖
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

from ..base_provider import (
    BaseProvider,
    ProviderType,
    ProviderFactory,
    ImageGenerationRequest,
    VideoGenerationRequest,
    GenerationResult,
)


@dataclass
class ComfyUIWorkflow:
    """ComfyUI工作流配置"""
    name: str
    workflow_json: Dict[str, Any]
    input_mappings: Dict[str, str]  # 参数名 -> 节点路径映射


class ComfyUIProvider(BaseProvider):
    """
    ComfyUI Provider
    通过WebSocket API与本地ComfyUI服务器通信
    """

    # 默认工作流模板
    DEFAULT_IMAGE_WORKFLOW = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": 7,
                "denoise": 1,
                "latent_image": ["5", 0],
                "model": ["4", 0],
                "negative": ["7", 0],
                "positive": ["6", 0],
                "sampler_name": "euler",
                "scheduler": "normal",
                "seed": 0,
                "steps": 20
            }
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "sd_xl_base_1.0.safetensors"
            }
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "batch_size": 1,
                "height": 1024,
                "width": 1024
            }
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["4", 1],
                "text": ""
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["4", 1],
                "text": ""
            }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["3", 0],
                "vae": ["4", 2]
            }
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "taoge",
                "images": ["8", 0]
            }
        }
    }

    def __init__(self, base_url: str = "http://127.0.0.1:8188", api_key: str = ""):
        super().__init__(api_key=api_key, base_url=base_url)
        self.ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        self.client_id = str(uuid.uuid4())
        self._custom_workflows: Dict[str, ComfyUIWorkflow] = {}

    @property
    def provider_name(self) -> str:
        return "ComfyUI"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.OPEN_SOURCE

    @property
    def supported_features(self) -> Dict[str, bool]:
        return {
            "image_generation": True,
            "video_generation": True,
            "image_to_video": True,
            "character_consistency": True,
            "first_last_frame": True,
        }

    @property
    def cost_per_operation(self) -> Dict[str, float]:
        # 本地运行，成本为0
        return {
            "image": 0.0,
            "video": 0.0,
        }

    def validate_credentials(self) -> bool:
        """验证ComfyUI服务器是否可用"""
        from urllib.request import urlopen
        from urllib.error import URLError
        try:
            response = urlopen(f"{self.base_url}/system_stats", timeout=5)
            return response.status == 200
        except (URLError, OSError):
            return False

    async def check_server_status(self) -> Dict[str, Any]:
        """检查服务器状态"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.base_url}/system_stats") as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "online": True,
                            "queue_remaining": data.get("exec_info", {}).get("queue_remaining", 0),
                            "system": data.get("system", {}),
                        }
            except Exception as e:
                return {"online": False, "error": str(e)}
        return {"online": False}

    async def get_available_models(self) -> Dict[str, List[str]]:
        """获取可用的模型列表"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.base_url}/object_info") as response:
                    if response.status == 200:
                        data = await response.json()

                        models = {
                            "checkpoints": [],
                            "loras": [],
                            "vaes": [],
                        }

                        # 提取checkpoint列表
                        if "CheckpointLoaderSimple" in data:
                            ckpt_info = data["CheckpointLoaderSimple"]["input"]["required"].get("ckpt_name", [])
                            if isinstance(ckpt_info, list) and len(ckpt_info) > 0:
                                models["checkpoints"] = ckpt_info[0] if isinstance(ckpt_info[0], list) else []

                        return models
            except Exception as e:
                return {"error": str(e)}
        return {}

    def register_workflow(self, name: str, workflow: ComfyUIWorkflow):
        """注册自定义工作流"""
        self._custom_workflows[name] = workflow

    def _build_image_workflow(self, request: ImageGenerationRequest) -> Dict[str, Any]:
        """构建图片生成工作流"""
        workflow = json.loads(json.dumps(self.DEFAULT_IMAGE_WORKFLOW))

        # 设置正向提示词
        workflow["6"]["inputs"]["text"] = request.prompt

        # 设置负向提示词
        workflow["7"]["inputs"]["text"] = request.negative_prompt or "low quality, blurry, distorted"

        # 设置尺寸
        workflow["5"]["inputs"]["width"] = request.width
        workflow["5"]["inputs"]["height"] = request.height

        # 设置种子
        if request.seed is not None:
            workflow["3"]["inputs"]["seed"] = request.seed
        else:
            workflow["3"]["inputs"]["seed"] = int(uuid.uuid4().int % (2**32))

        # 设置模型参数
        if "checkpoint" in request.model_params:
            workflow["4"]["inputs"]["ckpt_name"] = request.model_params["checkpoint"]

        if "steps" in request.model_params:
            workflow["3"]["inputs"]["steps"] = request.model_params["steps"]

        if "cfg" in request.model_params:
            workflow["3"]["inputs"]["cfg"] = request.model_params["cfg"]

        if "sampler" in request.model_params:
            workflow["3"]["inputs"]["sampler_name"] = request.model_params["sampler"]

        return workflow

    def _build_i2v_workflow(self, request: VideoGenerationRequest) -> Dict[str, Any]:
        """构建图生视频工作流（需要安装AnimateDiff等插件）"""
        # 这是一个简化的I2V工作流模板
        # 实际使用时需要根据安装的插件调整
        workflow = {
            "1": {
                "class_type": "LoadImage",
                "inputs": {
                    "image": request.source_image or ""
                }
            },
            "2": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": request.model_params.get("checkpoint", "sd_xl_base_1.0.safetensors")
                }
            },
            # AnimateDiff节点（如果安装了）
            "3": {
                "class_type": "ADE_AnimateDiffLoaderWithContext",
                "inputs": {
                    "model": ["2", 0],
                    "context_options": None,
                    "motion_lora": None,
                    "motion_model_settings": None,
                    "motion_scale": request.motion_intensity,
                    "apply_v2_models_properly": True,
                }
            },
            # 更多节点...
        }

        return workflow

    async def _queue_prompt(self, workflow: Dict[str, Any]) -> str:
        """提交工作流到队列"""
        prompt_data = {
            "prompt": workflow,
            "client_id": self.client_id
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/prompt",
                json=prompt_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("prompt_id", "")
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to queue prompt: {error_text}")

    async def _wait_for_completion(self, prompt_id: str, timeout: int = 300) -> Dict[str, Any]:
        """等待任务完成"""
        # 如果有websockets，使用WebSocket方式
        if HAS_WEBSOCKETS:
            return await self._wait_for_completion_ws(prompt_id, timeout)
        else:
            # 否则使用轮询方式
            return await self._wait_for_completion_polling(prompt_id, timeout)

    async def _wait_for_completion_ws(self, prompt_id: str, timeout: int = 300) -> Dict[str, Any]:
        """使用WebSocket等待任务完成"""
        ws_url = f"{self.ws_url}/ws?clientId={self.client_id}"

        try:
            async with websockets.connect(ws_url) as ws:
                start_time = asyncio.get_event_loop().time()

                while True:
                    if asyncio.get_event_loop().time() - start_time > timeout:
                        raise TimeoutError("Generation timeout")

                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        data = json.loads(message)

                        if data.get("type") == "executing":
                            exec_data = data.get("data", {})
                            if exec_data.get("prompt_id") == prompt_id:
                                if exec_data.get("node") is None:
                                    # 执行完成
                                    return {"status": "completed"}

                        elif data.get("type") == "execution_error":
                            error_data = data.get("data", {})
                            if error_data.get("prompt_id") == prompt_id:
                                return {
                                    "status": "failed",
                                    "error": error_data.get("exception_message", "Unknown error")
                                }

                        elif data.get("type") == "progress":
                            # 可以用于更新进度
                            pass

                    except asyncio.TimeoutError:
                        continue

        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def _wait_for_completion_polling(self, prompt_id: str, timeout: int = 300) -> Dict[str, Any]:
        """使用轮询方式等待任务完成"""
        start_time = asyncio.get_event_loop().time()
        poll_interval = 1.0  # 轮询间隔（秒）

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                return {"status": "failed", "error": "Generation timeout"}

            async with aiohttp.ClientSession() as session:
                # 检查历史记录
                async with session.get(f"{self.base_url}/history/{prompt_id}") as response:
                    if response.status == 200:
                        data = await response.json()
                        if prompt_id in data:
                            # 任务已完成
                            return {"status": "completed"}

                # 检查队列状态
                async with session.get(f"{self.base_url}/queue") as response:
                    if response.status == 200:
                        queue_data = await response.json()
                        running = queue_data.get("queue_running", [])
                        pending = queue_data.get("queue_pending", [])

                        # 检查是否在运行或等待队列中
                        in_queue = False
                        for item in running + pending:
                            if len(item) > 1 and item[1] == prompt_id:
                                in_queue = True
                                break

                        if not in_queue:
                            # 不在队列中，检查是否已完成
                            async with session.get(f"{self.base_url}/history/{prompt_id}") as hist_response:
                                if hist_response.status == 200:
                                    hist_data = await hist_response.json()
                                    if prompt_id in hist_data:
                                        return {"status": "completed"}
                                    else:
                                        return {"status": "failed", "error": "Task not found"}

            await asyncio.sleep(poll_interval)

    async def _get_output_images(self, prompt_id: str) -> List[str]:
        """获取生成的图片"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/history/{prompt_id}") as response:
                if response.status == 200:
                    data = await response.json()

                    images = []
                    if prompt_id in data:
                        outputs = data[prompt_id].get("outputs", {})
                        for node_id, node_output in outputs.items():
                            if "images" in node_output:
                                for img in node_output["images"]:
                                    filename = img.get("filename")
                                    subfolder = img.get("subfolder", "")
                                    img_type = img.get("type", "output")

                                    # 构建图片URL
                                    img_url = f"{self.base_url}/view?filename={filename}&subfolder={subfolder}&type={img_type}"
                                    images.append(img_url)

                    return images
        return []

    async def _download_image(self, url: str, save_path: str) -> bool:
        """下载图片到本地"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    with open(save_path, 'wb') as f:
                        f.write(await response.read())
                    return True
        return False

    async def generate_image(self, request: ImageGenerationRequest) -> GenerationResult:
        """生成图像"""
        try:
            # 检查服务器状态
            status = await self.check_server_status()
            if not status.get("online"):
                return GenerationResult(
                    success=False,
                    error_message="ComfyUI server is not available"
                )

            # 构建工作流
            workflow = self._build_image_workflow(request)

            # 提交任务
            prompt_id = await self._queue_prompt(workflow)

            # 等待完成
            result = await self._wait_for_completion(prompt_id)

            if result.get("status") == "completed":
                # 获取输出图片
                images = await self._get_output_images(prompt_id)

                if images:
                    # 下载第一张图片
                    output_dir = os.path.join("data", "outputs", "images")
                    filename = f"{request.request_id or uuid.uuid4()}.png"
                    save_path = os.path.join(output_dir, filename)

                    if await self._download_image(images[0], save_path):
                        return GenerationResult(
                            success=True,
                            result_path=save_path,
                            result_url=images[0],
                            task_id=prompt_id,
                            credits_used=0,
                            metadata={
                                "all_images": images,
                                "workflow": "default_image"
                            }
                        )

                return GenerationResult(
                    success=False,
                    error_message="No output images found"
                )
            else:
                return GenerationResult(
                    success=False,
                    error_message=result.get("error", "Generation failed")
                )

        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=str(e)
            )

    async def generate_video(self, request: VideoGenerationRequest) -> GenerationResult:
        """生成视频（需要安装视频生成插件）"""
        return GenerationResult(
            success=False,
            error_message="Video generation requires AnimateDiff or similar plugins. Please use image_to_video instead."
        )

    async def image_to_video(self, request: VideoGenerationRequest) -> GenerationResult:
        """图像转视频"""
        try:
            if not request.source_image:
                return GenerationResult(
                    success=False,
                    error_message="Source image is required for I2V"
                )

            # 检查服务器状态
            status = await self.check_server_status()
            if not status.get("online"):
                return GenerationResult(
                    success=False,
                    error_message="ComfyUI server is not available"
                )

            # 检查是否有自定义I2V工作流
            if "i2v" in self._custom_workflows:
                workflow = self._custom_workflows["i2v"].workflow_json
                # 应用参数映射
                # ...
            else:
                workflow = self._build_i2v_workflow(request)

            # 提交任务
            prompt_id = await self._queue_prompt(workflow)

            # 等待完成（视频生成可能需要更长时间）
            result = await self._wait_for_completion(prompt_id, timeout=600)

            if result.get("status") == "completed":
                # 获取输出视频
                # 注意：视频输出的处理方式可能与图片不同
                return GenerationResult(
                    success=True,
                    task_id=prompt_id,
                    credits_used=0,
                    metadata={"workflow": "i2v"}
                )
            else:
                return GenerationResult(
                    success=False,
                    error_message=result.get("error", "I2V generation failed")
                )

        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=str(e)
            )

    async def check_task_status(self, task_id: str) -> Dict[str, Any]:
        """检查任务状态"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/history/{task_id}") as response:
                if response.status == 200:
                    data = await response.json()
                    if task_id in data:
                        return {
                            "status": "completed",
                            "progress": 100,
                            "outputs": data[task_id].get("outputs", {})
                        }
                    else:
                        return {"status": "pending", "progress": 0}
        return {"status": "unknown"}

    async def interrupt_generation(self) -> bool:
        """中断当前生成"""
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/interrupt") as response:
                return response.status == 200

    async def clear_queue(self) -> bool:
        """清空队列"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/queue",
                json={"clear": True}
            ) as response:
                return response.status == 200


# 注册到工厂
ProviderFactory.register("comfyui", ComfyUIProvider)
