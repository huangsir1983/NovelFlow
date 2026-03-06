"""
涛割 - 配置管理模块
使用Pydantic进行配置验证和管理
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum


class ModelType(Enum):
    """模型类型枚举"""
    VIDU = "vidu"
    KLING = "kling"
    JIMENG = "jimeng"
    GROK = "grok"
    COMFYUI = "comfyui"
    DEEPSEEK = "deepseek"
    YUNWU = "yunwu"
    GEEK = "geek"


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GenerationMode(Enum):
    """生成模式枚举"""
    IMAGE_ONLY = "image_only"
    VIDEO_ONLY = "video_only"
    IMAGE_TO_VIDEO = "image_to_video"


@dataclass
class CreditSettings:
    """积分配置"""
    balance: float = 1000.0  # 当前积分余额
    warning_threshold: float = 0.8  # 80%使用时预警
    auto_stop_threshold: float = 0.95  # 95%使用时自动停止

    # 各模型单次调用消耗积分
    cost_per_call: Dict[str, float] = field(default_factory=lambda: {
        "vidu_image": 5.0,
        "vidu_video": 20.0,
        "kling_image": 4.0,
        "kling_video": 25.0,
        "jimeng_image": 3.0,
        "jimeng_video": 15.0,
        "deepseek_text": 0.5,
        "comfyui_workflow": 10.0,
    })


@dataclass
class APIConfig:
    """API配置"""
    # DeepSeek配置
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # Vidu配置
    vidu_api_key: str = ""
    vidu_base_url: str = ""

    # Kling配置
    kling_api_key: str = ""
    kling_base_url: str = ""

    # Jimeng配置
    jimeng_api_key: str = ""
    jimeng_base_url: str = ""

    # Grok配置
    grok_api_key: str = ""
    grok_base_url: str = ""

    # 云雾配置（yunwu.ai — 统一密钥，支持 gemini 图片 + sora-2 视频）
    yunwu_api_key: str = ""
    yunwu_base_url: str = "https://yunwu.ai"

    # Geek配置（geekapi — 支持 gemini 图片生成）
    geek_api_key: str = ""
    geek_base_url: str = "https://www.geeknow.top/v1"

    # 图片生成渠道: "geek" 或 "yunwu"，默认 geek
    image_provider: str = "geek"

    # ComfyUI配置
    comfyui_server_url: str = "http://localhost:8188"
    comfyui_enabled: bool = False

    # RunningHub TTS 配置
    runninghub_api_key: str = ""
    runninghub_base_url: str = "https://www.runninghub.cn/openapi/v2"
    runninghub_workflow_path: str = ""
    runninghub_instance_type: str = "default"
    tts_text_node_id: str = "48"
    tts_text_field_name: str = "编辑文本"
    tts_prompt_node_id: str = "49"
    tts_prompt_field_name: str = "编辑文本"
    tts_default_voice_prompt: str = ""


@dataclass
class UISettings:
    """UI配置"""
    theme: str = "dark"
    default_mode: str = "wizard"  # wizard 或 canvas
    language: str = "zh_CN"
    auto_save_interval: int = 20  # 自动保存间隔（秒）
    thumbnail_size: tuple = (100, 100)
    preview_size: tuple = (640, 360)
    canvas_width: int = 1920
    canvas_height: int = 1080


@dataclass
class ExportSettings:
    """导出配置"""
    default_export_path: str = ""
    jianying_font_path: str = "C:/Users/asus/AppData/Local/JianyingPro/apps/5.8.0.11559/Resources/Font/SystemFont/zh-hans.ttf"
    video_fps: int = 30
    video_width: int = 1920
    video_height: int = 1080
    video_format: str = "mp4"

    # 剪映相关
    jianying_version: str = "5.8.0"
    jianying_app_id: int = 3704


@dataclass
class PromptSettings:
    """提示词配置"""
    shot_split_prompt: str = ""  # 分镜拆分提示词，空字符串表示使用默认


@dataclass
class GenerationSettings:
    """生成配置"""
    default_model: str = "vidu"
    max_concurrent_tasks: int = 3
    retry_count: int = 3
    retry_delay: float = 2.0
    timeout: int = 300  # 5分钟超时

    # 场景分割配置
    default_scene_duration: float = 3.5  # 默认场景时长（秒）
    min_scene_duration: float = 2.0
    max_scene_duration: float = 6.0

    # 先图后视频流程
    image_first_workflow: bool = True
    auto_character_consistency: bool = True


@dataclass
class AppSettings:
    """应用主配置"""
    app_name: str = "涛割"
    app_version: str = "1.0.0"

    # 子配置
    credits: CreditSettings = field(default_factory=CreditSettings)
    api: APIConfig = field(default_factory=APIConfig)
    ui: UISettings = field(default_factory=UISettings)
    export: ExportSettings = field(default_factory=ExportSettings)
    generation: GenerationSettings = field(default_factory=GenerationSettings)
    prompts: PromptSettings = field(default_factory=PromptSettings)

    # 路径配置
    data_dir: str = "data"
    cache_dir: str = ".cache"
    materials_dir: str = "materials"
    generated_dir: str = "generated"

    # 激活状态
    is_activated: bool = False
    activation_date: Optional[str] = None
    machine_code: Optional[str] = None


class SettingsManager:
    """配置管理器 - 单例模式"""

    _instance: Optional['SettingsManager'] = None
    _settings: Optional[AppSettings] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._settings is None:
            self._config_file = Path("taoge_settings.json")
            self._settings = self._load_settings()

    @property
    def settings(self) -> AppSettings:
        """获取当前配置"""
        return self._settings

    def _load_settings(self) -> AppSettings:
        """从文件加载配置"""
        if self._config_file.exists():
            try:
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return self._dict_to_settings(data)
            except Exception as e:
                print(f"加载配置失败: {e}")
        return AppSettings()

    def _dict_to_settings(self, data: Dict[str, Any]) -> AppSettings:
        """将字典转换为设置对象"""
        settings = AppSettings()

        # 加载各子配置
        if 'credits' in data:
            settings.credits = CreditSettings(**data['credits'])
        if 'api' in data:
            settings.api = APIConfig(**data['api'])
        if 'ui' in data:
            settings.ui = UISettings(**data['ui'])
        if 'export' in data:
            settings.export = ExportSettings(**data['export'])
        if 'generation' in data:
            settings.generation = GenerationSettings(**data['generation'])
        if 'prompts' in data:
            settings.prompts = PromptSettings(**data['prompts'])

        # 加载顶级配置
        for key in ['app_name', 'app_version', 'data_dir', 'cache_dir',
                    'materials_dir', 'generated_dir', 'is_activated',
                    'activation_date', 'machine_code']:
            if key in data:
                setattr(settings, key, data[key])

        return settings

    def save_settings(self) -> bool:
        """保存配置到文件"""
        try:
            data = {
                'app_name': self._settings.app_name,
                'app_version': self._settings.app_version,
                'credits': asdict(self._settings.credits),
                'api': asdict(self._settings.api),
                'ui': asdict(self._settings.ui),
                'export': asdict(self._settings.export),
                'generation': asdict(self._settings.generation),
                'prompts': asdict(self._settings.prompts),
                'data_dir': self._settings.data_dir,
                'cache_dir': self._settings.cache_dir,
                'materials_dir': self._settings.materials_dir,
                'generated_dir': self._settings.generated_dir,
                'is_activated': self._settings.is_activated,
                'activation_date': self._settings.activation_date,
                'machine_code': self._settings.machine_code,
            }

            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    def update_api_key(self, provider: str, api_key: str) -> None:
        """更新API密钥"""
        key_mapping = {
            'deepseek': 'deepseek_api_key',
            'vidu': 'vidu_api_key',
            'kling': 'kling_api_key',
            'jimeng': 'jimeng_api_key',
            'grok': 'grok_api_key',
            'yunwu': 'yunwu_api_key',
            'geek': 'geek_api_key',
        }
        if provider in key_mapping:
            setattr(self._settings.api, key_mapping[provider], api_key)
            self.save_settings()

    def deduct_credits(self, operation: str, amount: Optional[float] = None) -> bool:
        """扣除积分"""
        if amount is None:
            amount = self._settings.credits.cost_per_call.get(operation, 0)

        if self._settings.credits.balance >= amount:
            self._settings.credits.balance -= amount
            self.save_settings()
            return True
        return False

    def check_credits_warning(self) -> bool:
        """检查是否需要积分预警"""
        initial_balance = 1000.0  # 假设初始积分
        used_ratio = 1 - (self._settings.credits.balance / initial_balance)
        return used_ratio >= self._settings.credits.warning_threshold

    def get_remaining_credits(self) -> float:
        """获取剩余积分"""
        return self._settings.credits.balance


# 全局配置管理器实例
def get_settings() -> AppSettings:
    """获取全局配置"""
    return SettingsManager().settings


def get_settings_manager() -> SettingsManager:
    """获取配置管理器实例"""
    return SettingsManager()
