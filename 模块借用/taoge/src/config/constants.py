"""
涛割 - 常量定义
包含Prompt模板、动作库、表情库等常量
"""

from typing import Dict, List
from PyQt6.QtGui import QColor


# ================== 动作库 ==================

# 表情库
EXPRESSION_LIBRARY: List[str] = [
    "爱心", "闭眼", "大哭", "担忧", "尴尬", "害羞", "含泪", "基础",
    "尖牙", "奸笑", "惊讶", "开心", "怒骂", "生气", "叹气", "头晕", "星星"
]

# 左手动作库
LEFT_HAND_ACTIONS: List[str] = [
    "插兜", "伏案左", "基础", "接电话", "摸头", "掐腰", "揉眼",
    "伸展", "托腮", "握持", "捂耳朵", "捂嘴左"
]

# 右手动作库
RIGHT_HAND_ACTIONS: List[str] = [
    "出拳", "打招呼", "点破", "端起", "伏案右", "过来", "基础",
    "拍胸", "掐腰", "伸展", "捂耳朵", "捂嘴右", "指点", "指指点点"
]

# 双手动作库
BOTH_HANDS_ACTIONS: List[str] = [
    "抱拳", "合十", "交叉", "结印", "托脸", "戳手指"
]

# 剧情-动作对应库
PLOT_ACTION_MAPPING: Dict[str, Dict[str, str]] = {
    "角色在困惑思考的同时指责他人": {"left_hand": "摸头", "right_hand": "指指点点"},
    "角色自信保证某事的同时显得轻松不在意": {"left_hand": "拍胸", "right_hand": "插兜"},
    "角色在伏案工作时突然拍胸保证或自责": {"left_hand": "伏案左", "right_hand": "拍胸"},
    "角色在自信表达时右手保持中性姿势": {"left_hand": "拍胸", "right_hand": "基础"},
    "角色在接电话时拍胸表示保证或确认": {"left_hand": "拍胸", "right_hand": "接电话"},
    "角色在自信表达后困惑地摸头": {"left_hand": "拍胸", "right_hand": "摸头"},
    "角色在自信表达的同时显得生气或等待": {"left_hand": "拍胸", "right_hand": "掐腰"},
    "角色在疲劳或哭泣时拍胸表示决心": {"left_hand": "拍胸", "right_hand": "揉眼"},
    "角色在放松时拍胸表示自信": {"left_hand": "拍胸", "right_hand": "伸展"},
    "角色在思考时拍胸强调观点": {"left_hand": "拍胸", "right_hand": "托腮"},
    "角色保持中性站立": {"left_hand": "基础", "right_hand": "基础"},
    "角色友好地打招呼": {"left_hand": "基础", "right_hand": "打招呼"},
    "角色揭示真相": {"left_hand": "基础", "right_hand": "点破"},
    "角色召唤他人": {"left_hand": "基础", "right_hand": "过来"},
    "角色开始生气": {"left_hand": "基础", "right_hand": "掐腰"},
    "角色放松身体": {"left_hand": "基础", "right_hand": "伸展"},
    "角色祈祷或表示感谢": {"left_hand": "双手动作：合十", "right_hand": ""},
    "角色行礼或表示敬意": {"left_hand": "双手动作：抱拳", "right_hand": ""},
    "角色施展法术或特殊能力": {"left_hand": "双手动作：结印", "right_hand": ""},
    "角色自信地站立或表示拒绝": {"left_hand": "双手动作：交叉", "right_hand": ""},
    "角色在思考或期待某事": {"left_hand": "双手动作：托脸", "right_hand": ""},
}


# ================== Prompt模板 ==================

# AI标签生成模板
TAG_GENERATION_PROMPT = """
请分析以下字幕内容，提取场景、角色、道具和特效标签。

字幕内容：
{subtitle_text}

要求：
1. 场景标签：描述场景环境（如：办公室、街道、咖啡厅等）
2. 角色标签：出现的角色名称或类型
3. 道具标签：场景中重要的道具物品
4. 特效标签：需要的视觉特效（如：光效、烟雾等）

请以JSON格式返回：
{{
    "场景": ["标签1", "标签2"],
    "角色": ["角色1", "角色2"],
    "道具": ["道具1"],
    "特效": ["特效1"]
}}
"""

# 角色动作分析模板
ACTION_ANALYSIS_PROMPT = """
请分析以下对话内容，推断角色此时的情绪和动作。

对话内容：
{dialogue_text}

可选表情：{expressions}
可选左手动作：{left_actions}
可选右手动作：{right_actions}
可选双手动作：{both_actions}

请以JSON格式返回：
{{
    "表情": "推荐表情",
    "左手动作": "推荐动作",
    "右手动作": "推荐动作",
    "情绪分析": "简短说明"
}}
"""

# 图像生成Prompt模板
IMAGE_GENERATION_PROMPT = """
{style_prefix}

场景：{scene_description}
角色：{character_description}
动作：{action_description}
光线：{lighting}
氛围：{mood}

{additional_notes}
"""

# 视频生成Prompt模板
VIDEO_GENERATION_PROMPT = """
基于以下静态图像生成动态视频：

图像描述：{image_description}
运动类型：{motion_type}
镜头运动：{camera_motion}
持续时间：{duration}秒

关键帧说明：
- 起始帧：{start_frame_description}
- 结束帧：{end_frame_description}
"""


# ================== 标签类别 ==================

TAG_CATEGORIES = ["场景", "角色", "道具", "特效"]

TAG_CATEGORY_COLORS = {
    "场景": "rgba(255, 107, 107, {alpha})",
    "角色": "rgba(78, 205, 196, {alpha})",
    "道具": "rgba(255, 209, 102, {alpha})",
    "特效": "rgba(67, 97, 238, {alpha})"
}

TAG_FONT_COLORS = {
    "场景": "#FFB4B4",
    "角色": "#A3F0EA",
    "道具": "#FFE8A3",
    "特效": "#A3B1FF"
}


# ================== 视频生成参数 ==================

# 支持的视频比例
VIDEO_ASPECT_RATIOS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:3": (1440, 1080),
    "21:9": (2560, 1080),
}

# 运镜类型
CAMERA_MOTIONS = [
    "静止", "推进", "拉远", "左移", "右移",
    "上移", "下移", "环绕", "震动", "跟随"
]

# 运镜枚举（英文标识 + 中文映射）
CAMERA_MOVES = {
    "Static": "静止",
    "PanLeft": "左移",
    "PanRight": "右移",
    "ZoomIn": "推进",
    "ZoomOut": "拉远",
    "TiltUp": "上移",
    "TiltDown": "下移",
    "Truck": "横移",
    "Dolly": "推轨",
    "Orbit": "环绕",
    "Handheld": "手持",
    "Crane": "摇臂",
}

# 运镜冲突规则：相邻两镜运镜组合如果命中规则则报冲突
CAMERA_CONFLICT_RULES = [
    # (前一镜运镜, 后一镜运镜, 冲突等级, 描述)
    ("PanLeft", "PanRight", "error", "左移接右移 — 视线方向突变"),
    ("PanRight", "PanLeft", "error", "右移接左移 — 视线方向突变"),
    ("ZoomIn", "ZoomOut", "warning", "推进接拉远 — 视距急剧变化"),
    ("ZoomOut", "ZoomIn", "warning", "拉远接推进 — 视距急剧变化"),
    ("TiltUp", "TiltDown", "warning", "上移接下移 — 垂直方向突变"),
    ("TiltDown", "TiltUp", "warning", "下移接上移 — 垂直方向突变"),
    ("Orbit", "Orbit", "warning", "连续环绕 — 观众可能眩晕"),
    ("Handheld", "Crane", "warning", "手持接摇臂 — 稳定性落差大"),
]

# AI 连贯性分析 Prompt
AI_CONTINUITY_ANALYSIS_PROMPT = """你是一位资深分镜导演和动画检查师。请分析以下分镜序列的连贯性问题。

分析维度：
1. 运镜连续性 — 相邻运镜是否冲突（如左移接右移）
2. 视线连续性 — 角色注视方向是否跳跃
3. 180度轴线 — 角色左右关系是否反转（越轴）
4. 时长节奏 — 是否有异常的时长跳跃
5. 动势连续性 — 运动方向是否断裂
6. 构图匹配 — 特写→全景是否过渡自然
7. 色调/光照一致性 — 是否有明显的视觉断裂

返回 JSON 数组，每个元素包含：
- scene_index: 问题所在场景序号
- issue: 问题描述（简洁，中文）
- suggestion: 修改建议（简洁，中文）

如果没有发现问题，返回空数组 []。

分镜数据：
"""

# 过渡效果
TRANSITIONS = [
    "淡入淡出", "溶解", "滑动", "缩放",
    "旋转", "黑场", "白场", "擦除"
]


# ================== 模型能力矩阵 ==================

MODEL_CAPABILITIES = {
    "vidu": {
        "image_generation": True,
        "video_generation": True,
        "image_to_video": True,
        "character_consistency": True,
        "max_video_duration": 8,
        "supported_ratios": ["16:9", "9:16", "1:1"],
    },
    "kling": {
        "image_generation": True,
        "video_generation": True,
        "image_to_video": True,
        "character_consistency": True,
        "max_video_duration": 10,
        "supported_ratios": ["16:9", "9:16", "1:1", "4:3"],
    },
    "jimeng": {
        "image_generation": True,
        "video_generation": True,
        "image_to_video": True,
        "character_consistency": False,
        "max_video_duration": 5,
        "supported_ratios": ["16:9", "9:16"],
    },
    "comfyui": {
        "image_generation": True,
        "video_generation": True,
        "image_to_video": True,
        "character_consistency": True,
        "max_video_duration": 60,
        "supported_ratios": ["16:9", "9:16", "1:1", "4:3", "21:9"],
    },
}


# ================== 剪映模板常量 ==================

JIANYING_PLATFORM_INFO = {
    "app_id": 3704,
    "app_source": "lv",
    "app_version": "4.9.0",
    "os": "windows",
    "os_version": "10.0.22000"
}

JIANYING_NEW_VERSION = "107.0.0"
JIANYING_VERSION = 360000


# ================== 文件扩展名 ==================

SUPPORTED_IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')
SUPPORTED_VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
SUPPORTED_AUDIO_EXTENSIONS = ('.mp3', '.wav', '.aac', '.flac', '.ogg')
SUPPORTED_SUBTITLE_EXTENSIONS = ('.srt', '.ass', '.vtt')


# ================== 画布模式常量 ==================

# 画布卡片尺寸
CANVAS_CARD_WIDTH = 200
CANVAS_CARD_HEIGHT = 140
CANVAS_CARD_THUMB_HEIGHT = 90
CANVAS_CARD_CORNER_RADIUS = 8

# 画布布局间距
CANVAS_GRID_SPACING = 30
CANVAS_GRID_PADDING = 30

# 画布缩放限制
CANVAS_ZOOM_MIN = 0.3
CANVAS_ZOOM_MAX = 3.0
CANVAS_ZOOM_STEP = 1.15

# 角色头像显示
CANVAS_MAX_AVATAR_COUNT = 3
CANVAS_AVATAR_SIZE = 20

# 分组矩形
CANVAS_GROUP_PADDING = 15
CANVAS_GROUP_COLORS = [
    QColor(0, 122, 204, 30),   # 蓝色
    QColor(76, 175, 80, 30),   # 绿色
    QColor(255, 152, 0, 30),   # 橙色
    QColor(156, 39, 176, 30),  # 紫色
    QColor(244, 67, 54, 30),   # 红色
]

# 角色提取Prompt
CHARACTER_EXTRACTION_PROMPT = """
请从以下文本中提取所有角色信息。

文本内容：
{text}

要求：
1. 提取所有出现的角色名称
2. 判断角色类型（human/animal/creature/object）
3. 如果能推断外貌特征，请描述

请以JSON数组格式返回：
[
    {{"name": "角色名", "type": "human", "appearance": "外貌描述"}},
    ...
]
"""

# 场景分割Prompt
SCENE_SPLIT_PROMPT = """
请将以下文本内容按照场景分割。每个场景应该是一个相对独立的画面或情节段落。

文本内容：
{text}

要求：
1. 每个场景包含对应的文本内容
2. 保持原文顺序不变
3. 合理分割，每个场景不超过3句话

请以JSON数组格式返回：
[
    {{"scene_text": "场景文本内容", "description": "场景简述"}},
    ...
]
"""

# ================== AI 一键分析 Prompt ==================

# 画面提示词生成（中文输出）
AI_IMAGE_PROMPT_GENERATION = """
请根据以下文案内容，生成用于AI图像生成的详细中文画面描述提示词。

文案内容：
{subtitle_text}

涉及角色：{characters}

要求：
1. 用中文描述一个完整的画面场景
2. 描述应包含：场景环境、人物外貌与姿态、光线氛围、构图方式、画面风格
3. 描述要详细具体，适合作为AI绘画的提示词使用
4. 不要使用英文，全部用中文描述

请以JSON格式返回：
{{
    "image_prompt": "详细的中文画面描述提示词"
}}
"""

# 视频提示词生成（替代原来的运镜分析）
AI_VIDEO_PROMPT_GENERATION = """
请根据以下文案内容和已有画面描述，生成综合性的视频提示词。

文案内容：
{subtitle_text}

已有画面描述：
{image_prompt}

涉及角色：{characters}

请从以下五个维度分析，并生成一段综合性的中文视频提示词：

1. **运镜方式**：推荐最合适的镜头运动方式（如推进、拉远、环绕、跟随等）
2. **景别**：推荐合适的景别（如特写、近景、中景、全景、远景等）
3. **角色动作**：描述角色在视频中应有的动作表现
4. **表情变化**：描述角色的表情变化过程
5. **特效分析**：推荐需要的视觉特效（如光效、粒子、烟雾等）

请以JSON格式返回：
{{
    "video_prompt": "综合性的中文视频提示词（将上述五个维度融合为一段流畅的描述）",
    "camera_motion": "推荐的运镜方式",
    "shot_size": "推荐的景别",
    "character_actions": "角色动作描述",
    "expression_changes": "表情变化描述",
    "vfx_analysis": "特效分析描述"
}}
"""

# 一键全面分析（同时生成画面提示词+视频提示词）
AI_SCENE_FULL_ANALYSIS_PROMPT = """
请根据以下文案内容，进行全面的分镜视觉分析，同时生成画面提示词和视频提示词。

文案内容：
{subtitle_text}

涉及角色：{characters}

请从以下维度分析：

1. **画面提示词**：生成详细的中文画面描述提示词，包含场景环境、人物姿态与表情、光线氛围、构图方式、画面风格
2. **视频提示词**：生成综合性的中文视频提示词，融合运镜、景别、角色动作、表情变化和特效
3. **运镜方式**：推荐最合适的镜头运动方式
4. **景别**：推荐合适的景别
5. **角色动作**：描述角色在视频中的动作表现
6. **表情变化**：描述角色的表情变化过程
7. **特效分析**：推荐需要的视觉特效

请以JSON格式返回：
{{
    "image_prompt": "详细的中文画面描述提示词",
    "video_prompt": "综合性的中文视频提示词",
    "camera_motion": "推荐的运镜方式",
    "shot_size": "推荐的景别",
    "character_actions": "角色动作描述",
    "expression_changes": "表情变化描述",
    "vfx_analysis": "特效分析描述"
}}
"""

# AI角色生成提示词
AI_CHARACTER_GENERATION_PROMPT = """
请从以下文案内容中提取和生成角色信息。

文案内容：
{text}

要求：
1. 提取所有出现的角色
2. 为每个角色生成详细的外貌描述（适合AI绘画使用）
3. 推断角色类型和性格特征

请以JSON数组格式返回：
[
    {{
        "name": "角色名称",
        "character_type": "human/animal/creature/object",
        "appearance": "详细的中文外貌描述（发型、五官、体型、特征等）",
        "clothing": "服装描述",
        "personality": "性格特征"
    }}
]
"""

# AI道具生成提示词
AI_PROP_GENERATION_PROMPT = """
请从以下文案内容中提取场景中涉及的重要道具和物品。

文案内容：
{text}

要求：
1. 提取所有重要的道具、物品、工具、装饰品等
2. 为每个道具生成简短描述
3. 判断道具类型

请以JSON数组格式返回：
[
    {{
        "name": "道具名称",
        "prop_type": "object/vehicle/weapon/food/tool/decoration",
        "description": "道具的简短中文描述",
        "prompt_description": "适合AI绘画的详细道具描述"
    }}
]
"""

# ================== 剧情模式 Prompt ==================

# AI 场景拆分提示词（按物理空间拆分）
AI_STORY_ACT_SPLIT_PROMPT = """
请将以下文本按"场景"拆分。这里的"场景"定义为：故事发生的物理空间/地点。

## 核心原则（必须严格遵守）

1. **场景 = 物理空间**：只有当故事发生的地点/空间发生了变化，才进行拆分。
   - 同一个房间里发生的所有事情（对话、争吵、和好、哭泣）都是同一个场景
   - 同一条街上的追逐、偶遇、交谈都是同一个场景
   - 人物在同一个地方情绪从开心到愤怒，不拆分
   - 人物在同一个地方从聊天变成打架，不拆分

2. **对话中不拆分**：两个或多个角色正在对话时，绝对不能在对话中间拆开，无论对话多长。整段对话必须保留在同一个场景内。

3. **以下情况才拆分**：
   - 地点明确变化（"走出咖啡馆""回到家中""来到公司"）
   - 时间明确跳跃（"第二天""三年后""那天晚上"）
   - 空间切换（闪回、梦境、回忆与现实切换）

4. **以下情况不拆分**：
   - 情绪变化（欢笑→悲伤→愤怒）
   - 话题转换（从聊工作变成聊感情）
   - 动作变化（从坐着变成站起来走动）
   - 新角色加入同一地点的对话

5. **拆分点位置（极其重要）**：场景变化的标志词/句子属于**新场景的开头**，不属于上一个场景的结尾。拆分点必须在场景变化标志词**之前**。

   正确示例：
   原文："他在咖啡馆喝了一杯拿铁。来到街上，他遇到了朋友。"
   ✅ 场景1: "他在咖啡馆喝了一杯拿铁。"
   ✅ 场景2: "来到街上，他遇到了朋友。"

   错误示例：
   ❌ 场景1: "他在咖啡馆喝了一杯拿铁。来到街上，"  ← 错！"来到街上"是新场景
   ❌ 场景2: "他遇到了朋友。"

   再举一例：
   原文："两人在办公室争吵了很久。第二天早上，她独自去了公园散心。"
   ✅ 场景1: "两人在办公室争吵了很久。"
   ✅ 场景2: "第二天早上，她独自去了公园散心。"

   总结：表示"去了某地""来到某处""第二天""走出/走进"等转换词句，永远放在新场景的第一句，不放在上一个场景的最后一句。

原文（共 {total_chars} 字）：
{source_text}

拆分要求：
1. 每个场景对应一个物理空间不变的连续段落
2. 对话过程不能被拆开
3. 拆分点在场景变化标志词之前——标志词属于新场景
4. 为每个场景生成标题（地点+事件，如"咖啡馆——初次见面"）和摘要（不超过100字）
5. 标注节奏标签：钩子（开头吸引）/ 铺垫 / 高潮 / 收束
6. 原文必须被完整覆盖，不遗漏不重叠

请以JSON数组格式返回：
[
    {{
        "title": "场景标题（地点+事件概括）",
        "summary": "该场景发生了什么（不超过100字）",
        "text": "该场景对应的完整原文片段（必须是原文的连续子串）",
        "rhythm_label": "钩子/铺垫/高潮/收束",
        "tags": []
    }}
]
"""

# AI 场次转分镜提示词（大场景→分镜）— 资深分镜导演模式（即梦 Seedance 2.0 适配）
AI_ACT_TO_SHOTS_PROMPT = """
# Role: 资深分镜导演 (AI Storyboard Director)

## 任务
你是一个精通视听语言的分镜导演，专门辅助 AI 视频生成（Jimeng Seedance 2.0）。
你的任务是读取用户提供的"小说场景文本"，将其拆解为一系列**可执行、画面感强、逻辑连贯**的分镜脚本（Shots）。

## 核心思考逻辑 (CoT)
在拆解时，请遵循以下原则：
1. **视觉化翻译 (Visual Translation)**：将心理描写或抽象比喻转化为具体的画面动作。
   * 例子："他心如死灰" -> "特写镜头，面部打光阴暗，眼神失去高光，呆滞地看着前方"。
2. **节奏控制 (Pacing)**：
   * 动作/打斗戏：切分细致，单个镜头时长短（2-4s），强调动感。
   * 情感/空镜戏：镜头连贯，单个镜头时长长（5-10s），强调氛围。
3. **场景环境必填（从原文推断，禁止留空）**：每张分镜都必须**独立判断**该镜头发生的具体地点，填入 `scene_environment`，**绝对不允许为空字符串**。
   **不同分镜如果发生在不同地点，必须填不同的场景，不要盲目复制上一镜的值。**
   * **推断方法**：从原文的地点描写、环境线索、对话暗示中判断——例如原文提到"推开房门"→"场景_卧室"，提到"街上人来人往"→"场景_街道"，提到"在湖边"→"场景_湖边"，提到"花园中"→"场景_花园"，提到"婚房内"→"场景_婚房"
   * 格式：统一使用 "场景_" 前缀 + 地点名，如"场景_客厅"、"场景_雪夜山道"、"场景_湖边"、"场景_花园"、"场景_婚房"
   * 仅当连续镜头确实在同一地点时才复制相同的 scene_environment
   * 空镜（无人物的意向性场景）→ `is_empty_shot: true`，仍需填写具体场景地点
   * 原文完全没有地点线索 → 根据情节内容合理推断一个最可能的地点，不要留空
   * 心理描写/回忆/幻想 → 填写"场景_内心世界"或"场景_回忆"
   * 纯色/抽象场景 → 填写"场景_纯色背景"或"场景_抽象空间"
4. **角色信息完整**：每张分镜中的 `characters` 数组必须详细列出该镜头中出现的每个角色的服装、动作、表情、台词。如果该镜头无人物，`characters` 为空数组。
5. **连贯性备注**：同场景连续分镜必须有 `continuity_note` 保证逻辑连贯。
6. **画面描述必须完整**：`visual_description` 必须明确写出：
   * 出现的每个角色 + 其穿着（格式："[角色名]穿着[角色名的XX服饰]"）
   * 关键道具及其状态
   * 光线特征（来源、色温、方向）
   * 场景环境细节
   * 若画面中无人物 → 写"画面中没有人物，[纯场景描述]"
7. **视频描述结构化**：`video_description` 必须按以下结构组织：
   * [景别]+[镜头运动]
   * 每个角色：动作 + 表情
   * 多人场景：角色间的互动关系和空间关系
   * 整体氛围
   * 有台词时标注谁在说、说话表情

## 拆解规则
1. **去除文学性**：不要保留"仿佛"、"好像"等词，直接描述画面。
2. **镜头术语**：必须使用专业的运镜术语（推、拉、摇、移、跟拍、主观视角、特写、全景）。
3. **资产标记**：为软件识别提供元数据。
   * `[REF_IMG: name]`：表示该镜头需要某角色的定妆照作为首帧/参考。
   * `[REF_VID: action]`：表示该动作复杂，需要用户提供参考视频。

## 输出格式 (JSON)
请输出一个 JSON 数组，每个元素包含以下字段：
- `shot_id`: 序号（从 1 开始）
- `scene_environment`: 场景地点（**必填，禁止为空**。从原文推断这段情节发生在哪里。如"场景_客厅"、"场景_雪夜山道"、"场景_办公室"、"场景_湖边"）
- `visual_description`: 画面描述（生成分镜图用 Prompt）。
  必须包含：①每个角色及服装（"角色名穿着角色名的XX服饰"），②场景环境，③关键道具，④光线特征。
  无人物时写"画面中没有人物，[环境描述]"。
- `video_description`: 视频内容描述。
  结构："[景别]+[镜头运动]，[角色A名]——动作：[X]，表情：[Y]；
  [角色B名]——动作：[X]，表情：[Y]。[互动描述]。氛围：[Z]。"
  有台词时加"台词：「…」（表情）"。
- `shot_size`: 景别（特写/近景/中景/全景/远景）
- `camera_movement`: 运镜指令（如：缓慢推近，镜头右摇）
- `characters`: 角色数组，每个角色包含：
  - `name`: 角色名
  - `clothing_style`: 当前穿着描述
  - `action`: 动作描述
  - `expression`: 面部表情
  - `dialogue`: 台词（无则空字符串）
  - `dialogue_expression`: 说话时的表情（无则空字符串）
- `props`: 出现的道具列表
- `lighting`: 光线描述
- `atmosphere`: 整体氛围
- `continuity_note`: 连贯性备注。必须具体说明：
  承接上一镜某角色的什么姿态/动作/位置，服装/光线/道具有无变化。
  第一个分镜写空字符串。同场景连续分镜不得省略。
- `asset_needs`: 资产需求列表（如 ["Character_A", "Costume_A_破旧披风", "Env_SnowMountain"]）
- `duration`: 预估时长（秒）
- `is_empty_shot`: 是否空镜（布尔值，无人物的意向性场景为 true）
- `interaction_desc`: 角色互动描述。
  多角色同画面时描述空间关系和互动方式。单人或空镜写空字符串。

---

## 示例 (Few-Shot Example)

**输入文本：**
"林冲雪夜上梁山。风雪交加，他提着那杆红缨枪，深一脚浅一脚地走在山道上。突然，前方草丛里窜出一只猛虎，林冲大喝一声，摆开架势。"

**输出：**
[
  {{
    "shot_id": 1,
    "scene_environment": "场景_雪夜山道",
    "visual_description": "全景镜头，大雪纷飞的夜晚，苍茫的雪山山道。林冲穿着林冲的破旧披风，手中提着红缨枪，背影朝画面深处行走。月光照在积雪上反射出冷冽白光，风雪粒子在前景飘过。",
    "video_description": "全景+固定镜头，林冲——动作：在山道上艰难前行，步伐沉重偶尔打滑，表情：坚毅而疲惫。整体氛围：凄凉悲壮。",
    "shot_size": "全景",
    "camera_movement": "固定镜头，风雪粒子特效在前景飘过",
    "characters": [
      {{
        "name": "林冲",
        "clothing_style": "破旧披风",
        "action": "提着红缨枪在雪地上艰难行走",
        "expression": "坚毅而疲惫",
        "dialogue": "",
        "dialogue_expression": ""
      }}
    ],
    "props": ["红缨枪", "积雪"],
    "lighting": "月光从左上方打下，冷白色调，积雪反光",
    "atmosphere": "凄凉悲壮",
    "continuity_note": "",
    "interaction_desc": "",
    "asset_needs": ["Character_LinChong", "Env_SnowMountain"],
    "duration": 5,
    "is_empty_shot": false
  }},
  {{
    "shot_id": 2,
    "scene_environment": "场景_雪夜山道",
    "visual_description": "脚部特写，林冲穿着林冲的破旧披风（仅露出下摆），破旧的靴子踩入厚厚的积雪中，拔出时带起雪块。月光映射下的雪地泛着冷光。",
    "video_description": "特写+跟随镜头，林冲——动作：靴子踩入积雪，缓慢拔出带起雪块，步伐沉重缓慢。氛围：沉重压抑。",
    "shot_size": "特写",
    "camera_movement": "镜头跟随脚步移动 (Tracking Shot)",
    "characters": [
      {{
        "name": "林冲",
        "clothing_style": "破旧披风",
        "action": "艰难的踩雪步伐",
        "expression": "",
        "dialogue": "",
        "dialogue_expression": ""
      }}
    ],
    "props": ["积雪"],
    "lighting": "月光映射下的雪地，冷白色调",
    "atmosphere": "沉重",
    "continuity_note": "承接上一镜林冲的行走姿态和方向，服装不变（破旧披风），月光角度不变",
    "interaction_desc": "",
    "asset_needs": [],
    "duration": 3,
    "is_empty_shot": false
  }},
  {{
    "shot_id": 3,
    "scene_environment": "场景_雪夜山道",
    "visual_description": "画面中没有人物，主观视角（林冲眼中），前方的枯草丛剧烈晃动，一只猛虎猛然扑出，画面具有强烈的冲击感。月光下草丛阴影闪烁。",
    "video_description": "中景+急速推镜头，画面中没有人物。草丛剧烈晃动后猛虎扑出，镜头震动。氛围：惊险紧张。",
    "shot_size": "中景",
    "camera_movement": "急速推镜头 (Zoom In) + 镜头震动",
    "characters": [],
    "props": ["猛虎"],
    "lighting": "月光下阴影闪烁",
    "atmosphere": "惊险紧张",
    "continuity_note": "承接上一镜林冲的主观视角方向，场景环境不变（雪夜山道），月光角度不变",
    "interaction_desc": "",
    "asset_needs": ["Ref_Video_TigerJump"],
    "duration": 2,
    "is_empty_shot": true
  }},
  {{
    "shot_id": 4,
    "scene_environment": "场景_雪夜山道",
    "visual_description": "侧面全景，林冲穿着林冲的破旧披风，迅速侧身下蹲，双手紧握红缨枪指向前方，摆出防御姿态。月光从侧面打光，披风随风飘动。",
    "video_description": "全景+环绕慢动作，林冲——动作：快速侧身下蹲摆出武术防御架势，双手紧握红缨枪，表情：警惕怒目。台词：「喝！」（怒喝）。氛围：紧张对峙。",
    "shot_size": "全景",
    "camera_movement": "慢动作 (Slow Motion)，镜头环绕人物旋转",
    "characters": [
      {{
        "name": "林冲",
        "clothing_style": "破旧披风",
        "action": "侧身下蹲双手紧握红缨枪防御",
        "expression": "警惕怒目",
        "dialogue": "喝！",
        "dialogue_expression": "怒喝"
      }}
    ],
    "props": ["红缨枪"],
    "lighting": "月光侧面打光，冷白色调",
    "atmosphere": "紧张对峙",
    "continuity_note": "承接上一镜猛虎从画面右侧扑出的方向，林冲从行走姿态急速转为防御架势，服装不变（破旧披风），月光角度不变",
    "interaction_desc": "",
    "asset_needs": ["Character_LinChong", "Ref_Video_MartialArts"],
    "duration": 4,
    "is_empty_shot": false
  }}
]

正式开始

请分析下方的"输入文本"，并严格按照上述格式输出分镜 JSON。

输入文本：
{act_text}
"""

# AI 场次标签分析提示词（剧情总结 + 爆点/情绪/冲突分析）
AI_ACT_TAG_ANALYSIS_PROMPT = """
请对以下已拆分好的各场次文本进行深度分析：
1. 为每个场次生成一段剧情总结（1-3句话，概括该场次发生了什么）
2. 为每个场次标注"爆点""情绪""冲突"三个维度的标签

场次列表：
{acts_json}

分析维度说明：
1. **剧情总结**：用1-3句话概括该场次的核心剧情，包括主要人物做了什么、发生了什么事件。
2. **爆点**：该场次是否包含剧情转折、意外揭示、惊人发现、反转等高冲击力内容。有则标注，无则不标。
3. **情绪**：该场次的主导情绪走向——感动、悲伤、欢乐、愤怒、恐惧、紧张、温馨、绝望等。如有明显情绪则标注情绪名称，无明显情绪则不标。
4. **冲突**：该场次是否包含角色间的对立、争吵、对抗、利益冲突、立场分歧等。有则标注，无则不标。

请以JSON数组格式返回，数组长度与输入场次数量一致：
[
    {{
        "act_index": 0,
        "summary": "该场次的剧情总结（1-3句话）",
        "tags": ["爆点", "冲突"],
        "emotion": "愤怒",
        "explosion_detail": "男主发现真相后摔门而去",
        "conflict_detail": "父子间关于去留的激烈争吵",
        "emotion_detail": "从克制到爆发的愤怒递进"
    }}
]

注意：
- summary 字段必须填写，用1-3句话概括剧情
- tags 数组只包含确实存在的标签（"爆点"/"情绪"/"冲突"），不存在则为空数组
- 如果标注了"情绪"，则 emotion 字段填具体情绪名称
- detail 字段是可选的，用一句话描述该标签的具体表现
"""


# ── 资产需求提取 Prompt ──

AI_ASSET_REQUIREMENT_EXTRACTION_PROMPT = """
请从以下分镜列表和源文本中提取所有资产需求，分为四类：角色、场景、道具、照明参考。

## 分镜列表：
{shots_text}

## 源文本（完整剧本）：
{source_text}

## 要求：
1. 从分镜列表中识别所有出现的角色、场景、道具、照明参考
2. 回到源文本获取每个资产的详细信息
3. 相同资产在多个分镜中出现时要合并去重
4. 记录每个资产出现在哪些分镜（scene_indices 列表）
5. **角色衍生形象**：同一角色在不同场景中有不同造型（如换装、年龄变化、外貌变化）时，将变化记录在该角色的 `variants` 数组中。每个 variant 有独立的 `variant_type`（costume_variant=服装变化, age_variant=年龄变化, appearance_variant=外貌变化）、`variant_name`、`variant_description` 和 `scene_indices`。基础角色卡记录角色的默认/主要形象
6. **Visual Anchors**：角色的视觉锚点（如"左眼下方小痣"、"右腕系红绳"等独特外观特征），帮助保持角色一致性
7. **角色按年龄段拆分**：同一角色在不同年龄段出场时（如少年时期和成年时期），作为 `age_variant` 放入该角色的 `variants` 数组中，而不是创建独立角色条目
8. **生成用语规范**：在所有描述中使用简洁清晰的视觉描述语言
9. **照明参考提取**：从分镜文本中提取有视觉参考价值的照明设定。格式为简洁的光线描述（如"月光冷白侧光"、"壁炉暖光"、"霓虹灯冷调"）。只提取有明确视觉特征的照明，通用描述（如"白天"、"夜晚"）放在场景的 time_of_day 中，不单独作为照明条目

## 返回格式（严格 JSON）：
{{
  "characters": [
    {{
      "name": "角色名",
      "age": "年龄（如25岁、约30岁）",
      "age_group": "年龄分段（儿童/少年/青年/中年/老年，必填）",
      "gender": "男/女",
      "hairstyle": "发型描述",
      "hair_color": "发色",
      "body_type": "体型（普通/偏瘦/健壮/丰满等，可为空）",
      "clothing_style": "当前主要穿着描述",
      "visual_anchors": ["左脸刀疤", "右腕系红绳"],
      "role_tag": "定位标签（主角/反派/配角/龙套）",
      "personality": "性格特征",
      "scene_indices": [0, 3, 7],
      "source_excerpt": "源文本中描述该角色的关键片段",
      "variants": [
        {{
          "variant_type": "costume_variant",
          "variant_name": "破旧披风造型",
          "variant_description": "灰色破旧披风，带有尘土痕迹",
          "clothing_style": "灰色破旧披风，内衬单衣",
          "clothing_color": "灰色",
          "scene_indices": [0, 1, 2]
        }},
        {{
          "variant_type": "age_variant",
          "variant_name": "少年时期",
          "variant_description": "15岁少年，面容稚嫩，身材瘦小",
          "scene_indices": [5, 6]
        }},
        {{
          "variant_type": "appearance_variant",
          "variant_name": "受伤状态",
          "variant_description": "额头缠绷带，衣服沾血",
          "scene_indices": [8]
        }}
      ]
    }}
  ],
  "scenes": [
    {{
      "name": "场景名称",
      "location": "地点描述",
      "time_of_day": "时间（白天/夜晚/黄昏/...）",
      "weather": "天气（可为空）",
      "era": "时代",
      "mood": "氛围",
      "scene_indices": [0, 1, 2],
      "source_excerpt": "源文本相关片段"
    }}
  ],
  "props": [
    {{
      "name": "道具名称",
      "description": "道具描述",
      "material": "材质（可为空）",
      "size": "大小（可为空）",
      "usage": "用途",
      "owner": "所属角色（可为空）",
      "scene_indices": [1, 4],
      "source_excerpt": "源文本相关片段"
    }}
  ],
  "lightings": [
    {{
      "name": "照明名称（如: 月光冷白侧光）",
      "light_source": "光源（月光/壁炉/霓虹灯/...）",
      "color_temperature": "色温（冷白/暖黄/中性/...）",
      "direction": "方向（顶部/侧面/逆光/散射/...）",
      "mood_effect": "情绪效果（阴郁/温馨/紧张/...）",
      "time_context": "时间语境（夜晚/黄昏/室内不限/...）",
      "scene_indices": [0, 1, 2],
      "source_excerpt": "源文本相关片段"
    }}
  ],
  "project_meta": {{
    "era": "整体时代背景（古代/现代/未来/架空）",
    "genre": "类型（仙侠/都市/悬疑/...）",
    "total_characters": 5,
    "total_scenes": 8,
    "total_props": 6,
    "total_lightings": 2
  }}
}}
"""

# ── 单个资产搜索补全 Prompt ──

AI_ASSET_SINGLE_SEARCH_PROMPT = """
请在以下源文本和分镜列表中搜索名为"{asset_name}"的{asset_type_label}，提取其所有相关信息。

## 源文本：
{source_text}

## 分镜列表（共 {shots_count} 个分镜）：
{shots_text}

## 要求：
1. 在源文本中搜索所有提及"{asset_name}"的片段
2. 根据资产类型提取结构化属性
3. 逐一检查每个分镜的台词和画面描述，如果该分镜中提及或涉及"{asset_name}"，将其 scene_index 加入 scene_indices 列表
4. 摘录源文本中描述该资产的关键片段

## 属性字段（按资产类型）：
- 角色(character): gender(性别), age(年龄), age_group(年龄段), hairstyle(发型), hair_color(发色), body_type(体型), clothing_style(当前穿着), role_tag(定位:主角/配角/反派/龙套), personality(性格), visual_anchors(视觉锚点列表)
- 场景(scene_bg): location(地点), time_of_day(时间), weather(天气), mood(氛围), era(时代)
- 道具(prop): description(描述), material(材质), size(大小), usage(用途), owner(所属角色)
- 照明(lighting_ref): light_source(光源), color_temperature(色温), direction(方向), mood_effect(情绪效果), time_context(时间语境)

请以JSON格式返回（只返回找到的属性字段，没有信息的字段不要填）：
{{
  "name": "{asset_name}",
  "attributes": {{...}},
  "scene_indices": [0, 3, 7],
  "source_excerpts": ["源文本中相关片段1", "源文本中相关片段2"]
}}

注意：scene_indices 中的数字是分镜列表中的 scene_index 编号，必须是实际出现该资产的分镜编号。

如果源文本中完全没有提及该名称，返回：
{{
  "name": "{asset_name}",
  "attributes": {{}},
  "scene_indices": [],
  "source_excerpts": []
}}
"""
