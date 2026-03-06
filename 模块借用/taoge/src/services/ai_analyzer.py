"""
涛割 - AI 分析服务
可替换的 LLM 提供者架构，支持 DeepSeek 及后续其他大语言模型
"""

import json
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod

from PyQt6.QtCore import QThread, pyqtSignal


class LLMProvider(ABC):
    """LLM 提供者抽象基类 - 后期可替换为其他大语言模型"""

    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """发送对话请求，返回模型响应文本"""
        ...

    @abstractmethod
    def name(self) -> str:
        """提供者名称"""
        ...


class DeepSeekProvider(LLMProvider):
    """DeepSeek LLM 提供者"""

    def __init__(self):
        from config.settings import SettingsManager
        settings = SettingsManager().settings
        self._api_key = settings.api.deepseek_api_key
        self._base_url = settings.api.deepseek_base_url
        self._model = settings.api.deepseek_model

    def name(self) -> str:
        return "DeepSeek"

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        if not self._api_key:
            raise ValueError("未配置DeepSeek API密钥，请在设置中填写")

        from openai import OpenAI

        client = OpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
        )

        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=False,
        )

        content = response.choices[0].message.content.strip()

        # 移除可能的 markdown 代码块标记
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        return content


def get_default_provider() -> LLMProvider:
    """获取默认 LLM 提供者（当前为 DeepSeek，后续可根据配置切换）"""
    return DeepSeekProvider()


class AIAnalysisWorker(QThread):
    """AI 分析工作线程 - 通用"""

    analysis_completed = pyqtSignal(str, dict)  # analysis_type, result_dict
    analysis_failed = pyqtSignal(str, str)      # analysis_type, error_message

    # 分析类型常量
    TYPE_IMAGE_PROMPT = "image_prompt"
    TYPE_VIDEO_PROMPT = "video_prompt"
    TYPE_ALL = "all"  # 一键全部分析
    TYPE_CHARACTER_GENERATE = "character_generate"
    TYPE_PROP_GENERATE = "prop_generate"

    def __init__(self, analysis_type: str, subtitle_text: str,
                 characters: Optional[List[str]] = None,
                 scene_description: str = "",
                 image_prompt: str = ""):
        super().__init__()
        self.analysis_type = analysis_type
        self.subtitle_text = subtitle_text
        self.characters = characters or []
        self.scene_description = scene_description
        self.image_prompt = image_prompt

    def run(self):
        try:
            provider = get_default_provider()

            if self.analysis_type == self.TYPE_ALL:
                self._analyze_all(provider)
            elif self.analysis_type == self.TYPE_IMAGE_PROMPT:
                self._analyze_image_prompt(provider)
            elif self.analysis_type == self.TYPE_VIDEO_PROMPT:
                self._analyze_video_prompt(provider)
            elif self.analysis_type == self.TYPE_CHARACTER_GENERATE:
                self._generate_character(provider)
            elif self.analysis_type == self.TYPE_PROP_GENERATE:
                self._generate_props(provider)
            else:
                self.analysis_failed.emit(self.analysis_type, f"未知的分析类型: {self.analysis_type}")

        except Exception as e:
            self.analysis_failed.emit(self.analysis_type, str(e))

    def _analyze_all(self, provider: LLMProvider):
        """一键分析所有内容（画面提示词+视频提示词）"""
        from config.constants import AI_SCENE_FULL_ANALYSIS_PROMPT

        chars_str = ", ".join(self.characters) if self.characters else "未指定"
        prompt = AI_SCENE_FULL_ANALYSIS_PROMPT.format(
            subtitle_text=self.subtitle_text[:2000],
            characters=chars_str,
        )

        content = provider.chat(
            "你是一个专业的分镜师和视觉导演，擅长将文字描述转化为具体的画面和运镜方案。请用中文回答，严格以JSON格式返回结果，不要包含其他内容。",
            prompt,
        )

        result = json.loads(content)

        if isinstance(result, dict):
            self.analysis_completed.emit(self.TYPE_ALL, result)
        else:
            self.analysis_failed.emit(self.TYPE_ALL, "AI返回格式不正确")

    def _analyze_image_prompt(self, provider: LLMProvider):
        """分析生成画面提示词（中文输出）"""
        from config.constants import AI_IMAGE_PROMPT_GENERATION

        chars_str = ", ".join(self.characters) if self.characters else "未指定"
        prompt = AI_IMAGE_PROMPT_GENERATION.format(
            subtitle_text=self.subtitle_text[:2000],
            characters=chars_str,
        )

        content = provider.chat(
            "你是一个专业的AI图像生成提示词专家。请根据文案内容生成高质量的中文画面描述提示词。请只返回JSON，不要包含其他内容。",
            prompt,
        )

        result = json.loads(content)
        if isinstance(result, dict):
            self.analysis_completed.emit(self.TYPE_IMAGE_PROMPT, result)
        else:
            self.analysis_failed.emit(self.TYPE_IMAGE_PROMPT, "AI返回格式不正确")

    def _analyze_video_prompt(self, provider: LLMProvider):
        """生成视频提示词"""
        from config.constants import AI_VIDEO_PROMPT_GENERATION

        chars_str = ", ".join(self.characters) if self.characters else "未指定"
        prompt = AI_VIDEO_PROMPT_GENERATION.format(
            subtitle_text=self.subtitle_text[:2000],
            image_prompt=self.image_prompt or "暂无",
            characters=chars_str,
        )

        content = provider.chat(
            "你是一个专业的视频导演和运镜师，擅长将文字和画面描述转化为视频拍摄方案。请用中文回答，严格以JSON格式返回结果，不要包含其他内容。",
            prompt,
        )

        result = json.loads(content)
        if isinstance(result, dict):
            self.analysis_completed.emit(self.TYPE_VIDEO_PROMPT, result)
        else:
            self.analysis_failed.emit(self.TYPE_VIDEO_PROMPT, "AI返回格式不正确")

    def _generate_character(self, provider: LLMProvider):
        """从文案生成角色描述"""
        from config.constants import AI_CHARACTER_GENERATION_PROMPT

        prompt = AI_CHARACTER_GENERATION_PROMPT.format(
            text=self.subtitle_text[:3000],
        )

        content = provider.chat(
            "你是一个专业的角色设计师，擅长从文本中提取和创建角色。请用中文回答，严格以JSON数组格式返回结果，不要包含其他内容。",
            prompt,
        )

        result = json.loads(content)
        if isinstance(result, list):
            self.analysis_completed.emit(self.TYPE_CHARACTER_GENERATE, {"characters": result})
        else:
            self.analysis_failed.emit(self.TYPE_CHARACTER_GENERATE, "AI返回格式不正确")

    def _generate_props(self, provider: LLMProvider):
        """从文案提取道具列表"""
        from config.constants import AI_PROP_GENERATION_PROMPT

        prompt = AI_PROP_GENERATION_PROMPT.format(
            text=self.subtitle_text[:3000],
        )

        content = provider.chat(
            "你是一个专业的场景道具设计师，擅长从文本中提取场景道具。请用中文回答，严格以JSON数组格式返回结果，不要包含其他内容。",
            prompt,
        )

        result = json.loads(content)
        if isinstance(result, list):
            self.analysis_completed.emit(self.TYPE_PROP_GENERATE, {"props": result})
        else:
            self.analysis_failed.emit(self.TYPE_PROP_GENERATE, "AI返回格式不正确")


class StoryActSplitWorker(QThread):
    """AI 情节拆分工作线程 - 将长文本拆分为场次(Act)"""

    split_completed = pyqtSignal(list)  # [{"title", "summary", "source_text_range", "rhythm_label", "tags"}]
    split_failed = pyqtSignal(str)      # error_message

    def __init__(self, source_text: str, parent=None):
        super().__init__(parent)
        self.source_text = source_text

    def run(self):
        try:
            from config.constants import AI_STORY_ACT_SPLIT_PROMPT

            provider = get_default_provider()

            # 截取前 8000 字避免超长
            text = self.source_text[:8000]
            prompt = AI_STORY_ACT_SPLIT_PROMPT.format(
                source_text=text,
                total_chars=len(self.source_text),
            )

            content = provider.chat(
                "你是一个专业的影视编剧和场景分析师。"
                "你的任务是按物理空间/地点来拆分文本——只有地点变化或时间跳跃时才分割。"
                "同一个地点内的所有事件（对话、情绪变化、动作）都属于同一个场景，绝不拆开。"
                "对话过程中绝不拆分。"
                "极其重要：拆分点必须在场景变化标志词之前，标志词（如'来到''走进''第二天'）属于新场景的第一句，不属于上一个场景的最后一句。"
                "请用中文回答，严格以JSON数组格式返回结果。",
                prompt,
            )

            result = json.loads(content)
            if isinstance(result, list):
                # 标准化结果
                acts = []
                offset = 0
                source = self.source_text
                for i, item in enumerate(result):
                    act_text = item.get('text', item.get('summary', ''))
                    if not act_text:
                        continue

                    # 在原文中定位该片段的起始位置
                    # 策略1: 用完整文本搜索
                    start = source.find(act_text, offset)
                    if start == -1:
                        # 策略2: 去除首尾空白后搜索
                        stripped = act_text.strip()
                        start = source.find(stripped, offset) if stripped else -1
                    if start == -1:
                        # 策略3: 用前50个字符搜索
                        prefix = act_text.strip()[:50]
                        start = source.find(prefix, offset) if prefix else -1
                    if start == -1:
                        # 策略4: 用前20个字符搜索（更宽松）
                        prefix = act_text.strip()[:20]
                        start = source.find(prefix, offset) if prefix else -1
                    if start == -1:
                        # 策略5: 从头开始搜索（不限offset），避免累积漂移
                        prefix = act_text.strip()[:30]
                        start = source.find(prefix) if prefix else -1
                    if start == -1:
                        # 最终回退: 使用当前 offset
                        start = offset

                    # 尝试在原文中找到该片段的真实结尾
                    # 优先匹配完整文本在原文中的长度
                    end_search = act_text.strip()
                    found_end = source.find(end_search, start)
                    if found_end == start:
                        end = start + len(end_search)
                    else:
                        end = start + len(act_text)

                    acts.append({
                        'title': item.get('title', f'场次 {i + 1}'),
                        'summary': item.get('summary', ''),
                        'source_text_range': [start, end],
                        'rhythm_label': item.get('rhythm_label', ''),
                        'tags': item.get('tags', []),
                    })
                    offset = end

                self.split_completed.emit(acts)
            else:
                self.split_failed.emit("AI返回格式不正确，需要JSON数组")

        except Exception as e:
            self.split_failed.emit(str(e))


class ActToShotsWorker(QThread):
    """AI 分镜拆分工作线程 - 将场次文本拆分为分镜（资深分镜导演模式，即梦 Seedance 2.0 适配）"""

    split_completed = pyqtSignal(int, list)  # act_id, [shot_dict with rich fields]
    split_failed = pyqtSignal(int, str)      # act_id, error_message

    def __init__(self, act_id: int, act_text: str, target_duration: float = 10.0, parent=None):
        super().__init__(parent)
        self.act_id = act_id
        self.act_text = act_text
        self.target_duration = target_duration

    def run(self):
        try:
            from config.constants import AI_ACT_TO_SHOTS_PROMPT
            from config import get_settings

            provider = get_default_provider()

            # 优先使用设置中的自定义提示词，为空则使用默认
            settings = get_settings()
            custom_prompt = ""
            if hasattr(settings, 'prompts') and settings.prompts.shot_split_prompt:
                custom_prompt = settings.prompts.shot_split_prompt

            prompt_template = custom_prompt if custom_prompt else AI_ACT_TO_SHOTS_PROMPT
            prompt = prompt_template.format(
                act_text=self.act_text[:4000],
            )

            content = provider.chat(
                "你是一个精通视听语言的分镜导演，专门辅助 AI 视频生成。"
                "你的任务是将小说场景文本拆解为可执行、画面感强、逻辑连贯的分镜脚本。"
                "请用中文回答，严格以JSON数组格式返回结果，不要包含其他内容。",
                prompt,
            )

            result = json.loads(content)
            if isinstance(result, list):
                shots = []
                for item in result:
                    visual_desc = item.get('visual_description', '')
                    video_desc = item.get('video_description', '')
                    camera_mov = item.get('camera_movement', '静止')
                    action_ref = item.get('action_reference') or ''
                    asset_needs = item.get('asset_needs') or []
                    scene_env = item.get('scene_environment', '')
                    characters = item.get('characters') or []
                    props_list = item.get('props') or []
                    lighting = item.get('lighting', '')
                    atmosphere = item.get('atmosphere', '')
                    continuity_note = item.get('continuity_note', '')
                    is_empty = item.get('is_empty_shot', False)
                    interaction_desc = item.get('interaction_desc', '')

                    # 提取对话（兼容新旧格式）
                    dialogue = item.get('dialogue') or ''
                    if not dialogue and characters:
                        # 从 characters 中提取首个有台词的角色
                        for ch in characters:
                            if ch.get('dialogue'):
                                dialogue = ch['dialogue']
                                break

                    # 景别：优先使用 AI 返回的 shot_size，回退到从描述中提取
                    shot_size = item.get('shot_size', '')
                    if not shot_size:
                        for kw in ['特写', '近景', '中景', '全景', '远景']:
                            if kw in visual_desc:
                                shot_size = kw
                                break

                    # 构建 shot_label
                    shot_label = f"{shot_size}：{visual_desc[:20]}" if shot_size else visual_desc[:25]

                    # 构建 character_actions（写入 Scene 模型）
                    character_actions = []
                    for ch in characters:
                        character_actions.append({
                            'character': ch.get('name', ''),
                            'action': ch.get('action', ''),
                            'expression': ch.get('expression', ''),
                            'dialogue': ch.get('dialogue', ''),
                            'dialogue_expression': ch.get('dialogue_expression', ''),
                            'clothing_style': ch.get('clothing_style', '') or ch.get('costume', ''),
                        })

                    # 构建 visual_prompt_struct — 映射到 Scene 模型的 JSON 字段
                    visual_prompt_struct = {
                        'subject': visual_desc,
                        'action': action_ref,
                        'asset_needs': ', '.join(asset_needs) if asset_needs else '',
                        'camera': camera_mov,
                        'scene_environment': scene_env,
                        'characters': characters,
                        'props': props_list,
                        'lighting': lighting,
                        'atmosphere': atmosphere,
                        'shot_size': shot_size,
                    }

                    # 构建 generation_params 扩展字段
                    generation_params = {}
                    if action_ref:
                        generation_params['action_reference'] = action_ref
                    if asset_needs:
                        generation_params['asset_needs'] = asset_needs

                    # 构建 audio_config
                    audio_config = None
                    if dialogue:
                        audio_config = {
                            'dialogue': dialogue,
                            'narration': '',
                            'sfx': '',
                        }

                    # 构建 continuity_notes
                    continuity_notes = None
                    if continuity_note:
                        continuity_notes = {
                            'prev_shot_note': continuity_note,
                            'state_changes': [],
                            'weather_change': None,
                        }

                    shots.append({
                        # 基础字段
                        'subtitle_text': visual_desc[:200] if visual_desc else '',
                        'duration': item.get('duration', self.target_duration),
                        'shot_label': shot_label,
                        'scene_type': 'normal',
                        # 导演指令字段
                        'image_prompt': visual_desc,
                        'video_prompt': video_desc,
                        'camera_motion': camera_mov,
                        'visual_prompt_struct': visual_prompt_struct,
                        'audio_config': audio_config,
                        'generation_params': generation_params if generation_params else None,
                        # v1.2 增强字段（写入 Scene 模型对应列）
                        'scene_environment': scene_env,
                        'shot_size': shot_size,
                        'character_actions': character_actions if character_actions else None,
                        'atmosphere': atmosphere,
                        'is_empty_shot': is_empty,
                        'continuity_notes': continuity_notes,
                        'interaction_desc': interaction_desc,
                        # 卡片显示用（不写入 Scene 但 dict 会传到 UI）
                        'action_reference': action_ref,
                        'asset_needs': asset_needs,
                        'dialogue': dialogue,
                        'characters': characters,
                        'props': props_list,
                        'lighting': lighting,
                    })

                # ── 后处理：每张分镜独立提取场景 ──
                # AI 经常对所有分镜填同一个场景（错误复制），必须逐张独立判断
                for i, shot in enumerate(shots):
                    # 策略1：从本分镜自身内容提取（优先级最高，覆盖 AI 值）
                    extracted = self._extract_scene_from_description(shot)
                    if extracted:
                        shot['scene_environment'] = extracted
                    elif not shot.get('scene_environment'):
                        # 策略2：AI 也没填 → 向前继承
                        for j in range(i - 1, -1, -1):
                            if shots[j].get('scene_environment'):
                                shot['scene_environment'] = shots[j]['scene_environment']
                                break
                    # 同步到 visual_prompt_struct
                    if shot.get('scene_environment'):
                        vps = shot.get('visual_prompt_struct')
                        if isinstance(vps, dict):
                            vps['scene_environment'] = shot['scene_environment']

                self.split_completed.emit(self.act_id, shots)
            else:
                self.split_failed.emit(self.act_id, "AI返回格式不正确，需要JSON数组")

        except Exception as e:
            self.split_failed.emit(self.act_id, str(e))

    @staticmethod
    def _extract_scene_from_description(shot: dict) -> str:
        """从分镜的多个字段综合推断物理场景地点。

        优先级：画面描述 > 道具/角色动作暗示。
        仅匹配明确的物理地点关键词。
        提取不到返回空字符串（UI 侧不显示标签）。
        统一使用 "场景_" 前缀。
        """
        # 拼接所有可能包含地点线索的文本
        parts = [
            shot.get('image_prompt', ''),
            shot.get('video_prompt', ''),
            shot.get('atmosphere', ''),
        ]
        for p in (shot.get('props') or []):
            if isinstance(p, str):
                parts.append(p)
        for ch in (shot.get('characters') or []):
            if isinstance(ch, dict):
                parts.append(ch.get('action', ''))
        text = ' '.join(parts)

        # ── 地点关键词表（统一 "场景_" 前缀） ──
        # 长词优先，避免 "婚房" 被 "房间" 提前截胡
        place_kw = [
            # 特殊房间（长词优先）
            ('婚房', '场景_婚房'), ('洞房', '场景_婚房'), ('新房', '场景_婚房'),
            ('书房', '场景_书房'), ('卧室', '场景_卧室'), ('闺房', '场景_闺房'),
            ('客厅', '场景_客厅'), ('厨房', '场景_厨房'), ('浴室', '场景_浴室'),
            ('走廊', '场景_走廊'), ('楼梯', '场景_楼梯间'), ('地下室', '场景_地下室'),
            ('地窖', '场景_地窖'), ('阁楼', '场景_阁楼'),
            # 传统/古代建筑
            ('大厅', '场景_大厅'), ('内堂', '场景_内堂'), ('正堂', '场景_正堂'),
            ('密室', '场景_密室'), ('牢房', '场景_牢房'), ('牢笼', '场景_牢笼'),
            ('监狱', '场景_监狱'), ('寝殿', '场景_寝殿'), ('灵堂', '场景_灵堂'),
            ('朝堂', '场景_朝堂'), ('殿内', '场景_宫殿'), ('宫殿', '场景_宫殿'),
            ('祠堂', '场景_祠堂'), ('庙内', '场景_庙宇'), ('庙宇', '场景_庙宇'),
            ('寺庙', '场景_寺庙'), ('教堂', '场景_教堂'),
            # 商业场所
            ('酒馆', '场景_酒馆'), ('客栈', '场景_客栈'), ('茶馆', '场景_茶馆'),
            ('酒楼', '场景_酒楼'), ('饭馆', '场景_饭馆'), ('食堂', '场景_食堂'),
            ('酒吧', '场景_酒吧'), ('餐厅', '场景_餐厅'), ('咖啡', '场景_咖啡厅'),
            ('药铺', '场景_药铺'), ('店铺', '场景_店铺'), ('店内', '场景_店铺'),
            ('商场', '场景_商场'), ('超市', '场景_超市'),
            # 现代建筑
            ('教室', '场景_教室'), ('办公室', '场景_办公室'), ('会议室', '场景_会议室'),
            ('图书馆', '场景_图书馆'), ('体育馆', '场景_体育馆'),
            ('病房', '场景_病房'), ('医院', '场景_医院'), ('手术室', '场景_手术室'),
            ('实验室', '场景_实验室'), ('仓库', '场景_仓库'),
            ('电梯', '场景_电梯'),
            # 交通工具
            ('车内', '场景_车内'), ('车厢', '场景_车厢'), ('驾驶座', '场景_车内'),
            ('船舱', '场景_船舱'), ('机舱', '场景_机舱'), ('船上', '场景_船上'),
            # 临时建筑
            ('帐篷', '场景_帐篷'), ('营帐', '场景_营帐'),
            ('洞穴', '场景_洞穴'), ('山洞', '场景_山洞'),
            # 通用室内（放最后，避免截胡）
            ('室内', '场景_室内'), ('房间', '场景_房间'), ('屋内', '场景_房间'),
            # ── 水域相关（长词优先） ──
            ('湖水', '场景_湖边'), ('湖中', '场景_湖边'), ('湖畔', '场景_湖畔'),
            ('湖边', '场景_湖边'), ('湖面', '场景_湖面'),
            ('河边', '场景_河边'), ('河岸', '场景_河岸'), ('河中', '场景_河边'),
            ('溪边', '场景_溪边'), ('溪流', '场景_溪边'),
            ('海边', '场景_海边'), ('海面', '场景_海面'), ('沙滩', '场景_沙滩'),
            ('水潭', '场景_水潭'), ('池塘', '场景_池塘'), ('水边', '场景_水边'),
            ('瀑布', '场景_瀑布'), ('温泉', '场景_温泉'),
            # 桥/渡
            ('桥上', '场景_桥上'), ('石桥', '场景_石桥'), ('桥头', '场景_桥头'),
            ('码头', '场景_码头'), ('渡口', '场景_渡口'), ('港口', '场景_港口'),
            # 山地
            ('山道', '场景_山道'), ('山路', '场景_山路'), ('山顶', '场景_山顶'),
            ('山脚', '场景_山脚'), ('悬崖', '场景_悬崖'), ('峡谷', '场景_峡谷'),
            ('山谷', '场景_山谷'), ('山坡', '场景_山坡'),
            # 林地
            ('森林', '场景_森林'), ('树林', '场景_树林'), ('竹林', '场景_竹林'),
            ('丛林', '场景_丛林'), ('林间', '场景_林间'),
            # 城镇
            ('街道', '场景_街道'), ('街上', '场景_街道'), ('大街', '场景_街道'),
            ('巷子', '场景_巷子'), ('胡同', '场景_胡同'), ('弄堂', '场景_弄堂'),
            ('集市', '场景_集市'), ('市场', '场景_市场'), ('夜市', '场景_夜市'),
            ('广场', '场景_广场'), ('城门', '场景_城门'), ('城墙', '场景_城墙'),
            # 军事
            ('战场', '场景_战场'), ('校场', '场景_校场'), ('演武场', '场景_演武场'),
            ('军营', '场景_军营'), ('营地', '场景_营地'),
            # 院/园
            ('花园', '场景_花园'), ('庭院', '场景_庭院'), ('院子', '场景_庭院'),
            ('后院', '场景_后院'), ('院落', '场景_院落'), ('天井', '场景_天井'),
            # 旷野
            ('田野', '场景_田野'), ('荒野', '场景_荒野'), ('荒地', '场景_荒地'),
            ('沙漠', '场景_沙漠'), ('戈壁', '场景_戈壁'),
            ('草原', '场景_草原'), ('草地', '场景_草地'), ('草坪', '场景_草坪'),
            ('雪地', '场景_雪地'), ('冰面', '场景_冰面'), ('雪原', '场景_雪原'),
            # 高处
            ('屋顶', '场景_屋顶'), ('天台', '场景_天台'), ('阳台', '场景_阳台'),
            ('露台', '场景_露台'), ('塔顶', '场景_塔顶'), ('城楼', '场景_城楼'),
            # 现代室外
            ('公园', '场景_公园'), ('操场', '场景_操场'), ('停车场', '场景_停车场'),
            ('马路', '场景_马路'), ('公路', '场景_公路'), ('高速', '场景_高速公路'),
            ('铁轨', '场景_铁轨'), ('站台', '场景_站台'), ('月台', '场景_月台'),
            ('机场', '场景_机场'), ('车站', '场景_车站'),
            # 墓/遗
            ('墓地', '场景_墓地'), ('坟场', '场景_坟场'), ('陵墓', '场景_陵墓'),
            ('废墟', '场景_废墟'), ('遗迹', '场景_遗迹'),
        ]
        # 环境物件暗示
        object_hint_kw = [
            ('黑板', '场景_教室'), ('讲台', '场景_教室'), ('课桌', '场景_教室'),
            ('手术台', '场景_手术室'), ('病床', '场景_病房'),
            ('书桌', '场景_书房'), ('书架', '场景_书房'), ('砚台', '场景_书房'),
            ('灶台', '场景_厨房'), ('炉灶', '场景_厨房'),
            ('龙椅', '场景_朝堂'), ('王座', '场景_宫殿'), ('龙榻', '场景_寝殿'),
            ('吧台', '场景_酒吧'), ('柜台', '场景_店铺'),
            ('擂台', '场景_擂台'), ('拳台', '场景_拳台'),
            ('红绸', '场景_婚房'), ('喜烛', '场景_婚房'), ('喜字', '场景_婚房'),
            ('婚礼', '场景_婚礼现场'), ('拜堂', '场景_婚礼现场'),
        ]

        for kw, label in place_kw:
            if kw in text:
                return label
        for kw, label in object_hint_kw:
            if kw in text:
                return label

        return ''


class ActTagAnalysisWorker(QThread):
    """AI 场次标签分析工作线程 — 分析爆点/情绪/冲突"""

    analysis_completed = pyqtSignal(list)  # [{"act_index", "tags", "emotion", ...}]
    analysis_failed = pyqtSignal(str)      # error_message

    def __init__(self, acts_data: list, parent=None):
        """
        Args:
            acts_data: list of dict，每项含 title, summary 或 text 等
        """
        super().__init__(parent)
        self.acts_data = acts_data

    def run(self):
        try:
            from config.constants import AI_ACT_TAG_ANALYSIS_PROMPT

            provider = get_default_provider()

            # 构造简洁的场次列表给 AI
            acts_for_ai = []
            for i, act in enumerate(self.acts_data):
                acts_for_ai.append({
                    'act_index': i,
                    'title': act.get('title', f'场次 {i + 1}'),
                    'text': act.get('text', act.get('summary', ''))[:500],
                })

            prompt = AI_ACT_TAG_ANALYSIS_PROMPT.format(
                acts_json=json.dumps(acts_for_ai, ensure_ascii=False, indent=2),
            )

            content = provider.chat(
                "你是一个专业的影视编剧分析师，擅长分析剧本情节中的爆点、情绪走向和冲突关系。"
                "请用中文回答，严格以JSON数组格式返回结果，不要包含其他内容。",
                prompt,
            )

            result = json.loads(content)
            if isinstance(result, list):
                self.analysis_completed.emit(result)
            else:
                self.analysis_failed.emit("AI返回格式不正确，需要JSON数组")

        except Exception as e:
            self.analysis_failed.emit(str(e))


class AssetRequirementExtractionWorker(QThread):
    """资产需求提取 Worker — 从分镜文本 + 源文本中提取角色/场景/道具/照明需求"""

    extraction_completed = pyqtSignal(dict)   # 完整结果 dict
    extraction_failed = pyqtSignal(str)       # error_message
    extraction_progress = pyqtSignal(str)     # 进度文本

    def __init__(self, shots_data: list, source_text: str, parent=None):
        """
        Args:
            shots_data: 分镜列表，每项含 subtitle_text / image_prompt 等
            source_text: 完整源文本
        """
        super().__init__(parent)
        self.shots_data = shots_data
        self.source_text = source_text

    @staticmethod
    def _clean_json(text: str) -> str:
        """清洗 LLM 返回的 JSON 文本，修复常见格式问题"""
        import re as _re

        s = text.strip()

        # 1. 移除 markdown 代码块标记
        if s.startswith("```"):
            lines = s.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            s = "\n".join(lines).strip()

        # 2. 提取 JSON 对象（从第一个 { 到最后一个 }）
        first_brace = s.find('{')
        last_brace = s.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            s = s[first_brace:last_brace + 1]

        # 3. 修复 JSON 字符串值中的裸换行符
        #    合法 JSON 字符串值不能含未转义的换行，需要替换为 \\n
        #    策略：在 "..." 内部将真实换行替换为 \\n
        result_chars = []
        in_string = False
        escape_next = False
        for ch in s:
            if escape_next:
                result_chars.append(ch)
                escape_next = False
                continue
            if ch == '\\' and in_string:
                result_chars.append(ch)
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                result_chars.append(ch)
                continue
            if in_string and ch == '\n':
                result_chars.append('\\n')
                continue
            if in_string and ch == '\r':
                continue  # 跳过 \r
            if in_string and ch == '\t':
                result_chars.append('\\t')
                continue
            result_chars.append(ch)
        s = ''.join(result_chars)

        # 4. 移除尾随逗号（,] 和 ,}）
        s = _re.sub(r',\s*([}\]])', r'\1', s)

        # 5. 移除字符串外部的单行注释 // ...（字符串感知）
        lines = s.split('\n')
        cleaned_lines = []
        for line in lines:
            out = []
            in_str2 = False
            esc2 = False
            i2 = 0
            while i2 < len(line):
                ch2 = line[i2]
                if esc2:
                    out.append(ch2)
                    esc2 = False
                    i2 += 1
                    continue
                if ch2 == '\\' and in_str2:
                    out.append(ch2)
                    esc2 = True
                    i2 += 1
                    continue
                if ch2 == '"':
                    in_str2 = not in_str2
                    out.append(ch2)
                    i2 += 1
                    continue
                if not in_str2 and ch2 == '/' and i2 + 1 < len(line) and line[i2 + 1] == '/':
                    break  # 丢弃 // 及后面的内容
                out.append(ch2)
                i2 += 1
            cleaned_lines.append(''.join(out))
        s = '\n'.join(cleaned_lines)

        return s

    @staticmethod
    def _try_repair_truncated(text: str) -> Optional[str]:
        """尝试修复被截断的 JSON（AI 输出 token 上限导致不完整）"""
        # 计算未闭合的括号数
        open_braces = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')

        if open_braces <= 0 and open_brackets <= 0:
            return None  # 不是截断问题

        # 找到最后一个完整的条目结尾（}, 或 }]）
        # 然后截断并补全缺失的括号
        s = text.rstrip()

        # 移除可能的不完整字符串值（在引号中间被截断）
        # 从末尾回退找到最后一个不在字符串中的 } 或 ]
        in_str = False
        escape = False
        last_good = -1
        for i, ch in enumerate(s):
            if escape:
                escape = False
                continue
            if ch == '\\' and in_str:
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
            if not in_str and ch in ('}', ']'):
                last_good = i

        if last_good > 0:
            s = s[:last_good + 1]

        # 补齐缺失的括号
        open_braces = s.count('{') - s.count('}')
        open_brackets = s.count('[') - s.count(']')
        s += ']' * max(0, open_brackets)
        s += '}' * max(0, open_braces)

        return s

    def run(self):
        try:
            from config.constants import AI_ASSET_REQUIREMENT_EXTRACTION_PROMPT

            self.extraction_progress.emit("正在分析分镜文本...")

            provider = get_default_provider()

            # 拼接分镜文本
            shots_lines = []
            for i, shot in enumerate(self.shots_data):
                text = shot.get('image_prompt') or shot.get('subtitle_text', '')
                if text:
                    shots_lines.append(f"[分镜 {i}] {text}")
            shots_text = "\n".join(shots_lines)

            # 截取源文本避免超长
            source_text = self.source_text[:6000]

            prompt = AI_ASSET_REQUIREMENT_EXTRACTION_PROMPT.format(
                shots_text=shots_text,
                source_text=source_text,
            )

            self.extraction_progress.emit("AI 正在提取资产需求...")

            content = provider.chat(
                "你是一个专业的影视资产管理师，擅长从剧本和分镜中提取所有视觉资产需求。"
                "你需要识别角色、场景、道具、照明参考四类资产，并详细描述其视觉属性。"
                "角色的服装变化、年龄变化、外貌变化放在角色的 variants 子数组中。"
                "请用中文回答，严格以JSON格式返回结果，不要包含其他内容。"
                "不要在JSON中使用尾随逗号。",
                prompt,
            )

            # 清洗 JSON
            cleaned = self._clean_json(content)

            result = None
            # 第一次尝试：标准清洗后解析
            try:
                result = json.loads(cleaned)
            except json.JSONDecodeError as je1:
                # 打印失败位置附近内容辅助调试
                pos = je1.pos if hasattr(je1, 'pos') else 0
                start = max(0, pos - 100)
                end = min(len(cleaned), pos + 100)
                snippet = cleaned[start:end]
                print(f"[涛割] JSON 第一次解析失败 位置 {pos}:")
                print(f"  ...{repr(snippet)}...")

                # 第1.5次尝试：移除所有 source_excerpt 字段后解析
                import re as _re
                # 策略A：用正则移除 "source_excerpt": "..." 整个键值对
                stripped = _re.sub(
                    r',?\s*"source_excerpt"\s*:\s*"(?:[^"\\]|\\.)*"',
                    '', cleaned
                )
                # 策略B：如果策略A后仍残留 source_excerpt（内部有未转义引号），按行移除
                if '"source_excerpt"' in stripped:
                    lines2 = stripped.split('\n')
                    filtered = []
                    skip_next = False
                    for ln in lines2:
                        if skip_next:
                            stripped_ln = ln.strip()
                            if stripped_ln.endswith('",') or stripped_ln.endswith('"'):
                                skip_next = False
                                continue
                            continue
                        if '"source_excerpt"' in ln:
                            stripped_ln = ln.strip()
                            if stripped_ln.endswith('",') or stripped_ln.endswith('"'):
                                continue
                            else:
                                skip_next = True
                                continue
                        filtered.append(ln)
                    stripped = '\n'.join(filtered)
                # 再清一次尾随逗号
                stripped = _re.sub(r',\s*([}\]])', r'\1', stripped)
                try:
                    result = json.loads(stripped)
                    print("[涛割] 移除 source_excerpt 后解析成功")
                except json.JSONDecodeError as je2:
                    pos2 = je2.pos if hasattr(je2, 'pos') else 0
                    print(f"[涛割] JSON 第二次解析失败 位置 {pos2}")

                    # 第三次尝试：移除所有可能含引号的长字符串字段
                    # 激进地移除 description/appearance/personality 等可能含未转义引号的字段
                    for field in ('description', 'appearance', 'personality',
                                  'source_excerpt', 'prompt_description'):
                        stripped = _re.sub(
                            rf',?\s*"{field}"\s*:\s*"(?:[^"\\]|\\.)*"',
                            '', stripped
                        )
                    stripped = _re.sub(r',\s*([}\]])', r'\1', stripped)
                    try:
                        result = json.loads(stripped)
                        print("[涛割] 移除长文本字段后解析成功")
                    except json.JSONDecodeError:
                        pass

                    # 第四次尝试：修补截断 JSON
                    if result is None:
                        repaired = self._try_repair_truncated(stripped)
                        if repaired:
                            try:
                                result = json.loads(repaired)
                                print("[涛割] 修补截断 JSON 后解析成功")
                            except json.JSONDecodeError:
                                pass

            if result is None:
                print(f"[涛割] 原始内容前 500 字符:\n{content[:500]}")
                self.extraction_failed.emit("JSON 解析失败，AI 返回内容格式异常")
                return

            if isinstance(result, dict):
                self.extraction_progress.emit("提取完成，正在整理结果...")
                self.extraction_completed.emit(result)
            else:
                self.extraction_failed.emit("AI返回格式不正确，需要JSON对象")

        except Exception as e:
            self.extraction_failed.emit(str(e))


class AssetSingleSearchWorker(QThread):
    """单个资产 AI 搜索补全 Worker — 从源文本中搜索指定名称的资产信息"""

    search_completed = pyqtSignal(int, dict)   # (req_id, result)
    search_failed = pyqtSignal(int, str)       # (req_id, error)

    ASSET_TYPE_LABELS = {
        'character': '角色',
        'scene_bg': '场景',
        'prop': '道具',
        'lighting_ref': '照明参考',
    }

    def __init__(self, requirement_id: int, asset_name: str,
                 asset_type: str, source_text: str,
                 shots_text: str = '', parent=None):
        super().__init__(parent)
        self.requirement_id = requirement_id
        self.asset_name = asset_name
        self.asset_type = asset_type
        self.source_text = source_text
        self.shots_text = shots_text

    def run(self):
        try:
            from config.constants import AI_ASSET_SINGLE_SEARCH_PROMPT

            provider = get_default_provider()

            type_label = self.ASSET_TYPE_LABELS.get(self.asset_type, self.asset_type)
            shots_lines = self.shots_text or '（暂无分镜数据）'
            prompt = AI_ASSET_SINGLE_SEARCH_PROMPT.format(
                asset_name=self.asset_name,
                asset_type_label=type_label,
                source_text=self.source_text[:6000],
                shots_text=shots_lines[:8000],
                shots_count=shots_lines.count('【分镜'),
            )

            content = provider.chat(
                "你是一个专业的影视资产管理师，擅长从剧本文本中搜索和提取资产信息。"
                "请用中文回答，严格以JSON格式返回结果，不要包含其他内容。",
                prompt,
            )

            # 清洗 JSON
            cleaned = content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1])

            result = json.loads(cleaned)
            if isinstance(result, dict):
                self.search_completed.emit(self.requirement_id, result)
            else:
                self.search_failed.emit(self.requirement_id, "AI返回格式不正确")

        except Exception as e:
            self.search_failed.emit(self.requirement_id, str(e))
