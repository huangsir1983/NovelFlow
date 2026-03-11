#!/usr/bin/env python3
"""Round 10: Character + Scene Extraction — 3 Modes × 4 Models Benchmark
==========================================================================
Tests:
  Mode A: Sequential (Instruction 1 → Instruction 2, separate API calls)
  Mode B: Combined  (Single prompt, one API call)
  Mode C: Combined + Streaming + Progressive Character Card Export

Models: chatgpt, claude, gemini, grok
Novel: 我和沈词的长子.txt (13,181 chars, GB18030)

Usage:
  py -3.14 run_test_round10.py
  py -3.14 run_test_round10.py --only chatgpt
  py -3.14 run_test_round10.py --mode A,B
  py -3.14 run_test_round10.py --only grok --mode C
"""

import argparse
import asyncio
import io
import json
import os
import re
import sys
import time
from pathlib import Path

# Fix Windows GBK console encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
os.environ["PYTHONIOENCODING"] = "utf-8"

import httpx

# ── Imports from existing infra ─────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from model_adapters import (
    MODEL_REGISTRY, call_api_async,
    ResponsesAPIAdapter, OpenAIChatAdapter,
    _semaphore, MAX_RETRIES, RETRY_WAIT_BASE, RATE_LIMIT_WAIT,
    is_retryable, is_rate_limited,
)

# ── Config ──────────────────────────────────────────────────────
NOVEL_PATH = Path(__file__).parent / "我和沈词的长子.txt"
RESULTS_DIR = Path(__file__).parent / "第10轮测试结果"

MODEL_SHORTCUTS = {
    "chatgpt": "gpt-5.4",
    "claude":  "claude-opus-4-6",
    "gemini":  "gemini",
    "grok":    "grok",
}
DISPLAY_NAMES = {
    "gpt-5.4": "ChatGPT",
    "claude-opus-4-6": "Claude",
    "gemini": "Gemini",
    "grok": "Grok",
}

# ── Custom ChatGPT Adapter (openclaudecode format) ──────────────
class ChatGPTAdapter(OpenAIChatAdapter):
    """ChatGPT adapter matching openclaudecode.cn exact template."""

    async def call(self, system: str, user: str,
                   temperature: float = 0.7,
                   max_tokens: int = 4096) -> tuple[str, dict]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        body = {
            "model": self.model_id,
            "messages": messages,
            "temperature": temperature,
            "top_p": 1,
            "n": 1,
            "stream": False,
            "stop": None,
            "max_tokens": max_tokens,
            "presence_penalty": 0,
            "frequency_penalty": 0,
        }

        last_exc = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with _semaphore:
                    t0 = time.time()
                    async with httpx.AsyncClient(timeout=self.timeout,
                                                  follow_redirects=True) as client:
                        resp = await client.post(
                            f"{self.api_base}/chat/completions",
                            json=body, headers=headers,
                        )
                        resp.raise_for_status()
                    elapsed = time.time() - t0

                resp_body = resp.text
                if not resp_body.strip():
                    raise RuntimeError(f"Empty response from {self.display_name}")

                # Handle SSE format
                if resp_body.lstrip().startswith("data: "):
                    from model_adapters import _parse_sse_to_text
                    text, usage = _parse_sse_to_text(resp_body)
                    inp = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
                    out = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
                    if not inp and not out and text:
                        out = len(text) // 2
                    return text, {"model": self.display_name, "input_tokens": inp,
                                  "output_tokens": out, "elapsed_s": round(elapsed, 2)}

                data = resp.json()
                choices = data.get("choices", [])
                text = choices[0].get("message", {}).get("content", "") if choices else ""
                usage = data.get("usage", {})
                inp = usage.get("prompt_tokens", 0)
                out = usage.get("completion_tokens", 0)
                if not inp and not out and text:
                    out = len(text) // 2
                return text, {"model": self.display_name, "input_tokens": inp,
                              "output_tokens": out, "elapsed_s": round(elapsed, 2)}

            except Exception as e:
                last_exc = e
                if is_rate_limited(e):
                    print(f"\n    ⚠ 429限流 ({self.display_name})，等待 {RATE_LIMIT_WAIT}s...",
                          flush=True)
                    await asyncio.sleep(RATE_LIMIT_WAIT)
                    continue
                if is_retryable(e) or isinstance(e, RuntimeError):
                    if attempt < MAX_RETRIES:
                        wait = RETRY_WAIT_BASE * (attempt + 1)
                        print(f"\n    ⚠ {type(e).__name__} ({self.display_name})，"
                              f"重试 {attempt+1}/{MAX_RETRIES}，等待 {wait}s...",
                              flush=True)
                        await asyncio.sleep(wait)
                        continue
                raise
        raise last_exc


# ── Anthropic Messages API Adapter (/v1/messages) ────────────────
class AnthropicMessagesAdapter(OpenAIChatAdapter):
    """Adapter for Anthropic Messages API format (/v1/messages)."""

    async def call(self, system: str, user: str,
                   temperature: float = 0.7,
                   max_tokens: int = 4096) -> tuple[str, dict]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model_id,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": user}],
        }
        if system:
            body["system"] = system
        if temperature is not None:
            body["temperature"] = temperature

        url = f"{self.api_base}/v1/messages"

        last_exc = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with _semaphore:
                    t0 = time.time()
                    async with httpx.AsyncClient(timeout=self.timeout,
                                                  follow_redirects=True) as client:
                        resp = await client.post(url, json=body, headers=headers)
                        resp.raise_for_status()
                    elapsed = time.time() - t0

                if not resp.text.strip():
                    raise RuntimeError(f"Empty response from {self.display_name}")

                data = resp.json()
                # Anthropic format: {"content": [{"type":"text","text":"..."}]}
                content_blocks = data.get("content", [])
                text = ""
                for block in content_blocks:
                    if block.get("type") == "text":
                        text += block.get("text", "")

                usage = data.get("usage", {})
                return text, {
                    "model": self.display_name,
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                    "elapsed_s": round(elapsed, 2),
                }

            except Exception as e:
                last_exc = e
                if is_rate_limited(e):
                    print(f"\n    ⚠ 429限流 ({self.display_name})，等待 {RATE_LIMIT_WAIT}s...",
                          flush=True)
                    await asyncio.sleep(RATE_LIMIT_WAIT)
                    continue
                if is_retryable(e) or isinstance(e, RuntimeError):
                    if attempt < MAX_RETRIES:
                        wait = RETRY_WAIT_BASE * (attempt + 1)
                        code = getattr(getattr(e, 'response', None),
                                       'status_code', type(e).__name__)
                        print(f"\n    ⚠ {code} ({self.display_name})，"
                              f"重试 {attempt+1}/{MAX_RETRIES}，等待 {wait}s... ({e})",
                              flush=True)
                        await asyncio.sleep(wait)
                        continue
                raise
        raise last_exc


# ── Streaming Responses API call (avoids Cloudflare 524 timeout) ─
async def _call_via_stream(model_name: str, system: str, user: str,
                           temperature: float = 0.5,
                           max_tokens: int = 8192) -> tuple[str, dict]:
    """Call API via streaming to avoid Cloudflare gateway timeout.
    Accumulates full text from SSE chunks."""
    full_text = ""
    t0 = time.time()
    try:
        async for chunk in stream_api_call(
            model_name, system, user, temperature, max_tokens
        ):
            full_text += chunk
    except Exception:
        # If streaming fails, fall back to normal call
        if not full_text:
            return await call_api_async(
                system, user, temperature, max_tokens, model_name
            )
    elapsed = time.time() - t0
    cost = {
        "model": model_name,
        "input_tokens": 0,
        "output_tokens": len(full_text) // 2,  # estimate
        "elapsed_s": round(elapsed, 2),
    }
    return full_text, cost

# Models that need streaming to avoid proxy timeout
_STREAM_REQUIRED_MODELS = {"gpt-5.4", "claude-opus-4-6"}

async def smart_call(model_name: str, system: str, user: str,
                     temperature: float = 0.5,
                     max_tokens: int = 8192) -> tuple[str, dict]:
    """Use streaming for models that timeout otherwise, normal call for rest."""
    if model_name in _STREAM_REQUIRED_MODELS:
        return await _call_via_stream(model_name, system, user,
                                      temperature, max_tokens)
    return await call_api_async(system, user, temperature, max_tokens,
                                model_name)

# ── R10 Model Overrides ─────────────────────────────────────────
# ChatGPT: openclaudecode, Responses API format (proxy requires /v1/responses)
_OCC_KEY = "sk-S2HdTVByFCfJcZ3oM3BUBQio0CGtty7xA2aTHdCP9occt50e"
MODEL_REGISTRY["gpt-5.4"] = ResponsesAPIAdapter(
    api_base="https://www.openclaudecode.cn/v1/responses",
    model_id="gpt-5.4",
    api_key=_OCC_KEY,
    timeout=600,
    display_name="gpt-5.4",
)

# Claude: comfly.chat, OpenAI Chat format (same as R9)
_COMFLY_KEY = "sk-4f5dNlvbRjwcwjsxGeWU2NqY8Yp4u9SaYZUeuAhQVrofzD6R"
MODEL_REGISTRY["claude-opus-4-6"] = OpenAIChatAdapter(
    api_base="https://ai.comfly.chat/v1",
    model_id="claude-opus-4-6",
    api_key=_COMFLY_KEY,
    timeout=600,
    display_name="claude-opus-4-6",
)

# Gemini: yhgcli proxy, gemini-3.1-pro-preview
_GCLI_KEY = "ghitavjlksjkvnklghrvjog"
MODEL_REGISTRY["gemini"] = OpenAIChatAdapter(
    api_base="https://yhgcli.xuhuanai.cn/v1",
    model_id="gemini-3.1-pro-preview",
    api_key=_GCLI_KEY,
    timeout=600,
    display_name="gemini-3.1-pro-preview",
)

# ════════════════════════════════════════════════════════════════
#  PROMPTS — Merged optimal design from 3 approaches
# ════════════════════════════════════════════════════════════════

# ── Instruction 1: 角色设定集 (Character Profile Set) ──────────
INST1_SYSTEM = (
    "你是一位顶级选角导演兼概念设计师，精通影视角色拆解和AI视觉档案构建。\n"
    "分析融合荣格原型理论和角色五维模型（身份/性格/欲望/创伤/能力边界）。\n\n"
    "识别阈值：有名字的角色 + 有独立台词或影响剧情的无名角色。\n"
    "外观描述精度：Stable Diffusion/Midjourney 可直接使用。\n"
    "关系分析：标注功能属性（助攻/镜像/引导/阻碍）。"
)

INST1_USER = """分析以下小说全文，提取所有角色的完整设定档案（Casting档案）。

要求：
1. 识别所有有名角色 + 有独立行为的无名角色
2. 每个角色包含：身份、外貌（AI绘图级）、性格（行为模式）、欲望、缺陷、弧线
3. 角色关系图：标注关系类型和叙事功能
4. 标注每个角色的出场场次概要

返回格式（仅返回JSON数组，不要附加任何解释文字）：
```json
[
  {{
    "name": "角色名",
    "aliases": ["别名"],
    "role": "protagonist|antagonist|supporting|minor",
    "age_range": "年龄范围",
    "appearance": {{
      "face": "面部特征（五官、肤色、标志表情）",
      "body": "体型（身高、体态）",
      "hair": "发型发色",
      "distinguishing_features": "最高辨识度特征"
    }},
    "costume": {{
      "typical_outfit": "典型着装",
      "color_palette": ["主色调1", "主色调2"]
    }},
    "casting_tags": ["选角关键词"],
    "visual_reference": "一句话英文AI绘图提示词(含年龄/外貌/服装/气质)",
    "personality": "核心性格（具体行为模式描述）",
    "desire": "核心欲望（具体化行为目标）",
    "flaw": "致命缺陷",
    "arc": "弧线（起点→转变→终点）",
    "scene_presence": "出场概要（出现在哪些关键情节中）",
    "relationships": [
      {{"target": "角色名", "type": "利益|情感|权力|对照", "dynamic": "张力描述", "function": "叙事功能"}}
    ]
  }}
]
```

小说全文：
---
{text}
---"""

# ── Instruction 2: 语义切场 (Semantic Scene Splitting) ─────────
INST2_SYSTEM = (
    "你是一位资深副导演（1st AD）和场记，按好莱坞标准制片流程执行场景拆解。\n\n"
    "核心原则：\n"
    "- 完全无视原小说章节划分，按语义切场（Semantic Chunking）\n"
    "- 切场依据：时间跳跃、空间转换、视角切换、情绪峰谷交替\n"
    "- 场景最小单位：一个连续时空中的戏剧动作单元\n"
    "- 每场必须有明确戏剧目的（推情节/揭角色/建氛围/造转折）\n"
    "- 对话提取保留潜台词层"
)

INST2_USER = """对以下小说全文执行语义切场（Semantic Chunking）。

关键规则：
- 完全无视原文章节划分，纯粹按时间-空间-情绪转换切场
- 每场是一个「连续时空+单一戏剧动作单元」
- 为每场标注：时空标签、在场角色、核心事件、情绪峰值、预计时长

已知角色列表（在characters_present中使用这些一致的名字）：
{character_names}

返回格式（仅返回JSON数组，不要附加任何解释文字）：
```json
[
  {{
    "scene_id": "scene_001",
    "heading": "INT/EXT. 地点 - 时间",
    "location": "具体地点",
    "time_of_day": "day|night|dawn|dusk",
    "characters_present": ["角色1", "角色2"],
    "core_event": "一句话核心事件描述",
    "key_dialogue": "最关键的一句台词（若有）",
    "emotional_peak": "场景中最强烈的情绪",
    "tension_score": 0.5,
    "estimated_duration_s": 60,
    "key_props": ["关键道具"],
    "dramatic_purpose": "推情节|揭角色|建氛围|造转折"
  }}
]
```

小说全文：
---
{text}
---"""

# ── Combined: Characters + Scenes in One Pass ──────────────────
COMBINED_SYSTEM = (
    "你是一位资深制片主任，同时精通选角和场景拆解。\n"
    "你的任务分两步执行，在同一次输出中完成：\n"
    "1. 第一步：以选角导演视角提取全剧角色设定集\n"
    "2. 第二步：以副导演视角执行语义切场（无视原文章节，按时空+情绪切分）\n\n"
    "角色外观精度：AI绘图可直接使用。\n"
    "切场原则：时间跳跃/空间转换/视角切换/情绪峰谷 = 新场景。\n\n"
    "重要：先输出完整的角色数组，再输出完整的场景数组，合在一个JSON对象中。\n"
    "场景必须按故事发生的时间顺序排列，每个场景是一个独立的叙事事件。\n"
    "同一个地点如果发生了不同的事件，应该拆分为多个场景。\n"
    "场景数组中每个场景的 key_props 要尽量详细列出所有可见道具。\n"
    "每个场景必须包含 order 字段（从0开始的整数），标记其在时间线上的位置。"
)

COMBINED_USER = """对以下小说全文执行两步分析，在一个JSON对象中输出：

第一步 — 角色设定集：
- 识别所有有名角色 + 有独立行为的无名角色
- 每个角色：身份、外貌（AI绘图级）、性格、欲望、缺陷、弧线、关系、出场概要

第二步 — 语义切场：
- 完全无视原文章节，按时间-空间-情绪切场
- 每场：时空标签、在场角色（使用第一步中的角色名）、核心事件、情绪峰值、张力分数、预计时长

返回格式（仅返回一个JSON对象，不要附加任何解释文字）：
```json
{{
  "characters": [
    {{
      "name": "角色名",
      "aliases": ["别名"],
      "role": "protagonist|antagonist|supporting|minor",
      "age_range": "年龄范围",
      "appearance": {{
        "face": "面部特征",
        "body": "体型",
        "hair": "发型发色",
        "distinguishing_features": "最高辨识度特征"
      }},
      "costume": {{
        "typical_outfit": "典型着装",
        "color_palette": ["主色调1", "主色调2"]
      }},
      "casting_tags": ["选角关键词"],
      "visual_reference": "英文AI绘图提示词",
      "personality": "核心性格",
      "desire": "核心欲望",
      "flaw": "致命缺陷",
      "arc": "弧线",
      "scene_presence": "出场概要",
      "relationships": [
        {{"target": "角色名", "type": "类型", "dynamic": "张力描述", "function": "叙事功能"}}
      ]
    }}
  ],
  "scenes": [
    {{
      "scene_id": "scene_001",
      "order": 0,
      "heading": "INT/EXT. 地点 - 时间",
      "location": "具体地点",
      "time_of_day": "day|night|dawn|dusk",
      "characters_present": ["角色1", "角色2"],
      "core_event": "核心事件",
      "key_dialogue": "最关键台词",
      "emotional_peak": "情绪峰值",
      "tension_score": 0.5,
      "estimated_duration_s": 60,
      "key_props": ["关键道具1", "关键道具2", "尽量列出所有可见道具"],
      "dramatic_purpose": "戏剧功能"
    }}
  ]
}}
```

小说全文：
---
{text}
---"""


# ── Location Card Prompts (Stage 2A) ──────────────────────────
LOCATION_CARD_SYSTEM = (
    "你是一位影视美术指导，精通场景设计和 AI 视觉档案构建。\n"
    "你需要为每个拍摄地点生成精确的视觉描述，使其可直接用于 AI 绘图生成一致的场景图。\n"
    "重点关注：建筑风格、空间布局、装饰细节、光线氛围、色彩基调。\n"
    "所有输出严格JSON格式，不要输出其他内容。"
)

LOCATION_CARD_USER = """为以下拍摄地点生成视觉档案。

每个地点在故事中出现的场景汇总：
{location_groups_json}

小说相关段落（供参考环境描写）：
{relevant_text_snippets}

返回JSON数组，每个地点一个对象：
[
  {{
    "location_id": "loc_001",
    "name": "地点名",
    "type": "interior|exterior|mixed",
    "era_style": "时代风格（年代+建筑类型）",
    "description": "详细环境描述（建筑结构/装饰/家具/摆设/空间感）",
    "visual_reference": "English AI art prompt, detailed, specific architectural style and era",
    "atmosphere": "整体氛围关键词",
    "color_palette": ["主色调1", "主色调2", "主色调3"],
    "lighting": "光线特征描述",
    "key_features": ["标志性视觉元素1", "元素2", "元素3"],
    "narrative_scenes": ["scene_001", "scene_007"],
    "scene_count": 2,
    "time_variations": ["day", "night"],
    "emotional_range": "场景跨度的情绪变化"
  }}
]

规则：
1. description 必须包含空间结构、装饰细节、家具布局等具体视觉信息
2. visual_reference 必须是英文，适合直接喂给 Midjourney/DALL-E
3. era_style 要尽量具体（如"明代中晚期官宦府邸"而非笼统的"古代中国"）
4. color_palette 最少 3 个色调
5. key_features 是该地点最具辨识度的视觉元素
6. emotional_range 描述该地点在不同场景中承载的情绪跨度
"""

# ── Prop Card Prompts (Stage 2C) ──────────────────────────────
PROP_CARD_SYSTEM = (
    "你是一位影视道具设计师，精通叙事道具设计和 AI 视觉档案构建。\n"
    "你需要为每个道具生成精确的视觉描述，使其可直接用于 AI 绘图生成一致的道具图。\n"
    "所有输出严格JSON格式，不要输出其他内容。"
)

PROP_CARD_USER = """为以下重要道具生成视觉档案。

道具列表及出场场景：
{prop_list_with_scenes}

小说相关段落（供参考）：
{relevant_text_snippets}

返回JSON数组，每个道具一个对象：
[
  {{
    "name": "道具名",
    "category": "costume|weapon|furniture|document|food|container|symbolic|jewelry|stationery|medical",
    "description": "外观描述（材质、颜色、尺寸、工艺细节）",
    "visual_reference": "English AI art prompt, detailed, specific style and era",
    "narrative_function": "叙事功能（推动情节 / 揭示角色 / 建立象征 / 承载情感）",
    "is_motif": true,
    "scenes_present": ["scene_001", "scene_005"],
    "emotional_association": "与此道具关联的核心情感"
  }}
]

规则：
1. description 必须包含材质、颜色、尺寸、做工等具体视觉信息
2. visual_reference 必须是英文，适合直接喂给 Midjourney/DALL-E
3. narrative_function 要结合小说上下文分析
4. is_motif 只有反复出现且承载象征意义的道具才为 true
"""

# ── Character Variant Prompts (Stage 3) ───────────────────────
VARIANT_SYSTEM = (
    "你是一位角色概念设计师，基于主设定形象为角色创建不同状态/时期/风格的衍生形象。\n"
    "每个变体需要标注对应出场场景和与主设定的差异。\n"
    "所有输出严格JSON格式，不要输出其他内容。"
)

VARIANT_USER = """基础角色设定：
{character_card_json}

该角色出场的所有叙事场景：
{character_scenes_json}

分析该角色在不同场景中的状态变化，生成衍生形象。

规则：
1. 只生成有明确文本依据的变体（不要凭空创造）
2. 每个变体标注具体差异和对应场景
3. visual_reference 必须能直接用于 AI 绘图
4. 至少生成 2 个变体，最多 6 个

返回JSON数组：
[
  {{
    "variant_id": "char_name_variant_01",
    "variant_type": "childhood|wedding|pregnant|injured|formal|casual|battle|aged|disguised|emotional_state",
    "variant_name": "高令宁 — 少女时期",
    "tags": ["少女", "未嫁", "活泼"],
    "scene_ids": ["scene_001", "scene_003"],
    "trigger": "出场背景描述（何时何地出现这个状态）",
    "appearance_delta": {{
      "face": "与主设定的面部差异（如更年轻、更憔悴）",
      "body": "体型差异",
      "hair": "发型差异",
      "distinguishing_features": "此状态的标志特征"
    }},
    "costume_override": {{
      "outfit": "此状态的具体着装",
      "color_palette": ["色调1", "色调2"]
    }},
    "visual_reference": "English AI art prompt for this specific variant, detailed",
    "emotional_tone": "此变体的核心情绪基调"
  }}
]"""


# ════════════════════════════════════════════════════════════════
#  Utilities
# ════════════════════════════════════════════════════════════════

def extract_json(raw: str):
    """Extract JSON from model response (handles thinking tags, code blocks)."""
    # Strip <think> tags — replace with space to avoid breaking JSON strings
    text = re.sub(r'<think>[\s\S]*?</think>', ' ', raw)
    text = re.sub(r'\[Agent\s*\d*\]\[AgentThink\][\s\S]*?\[/AgentThink\]', ' ', text)

    # Extract from code blocks (prefer the LAST one — actual output is at end)
    blocks = list(re.finditer(r'```(?:json)?\s*([\s\S]*?)```', text))
    if blocks:
        text = blocks[-1].group(1).strip()
    else:
        text = text.strip()

    # Clean control chars that break JSON parsing (except \n\r\t)
    def _clean_json_str(s: str) -> str:
        """Remove bare newlines inside JSON string values."""
        # Replace literal newlines not preceded by backslash inside strings
        # Simple approach: try as-is first, if fail then clean up
        return s

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fix 1: bare newlines inside JSON strings (from think-tag stripping)
    cleaned = text
    for _ in range(10):
        prev = cleaned
        cleaned = re.sub(r'("(?:[^"\\]|\\.)*?)\n((?:[^"\\]|\\.)*?")',
                         r'\1 \2', cleaned)
        if cleaned == prev:
            break
    # Fix 2: broken numbers from think-tag stripping (e.g. "0  .65" → "0.65")
    cleaned = re.sub(r'(\d)\s+\.(\d)', r'\1.\2', cleaned)
    # Fix 3: extra spaces around colons/commas in values
    cleaned = re.sub(r':\s{2,}', ': ', cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback: find first [ or { in cleaned text
    for src in [cleaned, text]:
        for i, ch in enumerate(src):
            if ch in '[{':
                remainder = src[i:]
                try:
                    return json.loads(remainder)
                except json.JSONDecodeError:
                    end_ch = ']' if ch == '[' else '}'
                    last = remainder.rfind(end_ch)
                    if last > 0:
                        try:
                            return json.loads(remainder[:last+1])
                        except json.JSONDecodeError:
                            pass
                break  # Only try first bracket per source

    # Truncation repair: try to close incomplete JSON by brute-force
    for src in [cleaned, text]:
        for i, ch in enumerate(src):
            if ch in '{':
                remainder = src[i:]
                # Try adding closing brackets
                for suffix in ['}]}', ']}', '}]}}', ']}}', '}}']:
                    try:
                        return json.loads(remainder + suffix)
                    except json.JSONDecodeError:
                        pass
                # Last resort: extract complete objects from partial array
                try:
                    partial = _extract_partial_json(remainder)
                    if partial:
                        return partial
                except Exception:
                    pass
                break

    raise ValueError(f"Cannot extract JSON (len={len(raw)}, preview={raw[:200]!r})")


def _extract_partial_json(text: str) -> dict | None:
    """Extract characters and scenes from truncated JSON."""
    result = {}
    # Find characters array
    m = re.search(r'"characters"\s*:\s*\[', text)
    if m:
        chars = _extract_complete_objects(text, m.end())
        if chars:
            result["characters"] = chars
    # Find scenes array
    m = re.search(r'"scenes"\s*:\s*\[', text)
    if m:
        scenes = _extract_complete_objects(text, m.end())
        if scenes:
            result["scenes"] = scenes
    return result if result else None


def _extract_complete_objects(text: str, start: int) -> list:
    """Extract all complete JSON objects from an array starting at `start`."""
    pos = start
    found = []
    while pos < len(text):
        while pos < len(text) and text[pos] in ' \t\n\r,':
            pos += 1
        if pos >= len(text) or text[pos] == ']':
            break
        if text[pos] != '{':
            pos += 1
            continue
        depth = 0
        in_str = False
        esc = False
        obj_start = pos
        found_end = False
        for j in range(pos, len(text)):
            c = text[j]
            if esc:
                esc = False
                continue
            if c == '\\' and in_str:
                esc = True
                continue
            if c == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[obj_start:j+1])
                        found.append(obj)
                    except json.JSONDecodeError:
                        pass
                    pos = j + 1
                    found_end = True
                    break
        if not found_end:
            break
    return found


class ProgressiveAssetParser:
    """Multi-phase progressive parser — scans characters → scenes arrays in order.

    Expected format: {"characters": [{...}, {...}], "scenes": [{...}, {...}]}
    Yields individual character/scene objects as they complete during streaming.
    Handles <think> tags interleaved in streaming output.

    Key design: scenes are NARRATIVE SCENES (ordered story events), not locations.
    The same location may appear in multiple scenes with different events.
    """

    def __init__(self):
        self.buffer = ""
        self.found_chars = []       # Extracted character objects
        self.found_scenes = []      # Extracted narrative scene objects
        self._chars_closed = False  # characters array closed?
        self._scenes_closed = False # scenes array closed?
        self._scan_pos = 0         # Incremental scan position

        # Current array scanning state
        self._in_array = False
        self._array_key = None     # "characters" or "scenes"
        self._obj_start = -1
        self._depth = 0

    def feed(self, chunk: str) -> dict:
        """Feed a streaming chunk, return newly discovered assets.

        Returns:
            {"characters": [...new_chars], "scenes": [...new_scenes]}
        """
        self.buffer += chunk
        self.buffer = self._clean(self.buffer)
        result = {"characters": [], "scenes": []}

        if not self._chars_closed:
            new_chars = self._scan_array("characters")
            result["characters"] = new_chars
            self.found_chars.extend(new_chars)

        if self._chars_closed and not self._scenes_closed:
            new_scenes = self._scan_array("scenes")
            result["scenes"] = new_scenes
            self.found_scenes.extend(new_scenes)

        return result

    def _scan_array(self, key: str) -> list[dict]:
        """Generic array scanner — find complete JSON objects from _scan_pos."""
        found = []
        buf = self.buffer
        pos = self._scan_pos

        while pos < len(buf):
            ch = buf[pos]

            if not self._in_array:
                marker = f'"{key}"'
                idx = buf.find(marker, pos)
                if idx < 0:
                    break
                bracket_pos = buf.find('[', idx + len(marker))
                if bracket_pos < 0:
                    break
                self._in_array = True
                self._array_key = key
                pos = bracket_pos + 1
                continue

            # Inside array — track { } depth
            if ch == '{':
                if self._depth == 0:
                    self._obj_start = pos
                self._depth += 1
            elif ch == '}':
                self._depth -= 1
                if self._depth == 0 and self._obj_start >= 0:
                    obj_str = buf[self._obj_start:pos + 1]
                    obj_str = self._fix_json_str(obj_str)
                    try:
                        obj = json.loads(obj_str, strict=False)
                        found.append(obj)
                    except json.JSONDecodeError:
                        pass
                    self._obj_start = -1
            elif ch == ']' and self._depth == 0:
                # Array closed
                self._in_array = False
                self._array_key = None
                if key == "characters":
                    self._chars_closed = True
                elif key == "scenes":
                    self._scenes_closed = True
                pos += 1
                break
            pos += 1

        self._scan_pos = pos
        return found

    @staticmethod
    def _clean(text: str) -> str:
        """Strip think tags + handle unclosed tags in streaming."""
        text = re.sub(r'<think>[\s\S]*?</think>', '', text)
        text = re.sub(r'\[Agent\s*\d*\]\[AgentThink\][\s\S]*?\[/AgentThink\]', '', text)
        text = re.sub(r'\[Agent \d+\]\[AgentThink\][^\n]*\n?', '', text)
        idx = text.rfind('<think>')
        if idx >= 0 and '</think>' not in text[idx:]:
            text = text[:idx]
        return text

    @staticmethod
    def _fix_json_str(s: str) -> str:
        """Fix bare newlines and broken numbers in JSON string."""
        fixed = s
        for _ in range(10):
            prev = fixed
            fixed = re.sub(
                r'("(?:[^"\\]|\\.)*?)\n((?:[^"\\]|\\.)*?")',
                r'\1 \2', fixed)
            if fixed == prev:
                break
        fixed = re.sub(r'(\d)\s+\.(\d)', r'\1.\2', fixed)
        return fixed


# Keep old parser as alias for backward compat with Mode C fallback
ProgressiveCharacterParser = ProgressiveAssetParser


# ════════════════════════════════════════════════════════════════
#  Pipeline Utilities
# ════════════════════════════════════════════════════════════════

def safe_filename(name: str) -> str:
    """Sanitize a string for use as a filename component."""
    name = re.sub(r'[\\/:*?"<>|\s]+', '_', name)
    return name.strip('_')[:50] or 'unnamed'


def save_json(directory: Path, filename: str, data):
    """Write JSON data to directory/filename."""
    filepath = directory / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_text(directory: Path, filename: str, text: str):
    """Write plain text to directory/filename."""
    filepath = directory / filename
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)


def ensure_dir(base: Path, subdir: str) -> Path:
    """Create and return base/subdir."""
    d = base / subdir
    d.mkdir(parents=True, exist_ok=True)
    return d


def now_iso() -> str:
    """Return current timestamp in ISO format."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# ════════════════════════════════════════════════════════════════
#  Stage 2A: Location Asset Card Generation
# ════════════════════════════════════════════════════════════════

def group_scenes_by_location(narrative_scenes: list[dict]) -> dict:
    """Group narrative scenes by location, collect visual cues.

    Returns dict keyed by location name with aggregated info.
    """
    from collections import defaultdict

    groups = defaultdict(lambda: {
        "scene_ids": [],
        "time_variations": set(),
        "all_props": set(),
        "all_characters": set(),
        "events": [],
        "emotional_peaks": [],
    })

    for scene in narrative_scenes:
        loc = scene.get("location", "未知地点")
        g = groups[loc]
        g["scene_ids"].append(scene.get("scene_id", ""))
        g["time_variations"].add(scene.get("time_of_day", ""))
        g["all_props"].update(scene.get("key_props", []))
        g["all_characters"].update(scene.get("characters_present", []))
        g["events"].append(scene.get("core_event", ""))
        g["emotional_peaks"].append(scene.get("emotional_peak", ""))

    # Convert sets to sorted lists for JSON serialization
    result = {}
    for loc, g in groups.items():
        result[loc] = {
            "scene_ids": g["scene_ids"],
            "time_variations": sorted(g["time_variations"]),
            "all_props": sorted(g["all_props"]),
            "all_characters": sorted(g["all_characters"]),
            "events": g["events"],
            "emotional_peaks": g["emotional_peaks"],
        }
    return result


async def generate_location_cards(narrative_scenes, novel, model_key,
                                   out_dir) -> list[dict]:
    """Stage 2A: Generate location asset cards from grouped narrative scenes."""
    locations_dir = ensure_dir(out_dir, "locations")

    # Step 1: Group by location
    groups = group_scenes_by_location(narrative_scenes)
    print(f"    地点分组: {len(groups)} 个唯一地点")

    if not groups:
        print(f"    无地点信息，跳过场景资产卡生成")
        return [], {"model": model_key, "input_tokens": 0, "output_tokens": 0, "elapsed_s": 0}

    # Step 2: Collect relevant novel snippets
    snippets = []
    for loc_name in groups:
        for m in re.finditer(re.escape(loc_name), novel):
            start = max(0, m.start() - 150)
            end = min(len(novel), m.end() + 150)
            snippets.append(f"[{loc_name}] ...{novel[start:end]}...")
            if len(snippets) >= 30:
                break
        if len(snippets) >= 30:
            break

    # Step 3: AI generation
    groups_json = json.dumps(groups, ensure_ascii=False, indent=2)

    resp, cost = await smart_call(
        model_key,
        LOCATION_CARD_SYSTEM,
        LOCATION_CARD_USER.format(
            location_groups_json=groups_json,
            relevant_text_snippets="\n".join(snippets[:30]),
        ),
        temperature=0.5,
        max_tokens=8192,
    )

    location_cards = []
    try:
        cards = extract_json(resp)
        if not isinstance(cards, list):
            cards = [cards]

        for i, card in enumerate(cards):
            loc_id = card.get("location_id", f"loc_{i+1:03d}")
            if not card.get("location_id"):
                card["location_id"] = loc_id
            name = card.get("name", f"unnamed_{i}")
            filename = f"{loc_id}_{safe_filename(name)}.json"
            save_json(locations_dir, filename, card)
            location_cards.append(card)

        # Generate index
        index = {
            "total_locations": len(location_cards),
            "locations": [
                {
                    "location_id": c.get("location_id"),
                    "name": c.get("name"),
                    "scene_count": c.get("scene_count", 0),
                    "narrative_scenes": c.get("narrative_scenes", []),
                }
                for c in location_cards
            ],
        }
        save_json(locations_dir, "_index.json", index)

        print(f"    场景资产卡: {len(location_cards)} 张")
    except Exception as e:
        print(f"    ⚠ 场景资产卡解析失败: {e}")
        save_text(locations_dir, "_location_card_error.txt",
                  f"{e}\n\n{resp[:2000]}")

    return location_cards, cost


# ════════════════════════════════════════════════════════════════
#  Stage 2B: Prop Collection & Tiering
# ════════════════════════════════════════════════════════════════

def collect_and_tier_props(narrative_scenes: list[dict]) -> dict:
    """Collect props from ALL narrative scenes (not deduplicated locations).

    Rules:
    - Appears ≥3 times → major (needs full visual archive card)
    - Appears <3 times → minor (name + scene refs only)
    """
    from collections import Counter, defaultdict

    prop_counter = Counter()
    prop_scenes = defaultdict(list)

    for scene in narrative_scenes:
        scene_id = scene.get("scene_id", "")
        for prop in scene.get("key_props", []):
            prop = prop.strip()
            if not prop:
                continue
            prop_counter[prop] += 1
            if scene_id not in prop_scenes[prop]:
                prop_scenes[prop].append(scene_id)

    major_props = {
        p: {"count": c, "scenes": prop_scenes[p]}
        for p, c in prop_counter.items() if c >= 3
    }
    minor_props = {
        p: {"count": c, "scenes": prop_scenes[p]}
        for p, c in prop_counter.items() if c < 3
    }

    return {
        "major": major_props,
        "minor": minor_props,
        "total_unique": len(prop_counter),
        "major_count": len(major_props),
        "minor_count": len(minor_props),
    }


# ════════════════════════════════════════════════════════════════
#  Stage 2 Pipeline Orchestrator
# ════════════════════════════════════════════════════════════════

async def run_phase2(characters, narrative_scenes, novel, model_key, out_dir):
    """Stage 2: Location cards + Prop collection + Prop card generation.

    Returns (location_cards, prop_data, costs_list).
    """
    print(f"\n  阶段2: 后处理...")
    costs = []

    # 2A: Location asset card generation
    location_cards, loc_cost = await generate_location_cards(
        narrative_scenes, novel, model_key, out_dir)
    costs.append({"stage": "2A_locations", **loc_cost})

    # 2B: Prop collection & tiering (from ALL narrative scenes)
    props_dir = ensure_dir(out_dir, "props")
    prop_data = collect_and_tier_props(narrative_scenes)
    save_json(props_dir, "prop_index.json", prop_data)
    print(f"    道具: {prop_data['total_unique']} 种 "
          f"(major: {prop_data['major_count']}, minor: {prop_data['minor_count']})")

    # 2C: Prop card generation (major only)
    if prop_data["major"]:
        prop_list_str = json.dumps(prop_data["major"], ensure_ascii=False, indent=2)

        # Extract relevant novel snippets for each prop
        snippets = []
        for prop_name in prop_data["major"]:
            for m in re.finditer(re.escape(prop_name), novel):
                start = max(0, m.start() - 100)
                end = min(len(novel), m.end() + 100)
                snippets.append(f"[{prop_name}] ...{novel[start:end]}...")
                if len(snippets) >= 20:
                    break
            if len(snippets) >= 20:
                break

        resp, prop_cost = await smart_call(
            model_key,
            PROP_CARD_SYSTEM,
            PROP_CARD_USER.format(
                prop_list_with_scenes=prop_list_str,
                relevant_text_snippets="\n".join(snippets[:20]),
            ),
            temperature=0.5,
            max_tokens=8192,
        )
        costs.append({"stage": "2C_props", **prop_cost})

        try:
            prop_cards = extract_json(resp)
            if not isinstance(prop_cards, list):
                prop_cards = [prop_cards]
            for card in prop_cards:
                name = card.get("name", "unnamed")
                save_json(props_dir, f"prop_major_{safe_filename(name)}.json", card)
            print(f"    道具卡: {len(prop_cards)} 张")
        except Exception as e:
            print(f"    ⚠ 道具卡解析失败: {e}")
            save_text(props_dir, "_prop_card_error.txt", f"{e}\n\n{resp[:2000]}")
    else:
        print(f"    无 major 道具，跳过道具卡生成")

    return location_cards, prop_data, costs


# ════════════════════════════════════════════════════════════════
#  Stage 3: Character Variant Generation
# ════════════════════════════════════════════════════════════════

async def run_phase3(characters, narrative_scenes, model_key, out_dir):
    """Stage 3: Generate character variants based on narrative scenes.

    Returns (all_variant_lists, costs_list).
    """
    print(f"\n  阶段3: 角色变体生成...")
    costs = []

    # Filter eligible characters
    eligible_chars = []
    for char in characters:
        role = char.get("role", "")
        name = char.get("name", "")

        # Count appearances in NARRATIVE SCENES (not locations)
        scene_count = sum(
            1 for s in narrative_scenes
            if name in s.get("characters_present", [])
        )

        if role in ("protagonist", "antagonist"):
            eligible_chars.append((char, scene_count))
        elif role == "supporting" and scene_count >= 5:
            eligible_chars.append((char, scene_count))

    if not eligible_chars:
        print(f"    无符合条件的角色，跳过变体生成")
        return [], costs

    print(f"    符合条件: {len(eligible_chars)} 个角色")

    variants_dir = ensure_dir(out_dir, "variants")
    variant_sem = asyncio.Semaphore(2)  # Max 2 concurrent to avoid 429

    async def gen_variant(char, scene_count):
        name = char.get("name", "unnamed")

        # Get all narrative scenes this character appears in
        char_scenes = [
            s for s in narrative_scenes
            if name in s.get("characters_present", [])
        ]

        async with variant_sem:
            resp, cost = await smart_call(
                model_key,
                VARIANT_SYSTEM,
                VARIANT_USER.format(
                    character_card_json=json.dumps(char, ensure_ascii=False, indent=2),
                    character_scenes_json=json.dumps(char_scenes, ensure_ascii=False, indent=2),
                ),
                temperature=0.6,
                max_tokens=8192,
            )
            costs.append({"stage": "3_variants", "character": name, **cost})

        try:
            variants = extract_json(resp)
            if not isinstance(variants, list):
                variants = [variants]
            for v in variants:
                v_type = v.get("variant_type", "unknown")
                filename = f"variant_{safe_filename(name)}_{safe_filename(v_type)}.json"
                save_json(variants_dir, filename, v)
            print(f"    → {name}: {len(variants)} 个变体")
            return variants
        except Exception as e:
            print(f"    ⚠ {name} 变体解析失败: {e}")
            save_text(variants_dir, f"_error_{safe_filename(name)}.txt",
                      f"{e}\n\n{resp[:2000]}")
            return []

    tasks = [gen_variant(char, sc) for char, sc in eligible_chars]
    all_variants = await asyncio.gather(*tasks, return_exceptions=True)

    total = sum(len(v) for v in all_variants if isinstance(v, list))
    print(f"    变体总计: {total} 个")

    return all_variants, costs


# ════════════════════════════════════════════════════════════════
#  Manifest Builder
# ════════════════════════════════════════════════════════════════

def build_manifest(out_dir, characters, narrative_scenes, location_cards,
                   prop_data, all_variants, cost_data):
    """Generate asset manifest index."""
    variant_count = sum(
        len(v) for v in all_variants if isinstance(v, list)
    )
    manifest = {
        "version": "mode_c_v2",
        "generated_at": now_iso(),
        "summary": {
            "characters": len(characters),
            "narrative_scenes": len(narrative_scenes),
            "locations": len(location_cards),
            "props_total": prop_data.get("total_unique", 0),
            "props_major": prop_data.get("major_count", 0),
            "props_minor": prop_data.get("minor_count", 0),
            "variants": variant_count,
        },
        "directories": {
            "characters": "characters/",
            "narrative_scenes": "narrative_scenes/",
            "locations": "locations/",
            "props": "props/",
            "variants": "variants/",
        },
        "files": {
            "timeline": "narrative_scenes/_timeline.json",
            "location_index": "locations/_index.json",
            "props_index": "props/prop_index.json",
            "manifest": "manifest.json",
        },
        "cost": cost_data,
    }
    save_json(out_dir, "manifest.json", manifest)
    return manifest


# ════════════════════════════════════════════════════════════════
#  Streaming API Call
# ════════════════════════════════════════════════════════════════

async def stream_api_call(model_name: str, system: str, user: str,
                          temperature: float = 0.5, max_tokens: int = 16000):
    """Async generator: yields (chunk_text, cost_meta_or_None).

    The last yield may include cost_meta if the API returns usage info.
    """
    adapter = MODEL_REGISTRY[model_name]

    # AnthropicMessagesAdapter must be checked BEFORE OpenAIChatAdapter
    # (it inherits from it)
    if isinstance(adapter, AnthropicMessagesAdapter):
        headers = {
            "x-api-key": adapter.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = {
            "model": adapter.model_id,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": user}],
            "stream": True,
        }
        if system:
            body["system"] = system
        if temperature is not None:
            body["temperature"] = temperature
        url = f"{adapter.api_base}/v1/messages"
    elif isinstance(adapter, OpenAIChatAdapter):
        headers = {
            "Authorization": f"Bearer {adapter.api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        body = {
            "model": adapter.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        url = f"{adapter.api_base}/chat/completions"
    elif isinstance(adapter, ResponsesAPIAdapter):
        headers = {
            "Authorization": f"Bearer {adapter.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": adapter.model_id,
            "input": [{"role": "user", "content": user}],
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "stream": True,
        }
        if system:
            body["instructions"] = system
        url = adapter.api_base
    else:
        raise TypeError(f"Unknown adapter: {type(adapter)}")

    async with _semaphore:
        async with httpx.AsyncClient(timeout=adapter.timeout,
                                      follow_redirects=True) as client:
            async with client.stream("POST", url, json=body,
                                      headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        break
                    try:
                        data = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    # OpenAI Chat format
                    if "choices" in data:
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content

                    # Responses API format
                    elif data.get("type") == "response.output_text.delta":
                        delta_text = data.get("delta", "")
                        if delta_text:
                            yield delta_text

                    # Anthropic Messages streaming format
                    elif data.get("type") == "content_block_delta":
                        delta_obj = data.get("delta", {})
                        if delta_obj.get("type") == "text_delta":
                            text = delta_obj.get("text", "")
                            if text:
                                yield text


# ════════════════════════════════════════════════════════════════
#  Test Mode A: Sequential
# ════════════════════════════════════════════════════════════════

async def test_mode_a(model_name: str, novel_text: str, out: Path) -> dict:
    """Mode A: Instruction 1 (Characters) → Instruction 2 (Scenes)."""
    print(f"\n  [Mode A] Sequential: 指令1(角色) → 指令2(切场)")

    # Instruction 1
    print(f"    → 指令1: 角色设定集...", end="", flush=True)
    t0 = time.time()
    raw1, cost1 = await smart_call(
        model_name, INST1_SYSTEM, INST1_USER.format(text=novel_text),
        temperature=0.5, max_tokens=8192,
    )
    t1 = time.time()
    inst1_time = t1 - t0
    print(f" {inst1_time:.1f}s")

    try:
        characters = extract_json(raw1)
        if isinstance(characters, dict):
            characters = characters.get("characters", [characters])
    except Exception as e:
        print(f"    ✗ 角色JSON解析失败: {e}")
        characters = []

    char_names = [c.get("name", "?") for c in characters]
    print(f"    ✓ {len(characters)} 角色: {', '.join(char_names)}")

    for i, ch in enumerate(characters):
        with open(out / f"mode_a_char_{i:02d}_{ch.get('name','?')}.json",
                  "w", encoding="utf-8") as f:
            json.dump(ch, f, ensure_ascii=False, indent=2)

    # Instruction 2
    print(f"    → 指令2: 语义切场...", end="", flush=True)
    t2 = time.time()
    raw2, cost2 = await smart_call(
        model_name, INST2_SYSTEM, INST2_USER.format(
            text=novel_text,
            character_names=", ".join(char_names),
        ),
        temperature=0.5, max_tokens=12000,
    )
    t3 = time.time()
    inst2_time = t3 - t2
    print(f" {inst2_time:.1f}s")

    try:
        scenes = extract_json(raw2)
        if isinstance(scenes, dict):
            scenes = scenes.get("scenes", [scenes])
    except Exception as e:
        print(f"    ✗ 场景JSON解析失败: {e}")
        scenes = []

    print(f"    ✓ {len(scenes)} 场戏")

    with open(out / "mode_a_scenes.json", "w", encoding="utf-8") as f:
        json.dump(scenes, f, ensure_ascii=False, indent=2)

    dbg = out / "_debug"
    dbg.mkdir(exist_ok=True)
    with open(dbg / "mode_a_raw1.txt", "w", encoding="utf-8") as f:
        f.write(raw1)
    with open(dbg / "mode_a_raw2.txt", "w", encoding="utf-8") as f:
        f.write(raw2)

    tok1 = cost1.get("input_tokens", 0) + cost1.get("output_tokens", 0)
    tok2 = cost2.get("input_tokens", 0) + cost2.get("output_tokens", 0)

    return {
        "mode": "A_sequential",
        "inst1_time_s": round(inst1_time, 2),
        "inst2_time_s": round(inst2_time, 2),
        "total_time_s": round(t3 - t0, 2),
        "num_characters": len(characters),
        "num_scenes": len(scenes),
        "character_names": char_names,
        "costs": [cost1, cost2],
        "total_tokens": tok1 + tok2,
        "input_tokens": cost1.get("input_tokens", 0) + cost2.get("input_tokens", 0),
        "output_tokens": cost1.get("output_tokens", 0) + cost2.get("output_tokens", 0),
    }


# ════════════════════════════════════════════════════════════════
#  Test Mode B: Combined
# ════════════════════════════════════════════════════════════════

async def test_mode_b(model_name: str, novel_text: str, out: Path) -> dict:
    """Mode B: Combined single prompt."""
    print(f"\n  [Mode B] Combined: 角色+切场一次性输出")

    print(f"    → 合并指令...", end="", flush=True)
    t0 = time.time()
    raw, cost = await smart_call(
        model_name, COMBINED_SYSTEM, COMBINED_USER.format(text=novel_text),
        temperature=0.5, max_tokens=32000,
    )
    t1 = time.time()
    total_time = t1 - t0
    print(f" {total_time:.1f}s")

    try:
        result = extract_json(raw)
        if isinstance(result, list):
            characters = result
            scenes = []
        else:
            characters = result.get("characters", [])
            scenes = result.get("scenes", [])
    except Exception as e:
        print(f"    ✗ JSON解析失败: {e}")
        characters, scenes = [], []

    char_names = [c.get("name", "?") for c in characters]
    print(f"    ✓ {len(characters)} 角色, {len(scenes)} 场戏")

    for i, ch in enumerate(characters):
        with open(out / f"mode_b_char_{i:02d}_{ch.get('name','?')}.json",
                  "w", encoding="utf-8") as f:
            json.dump(ch, f, ensure_ascii=False, indent=2)
    with open(out / "mode_b_scenes.json", "w", encoding="utf-8") as f:
        json.dump(scenes, f, ensure_ascii=False, indent=2)

    dbg = out / "_debug"
    dbg.mkdir(exist_ok=True)
    with open(dbg / "mode_b_raw.txt", "w", encoding="utf-8") as f:
        f.write(raw)

    return {
        "mode": "B_combined",
        "total_time_s": round(total_time, 2),
        "num_characters": len(characters),
        "num_scenes": len(scenes),
        "character_names": char_names,
        "costs": [cost],
        "total_tokens": cost.get("input_tokens", 0) + cost.get("output_tokens", 0),
        "input_tokens": cost.get("input_tokens", 0),
        "output_tokens": cost.get("output_tokens", 0),
    }


# ════════════════════════════════════════════════════════════════
#  Test Mode C: Streaming + Progressive Export + Full Asset Pipeline
# ════════════════════════════════════════════════════════════════

async def _mode_c_stage1_streaming(model_name: str, novel_text: str,
                                    out: Path) -> tuple[list, list, dict]:
    """Stage 1: True streaming with progressive character + scene export.

    Returns (characters, narrative_scenes, stage1_meta).
    """
    parser = ProgressiveAssetParser()
    chars_dir = ensure_dir(out, "characters")
    scenes_dir = ensure_dir(out, "narrative_scenes")
    char_export_log = []
    scene_export_log = []
    full_text = ""
    chunk_count = 0
    char_count = 0
    scene_count = 0

    print(f"    → 阶段1: 流式输出中...", flush=True)
    t0 = time.time()

    async for chunk in stream_api_call(
        model_name, COMBINED_SYSTEM, COMBINED_USER.format(text=novel_text),
        temperature=0.5, max_tokens=32000,
    ):
        full_text += chunk
        chunk_count += 1

        result = parser.feed(chunk)

        for char in result["characters"]:
            t_now = time.time() - t0
            name = char.get("name", f"unknown_{char_count}")
            char_export_log.append({"name": name, "time_s": round(t_now, 2)})

            filename = f"char_{char_count:02d}_{safe_filename(name)}.json"
            save_json(chars_dir, filename, char)
            print(f"      ✓ 角色卡导出: {name} @ {t_now:.1f}s")
            char_count += 1

        for scene_obj in result["scenes"]:
            t_now = time.time() - t0
            loc = scene_obj.get("location", f"unnamed_{scene_count}")
            scene_id = f"scene_{scene_count+1:03d}"
            scene_obj["scene_id"] = scene_id
            if "order" not in scene_obj:
                scene_obj["order"] = scene_count

            event = scene_obj.get("core_event", "")[:30]
            scene_export_log.append({
                "scene_id": scene_id,
                "location": loc,
                "time_s": round(t_now, 2),
            })

            filename = f"{scene_id}_{safe_filename(loc)}.json"
            save_json(scenes_dir, filename, scene_obj)
            print(f"      ✓ 叙事场景导出: [{scene_id}] {loc} — {event} @ {t_now:.1f}s")
            scene_count += 1

    t1 = time.time()
    total_time = t1 - t0
    print(f"    流式完成 {total_time:.1f}s ({chunk_count} chunks)")

    # If streaming returned nothing, raise to trigger fallback
    if chunk_count == 0 or not full_text.strip():
        raise RuntimeError(f"流式返回空内容 ({chunk_count} chunks, {len(full_text)} chars)")

    # Fallback: if parser didn't get scenes via streaming, parse full text
    characters = parser.found_chars
    narrative_scenes = parser.found_scenes

    if not narrative_scenes:
        print(f"    ⚠ 流式中未检测到场景，尝试完整解析...")
        try:
            result = extract_json(full_text)
            if isinstance(result, dict):
                if not characters:
                    characters = result.get("characters", [])
                    # Export characters that weren't caught during streaming
                    for i, char in enumerate(characters):
                        if i >= char_count:
                            name = char.get("name", f"unknown_{i}")
                            filename = f"char_{i:02d}_{safe_filename(name)}.json"
                            save_json(chars_dir, filename, char)
                            char_count += 1
                narrative_scenes = result.get("scenes", [])
                # Export scenes
                for i, scene_obj in enumerate(narrative_scenes):
                    scene_id = f"scene_{i+1:03d}"
                    scene_obj["scene_id"] = scene_id
                    if "order" not in scene_obj:
                        scene_obj["order"] = i
                    loc = scene_obj.get("location", f"unnamed_{i}")
                    filename = f"{scene_id}_{safe_filename(loc)}.json"
                    save_json(scenes_dir, filename, scene_obj)
                scene_count = len(narrative_scenes)
        except Exception as e:
            print(f"    ✗ 完整JSON解析也失败: {e}")

    # Generate timeline index
    timeline = {
        "total_scenes": len(narrative_scenes),
        "scenes": [
            {
                "scene_id": s.get("scene_id", f"scene_{i+1:03d}"),
                "order": s.get("order", i),
                "location": s.get("location", ""),
                "core_event": s.get("core_event", ""),
                "characters_present": s.get("characters_present", []),
            }
            for i, s in enumerate(narrative_scenes)
        ],
    }
    save_json(scenes_dir, "_timeline.json", timeline)

    char_names = [c.get("name", "?") for c in characters]
    print(f"    ✓ 阶段1完成: {len(characters)} 角色, {len(narrative_scenes)} 叙事场景")
    print(f"    ✓ 渐进导出: {len(char_export_log)} 角色卡, {len(scene_export_log)} 场景卡")

    # Save debug
    dbg = ensure_dir(out, "_debug")
    save_text(dbg, "mode_c_raw.txt", full_text)

    time_first = char_export_log[0]["time_s"] if char_export_log else None

    stage1_meta = {
        "streaming": True,
        "total_time_s": round(total_time, 2),
        "time_to_first_char_s": time_first,
        "char_export_log": char_export_log,
        "scene_export_log": scene_export_log,
        "num_characters": len(characters),
        "num_characters_streamed": len(char_export_log),
        "num_scenes": len(narrative_scenes),
        "num_scenes_streamed": len(scene_export_log),
        "character_names": char_names,
        "stream_chunks": chunk_count,
    }

    return characters, narrative_scenes, stage1_meta


async def _mode_c_stage1_simulated(model_name: str, novel_text: str,
                                    out: Path) -> tuple[list, list, dict]:
    """Stage 1 fallback: non-streaming call + simulated progressive parse."""
    print(f"    → 阶段1(降级): 非流式 + 模拟渐进解析...", end="", flush=True)
    t0 = time.time()
    raw, cost = await smart_call(
        model_name, COMBINED_SYSTEM, COMBINED_USER.format(text=novel_text),
        temperature=0.5, max_tokens=32000,
    )
    t1 = time.time()
    total_time = t1 - t0
    print(f" {total_time:.1f}s")

    chars_dir = ensure_dir(out, "characters")
    scenes_dir = ensure_dir(out, "narrative_scenes")

    # Simulate progressive parsing
    parser = ProgressiveAssetParser()
    char_export_log = []
    scene_export_log = []
    total_len = len(raw)
    char_count = 0
    scene_count = 0

    for i, ch in enumerate(raw):
        result = parser.feed(ch)
        position_ratio = (i + 1) / total_len
        estimated_time = total_time * position_ratio

        for char in result["characters"]:
            name = char.get("name", f"unknown_{char_count}")
            char_export_log.append({
                "name": name,
                "time_s": round(estimated_time, 2),
                "position_pct": round(position_ratio * 100, 1),
            })
            filename = f"char_{char_count:02d}_{safe_filename(name)}.json"
            save_json(chars_dir, filename, char)
            print(f"      ✓ 角色卡(模拟): {name} @ ~{estimated_time:.1f}s "
                  f"({position_ratio*100:.0f}%)")
            char_count += 1

        for scene_obj in result["scenes"]:
            loc = scene_obj.get("location", f"unnamed_{scene_count}")
            scene_id = f"scene_{scene_count+1:03d}"
            scene_obj["scene_id"] = scene_id
            if "order" not in scene_obj:
                scene_obj["order"] = scene_count
            scene_export_log.append({
                "scene_id": scene_id,
                "location": loc,
                "time_s": round(estimated_time, 2),
                "position_pct": round(position_ratio * 100, 1),
            })
            filename = f"{scene_id}_{safe_filename(loc)}.json"
            save_json(scenes_dir, filename, scene_obj)
            event = scene_obj.get("core_event", "")[:30]
            print(f"      ✓ 叙事场景(模拟): [{scene_id}] {loc} — {event} "
                  f"@ ~{estimated_time:.1f}s ({position_ratio*100:.0f}%)")
            scene_count += 1

    characters = parser.found_chars
    narrative_scenes = parser.found_scenes

    # Fallback: full parse if parser didn't find scenes
    if not narrative_scenes:
        try:
            result = extract_json(raw)
            if isinstance(result, dict):
                if not characters:
                    characters = result.get("characters", [])
                    for i, char in enumerate(characters):
                        if i >= char_count:
                            name = char.get("name", f"unknown_{i}")
                            filename = f"char_{i:02d}_{safe_filename(name)}.json"
                            save_json(chars_dir, filename, char)
                narrative_scenes = result.get("scenes", [])
                for i, scene_obj in enumerate(narrative_scenes):
                    scene_id = f"scene_{i+1:03d}"
                    scene_obj["scene_id"] = scene_id
                    if "order" not in scene_obj:
                        scene_obj["order"] = i
                    loc = scene_obj.get("location", f"unnamed_{i}")
                    filename = f"{scene_id}_{safe_filename(loc)}.json"
                    save_json(scenes_dir, filename, scene_obj)
        except Exception as e:
            print(f"    ✗ JSON解析失败: {e}")

    # Generate timeline
    timeline = {
        "total_scenes": len(narrative_scenes),
        "scenes": [
            {
                "scene_id": s.get("scene_id", f"scene_{i+1:03d}"),
                "order": s.get("order", i),
                "location": s.get("location", ""),
                "core_event": s.get("core_event", ""),
                "characters_present": s.get("characters_present", []),
            }
            for i, s in enumerate(narrative_scenes)
        ],
    }
    save_json(scenes_dir, "_timeline.json", timeline)

    char_names = [c.get("name", "?") for c in characters]
    print(f"    ✓ 阶段1完成: {len(characters)} 角色, {len(narrative_scenes)} 叙事场景")

    dbg = ensure_dir(out, "_debug")
    save_text(dbg, "mode_c_raw.txt", raw)

    time_first = char_export_log[0]["time_s"] if char_export_log else None

    stage1_meta = {
        "streaming": False,
        "total_time_s": round(total_time, 2),
        "time_to_first_char_s": time_first,
        "char_export_log": char_export_log,
        "scene_export_log": scene_export_log,
        "num_characters": len(characters),
        "num_characters_streamed": len(char_export_log),
        "num_scenes": len(narrative_scenes),
        "num_scenes_streamed": len(scene_export_log),
        "character_names": char_names,
        "costs": [cost],
        "total_tokens": cost.get("input_tokens", 0) + cost.get("output_tokens", 0),
    }

    return characters, narrative_scenes, stage1_meta


async def test_mode_c(model_name: str, novel_text: str, out: Path) -> dict:
    """Mode C: Full asset pipeline — 3 stages.

    Stage 1: Streaming progressive export (characters + narrative scenes)
    Stage 2: Location cards + Props collection + Prop cards
    Stage 3: Character variant generation
    """
    print(f"\n  [Mode C] Full Asset Pipeline (3 stages)")
    t0_total = time.time()

    # --- Stage 1: Streaming ---
    try:
        characters, narrative_scenes, s1_meta = await _mode_c_stage1_streaming(
            model_name, novel_text, out)
    except Exception as e:
        print(f"    ⚠ 流式不可用: {type(e).__name__}: {e}")
        characters, narrative_scenes, s1_meta = await _mode_c_stage1_simulated(
            model_name, novel_text, out)

    all_costs = s1_meta.get("costs", [])

    # --- Stage 2: Location cards + Props ---
    try:
        location_cards, prop_data, phase2_costs = await run_phase2(
            characters, narrative_scenes, novel_text, model_name, out)
        all_costs.extend(phase2_costs)
    except Exception as e:
        print(f"    ⚠ 阶段2失败: {type(e).__name__}: {e}")
        location_cards = []
        prop_data = {"total_unique": 0, "major_count": 0, "minor_count": 0}

    # --- Stage 3: Character variants ---
    try:
        all_variants, phase3_costs = await run_phase3(
            characters, narrative_scenes, model_name, out)
        all_costs.extend(phase3_costs)
    except Exception as e:
        print(f"    ⚠ 阶段3失败: {type(e).__name__}: {e}")
        all_variants = []

    # --- Build manifest ---
    total_time = time.time() - t0_total
    manifest = build_manifest(
        out, characters, narrative_scenes, location_cards,
        prop_data, all_variants, all_costs)
    print(f"\n  ✓ Mode C 完成: {total_time:.1f}s 总耗时")
    print(f"    资产: {manifest['summary']}")

    # --- Return results ---
    variant_count = sum(len(v) for v in all_variants if isinstance(v, list))
    result = {
        "mode": "C_pipeline",
        **s1_meta,
        "num_locations": len(location_cards),
        "num_props_total": prop_data.get("total_unique", 0),
        "num_props_major": prop_data.get("major_count", 0),
        "num_variants": variant_count,
        "pipeline_total_time_s": round(total_time, 2),
    }
    return result


# ════════════════════════════════════════════════════════════════
#  Runner
# ════════════════════════════════════════════════════════════════

async def run_model(model_key: str, model_name: str,
                    novel_text: str, modes: list[str]) -> dict:
    display = DISPLAY_NAMES.get(model_name, model_name)
    print(f"\n{'='*60}")
    print(f"  Model: {display} ({model_name})")
    print(f"{'='*60}")

    model_dir = RESULTS_DIR / model_key
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "_debug").mkdir(exist_ok=True)

    results = {"model": display, "model_id": model_name}

    for mode in modes:
        try:
            if mode == "A":
                results["mode_a"] = await test_mode_a(model_name, novel_text, model_dir)
            elif mode == "B":
                results["mode_b"] = await test_mode_b(model_name, novel_text, model_dir)
            elif mode == "C":
                results["mode_c"] = await test_mode_c(model_name, novel_text, model_dir)
        except Exception as e:
            key = f"mode_{mode.lower()}"
            print(f"    ✗ Mode {mode} 失败: {type(e).__name__}: {e}")
            results[key] = {"error": str(e), "error_type": type(e).__name__}

    with open(model_dir / "results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return results


def print_summary(all_results: dict):
    print("\n" + "=" * 80)
    print("  ROUND 10 BENCHMARK SUMMARY")
    print("=" * 80)

    # Table header
    print(f"\n{'Model':<10} {'Mode':<20} {'Total(s)':<10} "
          f"{'Chars':<7} {'Scenes':<8} {'Locs':<6} {'Tokens':<9} {'1st Card':<10}")
    print("-" * 86)

    for model_key, results in all_results.items():
        display = results.get("model", model_key)

        for mk in ["mode_a", "mode_b", "mode_c"]:
            r = results.get(mk)
            if not r or "error" in r:
                if r and "error" in r:
                    print(f"{display:<10} {mk:<20} FAILED: {r['error'][:40]}")
                continue

            mode_label = r.get("mode", mk)
            if mk == "mode_a":
                i1 = r.get("inst1_time_s", "?")
                i2 = r.get("inst2_time_s", "?")
                mode_label = f"A ({i1}s+{i2}s)"

            total = r.get("total_time_s", r.get("pipeline_total_time_s", "?"))
            chars = r.get("num_characters", "?")
            scenes = r.get("num_scenes", "?")
            locs = r.get("num_locations", "-")
            tokens = r.get("total_tokens", "?")
            first = r.get("time_to_first_char_s")
            first_str = f"{first}s" if first else "-"

            print(f"{display:<10} {mode_label:<20} {str(total)+'s':<10} "
                  f"{chars:<7} {scenes:<8} {str(locs):<6} {tokens:<9} {first_str:<10}")

    # Efficiency analysis
    print("\n" + "-" * 80)
    print("  EFFICIENCY ANALYSIS")
    print("-" * 80)

    for model_key, results in all_results.items():
        display = results.get("model", model_key)
        a = results.get("mode_a", {})
        b = results.get("mode_b", {})
        c = results.get("mode_c", {})

        print(f"\n  [{display}]")

        if "error" not in a and "error" not in b:
            at = a.get("total_time_s", 0)
            bt = b.get("total_time_s", 0)
            if at > 0 and bt > 0:
                pct = (at - bt) / at * 100
                winner = "合并更快" if pct > 0 else "分离更快"
                print(f"    分离(A) {at:.0f}s vs 合并(B) {bt:.0f}s → "
                      f"{winner} {abs(pct):.1f}%")
            at_tok = a.get("total_tokens", 0)
            bt_tok = b.get("total_tokens", 0)
            if at_tok and bt_tok:
                tok_save = at_tok - bt_tok
                print(f"    Token: A={at_tok} vs B={bt_tok} → "
                      f"{'节省' if tok_save > 0 else '多用'} {abs(tok_save)}")

        if "error" not in c:
            ct = c.get("total_time_s", 0)
            pt = c.get("pipeline_total_time_s", ct)
            first = c.get("time_to_first_char_s")
            streamed_chars = c.get("num_characters_streamed", 0)
            streamed_scenes = c.get("num_scenes_streamed", 0)
            is_true_stream = c.get("streaming", False)
            mode_desc = "真流式" if is_true_stream else "模拟流式"

            n_locs = c.get("num_locations", 0)
            n_props = c.get("num_props_total", 0)
            n_variants = c.get("num_variants", 0)

            if first:
                print(f"    {mode_desc}(C): 首张角色卡 @ {first}s, "
                      f"阶段1耗时 {ct:.0f}s, 管线总耗时 {pt:.0f}s")
                print(f"    渐进导出: {streamed_chars} 角色卡 + {streamed_scenes} 叙事场景")
                if n_locs or n_props or n_variants:
                    print(f"    管线产出: {n_locs} 场景资产卡, {n_props} 道具, {n_variants} 变体")
                if "error" not in b:
                    bt = b.get("total_time_s", 0)
                    if bt > 0 and first:
                        advantage = bt - first
                        print(f"    首卡提前量: 比等待完整响应早 {advantage:.1f}s")

            # Show progressive export timeline
            log = c.get("char_export_log", [])
            scene_log = c.get("scene_export_log", [])
            if log or scene_log:
                print(f"    渐进导出时间线:")
                for entry in log:
                    pct = entry.get("position_pct", "")
                    pct_str = f" ({pct}%)" if pct else ""
                    print(f"      {entry['time_s']:>6.1f}s → 角色: {entry['name']}{pct_str}")
                for entry in scene_log:
                    pct = entry.get("position_pct", "")
                    pct_str = f" ({pct}%)" if pct else ""
                    print(f"      {entry['time_s']:>6.1f}s → 场景: [{entry['scene_id']}] "
                          f"{entry['location']}{pct_str}")


async def main():
    ap = argparse.ArgumentParser(description="Round 10: Char+Scene Benchmark")
    ap.add_argument("--only", help="chatgpt/claude/gemini/grok")
    ap.add_argument("--mode", help="A,B,C (comma-separated)")
    args = ap.parse_args()

    modes = ["A", "B", "C"]
    if args.mode:
        modes = [m.strip().upper() for m in args.mode.split(",")]

    models = list(MODEL_SHORTCUTS.items())
    if args.only:
        key = args.only.lower()
        if key in MODEL_SHORTCUTS:
            models = [(key, MODEL_SHORTCUTS[key])]
        else:
            print(f"Unknown: {key}. Available: {list(MODEL_SHORTCUTS.keys())}")
            sys.exit(1)

    # Read novel
    print(f"Loading novel: {NOVEL_PATH}")
    with open(NOVEL_PATH, "r", encoding="gb18030") as f:
        novel_text = f.read()
    print(f"  {len(novel_text)} chars\n")
    print(f"Benchmark: {len(models)} model(s) × {len(modes)} mode(s)")
    print(f"  Models: {', '.join(k for k, v in models)}")
    print(f"  Modes:  {', '.join(modes)}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    all_results = {}
    for mk, mn in models:
        all_results[mk] = await run_model(mk, mn, novel_text, modes)

    # Save
    with open(RESULTS_DIR / "all_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print_summary(all_results)

    # Save summary text
    old = sys.stdout
    sys.stdout = buf = io.StringIO()
    print_summary(all_results)
    sys.stdout = old
    with open(RESULTS_DIR / "00_benchmark_summary.txt", "w", encoding="utf-8") as f:
        f.write(buf.getvalue())

    print(f"\n\nResults → {RESULTS_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
