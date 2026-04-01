"""R32 — GPT-5.4 (OpenClaudeCode) 全流水线测试.

基于 R30 全部优化, GPT-5.4 模型重跑验证:
  R32: GPT-5.4 重跑验证 (与 R31 DeepSeek 对比基线)
  R30 保留: 变体提前启动(仅等角色) | loc_id 修复 | Event 解耦
  R28 保留: 精细切场 35-50 | 闪回独立 | 情绪转折拆分
  R27 保留: asyncio.Event 解耦 | 渐进位置卡发射 | 弹性并发

用法:
    python run_r32_pipeline_test.py
"""

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from collections import defaultdict

# Fix Windows GBK console encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
os.environ["PYTHONIOENCODING"] = "utf-8"

import httpx

# ===================================================================
#  添加 backend 到 sys.path
# ===================================================================
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# 从后端导入
from services.streaming_parser import (
    ProgressiveAssetParser, extract_json_robust,
    is_truncated, estimate_max_tokens,
)
from services.asset_enrichment import (
    group_scenes_by_location, collect_and_tier_props,
)
from services.prompt_templates import render_prompt

# ===================================================================
#  GPT-5.4 配置
# ===================================================================

_OCC_KEY = "sk-S2HdTVByFCfJcZ3oM3BUBQio0CGtty7xA2aTHdCP9occt50e"

MAX_RETRIES = 3
RETRY_WAIT_BASE = 20
RATE_LIMIT_WAIT = 30
MAX_CONCURRENT = 10
MAJOR_PROP_TOP_N = 10

_semaphore = asyncio.Semaphore(MAX_CONCURRENT)

MODEL_CFG = {
    "model_id": "gpt-5.4",
    "display_name": "ChatGPT (gpt-5.4)",
    "api_type": "responses",
    "api_base": "https://www.openclaudecode.cn/v1/responses",
    "api_key": _OCC_KEY,
    "timeout": 600,
}

# R13 Stage 1 补充 prompt
_R13_STAGE1_SUPPLEMENT = (
    "\n\n【重要补充要求 — R13】\n"
    "1. 确保至少提取15个以上的叙事场景，仔细检查是否遗漏了时空跳转点\n"
    "2. key_props 只列出推动剧情或揭示角色的核心道具（预计每场景2-5个），"
    "不要列出纯环境装饰物（如'桌椅'、'墙壁'、'地面'）。"
    "同类道具归为一组（如'各色酒盏'而非分列每个杯子）\n"
    "3. visual_reference 和 visual_prompt_negative 必须使用中文\n"
    "4. 每个场景必须包含 source_text_start 和 source_text_end 字段：\n"
    "   - source_text_start: 该场景对应原文段落的前20个字（精确复制原文，不修改）\n"
    "   - source_text_end: 该场景对应原文段落的最后20个字（精确复制原文，不修改）\n"
    "   这两个字段用于后期在原文中精确定位每个场景的文本范围\n"
)

# ===================================================================
#  R25: 角色独立 / 场景独立 prompt
# ===================================================================

_CHAR_ONLY_SYSTEM = (
    "你是一位资深选角导演，精通角色分析和 AI 视觉档案构建。\n"
    "从小说中提取全剧角色设定集。\n"
    "角色外观精度：AI绘图可直接使用。\n"
    "重要：输出必须是一个JSON对象，顶层key为\"characters\"，值为数组。\n"
    "每个角色的所有字段都必须填写完整，不得省略。\n"
    "所有输出严格JSON格式，不要输出其他内容。"
)

_CHAR_ONLY_USER = """对以下小说提取全部角色设定集。

要求：
- 识别所有有名角色 + 有独立行为的无名角色
- 每个角色：身份、外貌（AI绘图级）、性格、欲望、缺陷、弧线、关系、出场概要
- visual_reference 和 visual_prompt_negative 必须使用中文，且必须填写
- role 字段必须从 protagonist/antagonist/supporting/minor 中选一个

注意：输出必须是 {{"characters": [...]}} 格式的JSON对象（顶层key为"characters"），不要直接输出数组。

返回格式（仅返回JSON，不要附加任何解释文字）：
```json
{{"characters": [
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
    "visual_reference": "中文AI绘图提示词（详细描述外貌、服装、姿态、光影氛围）",
    "visual_prompt_negative": "生成此角色时应避免的元素（中文）",
    "personality": "核心性格",
    "desire": "核心欲望",
    "flaw": "致命缺陷",
    "arc": "弧线",
    "scene_presence": "出场概要",
    "relationships": [
      {{"target": "角色名", "type": "类型", "dynamic": "张力描述", "function": "叙事功能"}}
    ]
  }}
]}}
```

小说全文：
---
{text}
---"""

_SCENE_ONLY_SYSTEM = (
    "你是一位资深副导演，精通影视分镜级的场景拆解。\n"
    "对小说执行精细语义切场（无视原文章节，按时空+情绪切分）。\n"
    "\n"
    "【精细切场原则 — R28】\n"
    "1. 时间跳跃 = 新场景（哪怕只跳了几小时）\n"
    "2. 空间转换 = 新场景（从屋内到门口也算）\n"
    "3. 视角切换 = 新场景\n"
    "4. 情绪峰谷转折 = 新场景（同一地点内情绪发生重大转折时必须拆分）\n"
    "5. 回忆/闪回 = 独立场景（不要和当前时空混在一起，必须单独成场，heading 用 FLASHBACK）\n"
    "6. 同一地点发生的多个独立事件 = 每个事件一个场景\n"
    "7. 对话中穿插的回忆或内心独白 = 如果超过5行以上，必须独立成 FLASHBACK 场景\n"
    "8. 宁可多拆不要少拆，每个场景只包含一个核心动作/决定/冲突\n"
    "\n"
    "【R28 重点修正 — 针对已知切分缺陷】\n"
    "A. 序章/开篇如果是闪前（先写结局再回到过去），必须独立成场，不要和后续的正叙混在一起\n"
    "B. 长段回忆中如果包含多个独立事件（如：争吵→伤人→失去孩子），每个事件必须独立成场\n"
    "C. 人物性格介绍段落 和 情节冲突段落 属于不同叙事功能，不要合并为同一场景\n"
    "D. 角色在对话中回忆另一个时空的侮辱/伤害（如回忆某人说过的话），这段回忆如果有具体场景画面感，应拆为独立 FLASHBACK\n"
    "E. 一个回忆段覆盖多年跨度时，必须按关键事件拆分为多个 FLASHBACK 场景\n"
    "\n"
    "场景数量指导：目标 35-50 个叙事场景。若不足35个说明切分太粗。\n"
    "场景必须按故事发生的时间顺序排列。\n"
    "道具粒度指导：key_props 只列出推动剧情或揭示角色的核心道具（每场景2-5个），"
    "不要列出纯环境装饰物。同类道具合并为一项。\n"
    "原文定位指导：每个场景必须标注其在原文中对应段落的起始和终结文本片段（各20个字）。\n"
    "重要：输出必须是一个JSON对象，顶层key为\"scenes\"，值为数组。\n"
    "所有输出严格JSON格式，不要输出其他内容。"
)

_SCENE_ONLY_USER = """对以下小说执行精细影视级语义切场分析。

【核心要求 — 精细切分 R28】
- 完全无视原文章节，按时间-空间-情绪精细切场
- 每个场景只包含一个核心事件/动作/决定/冲突，不要把多个事件合并在一个场景里
- 回忆和闪回必须独立成场（标注 heading 为 FLASHBACK）
- 同一地点如果情绪发生重大转折（如从争吵到和解），必须拆成两个场景
- 角色的进入/退出如果带来新事件，也应拆分
- 目标：35-50 个场景。如果你只提取了不到35个，请重新检查是否有合并过粗的场景

【R28 重点注意 — 常见错误修正】
1. 如果小说开篇是闪前（先交代结局/现状，再回到过去叙述），闪前部分必须独立成场，不要和后续第一个正叙场景合并
2. 长段回忆如果包含"争吵→暴力→失去孩子"等多个独立事件，必须拆成多个 FLASHBACK 场景，不能用一个场景概括
3. 人物性格/背景介绍段 和 紧随其后的冲突事件段，属于不同叙事功能，应拆成两个场景
4. 角色在当前对话中想起过去被羞辱的具体画面（有明确的时间地点人物），该回忆应独立为 FLASHBACK
5. 对峙场景中如果中途有角色下跪/情绪骤变/新角色介入，应从该点拆分

其他要求：
- 每场：时空标签、在场角色、核心事件、情绪峰值、张力分数、预计时长
- key_props 只列出推动剧情或揭示角色的核心道具（每场景2-5个）
- visual_reference 和 visual_prompt_negative 必须使用中文
- 每个场景必须包含 source_text_start 和 source_text_end 字段

注意：输出必须是 {{"scenes": [...]}} 格式的JSON对象（顶层key为"scenes"），不要直接输出数组。

返回格式（仅返回JSON，不要附加任何解释文字）：
```json
{{"scenes": [
  {{
    "scene_id": "scene_001",
    "order": 0,
    "heading": "INT/EXT. 地点 - 时间 (或 FLASHBACK. 地点 - 时间)",
    "location": "具体地点（精确到房间级别，如'高家书房'而非'高家'）",
    "time_of_day": "day|night|dawn|dusk",
    "characters_present": ["角色1", "角色2"],
    "core_event": "核心事件（只描述这一个场景中发生的一件事，30-50字）",
    "key_dialogue": "最关键台词",
    "emotional_peak": "情绪峰值",
    "tension_score": 0.5,
    "estimated_duration_s": 60,
    "key_props": ["核心道具1", "核心道具2"],
    "dramatic_purpose": "戏剧功能",
    "visual_reference": "中文AI绘图提示词（详细描述场景画面）",
    "visual_prompt_negative": "生成此场景时应避免的元素（中文）",
    "source_text_start": "该场景对应原文的起始文本片段（原文前20个字，精确复制）",
    "source_text_end": "该场景对应原文的终结文本片段（原文最后20个字，精确复制）"
  }}
]}}
```

小说全文：
---
{text}
---"""


# ===================================================================
#  辅助: 重试 / SSE 解析
# ===================================================================

def is_retryable(exc):
    if isinstance(exc, (httpx.ReadTimeout, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (500, 502, 503, 504, 524)
    return False

def is_rate_limited(exc):
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429
    return False


# ===================================================================
#  API 调用 (Responses API for GPT-5.4)
# ===================================================================

async def call_api(system: str, user: str,
                   temperature: float = 0.5, max_tokens: int = 8192) -> tuple[str, dict]:
    """非流式 API 调用 — Responses API."""
    cfg = MODEL_CFG
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    body = {
        "model": cfg["model_id"],
        "input": [{"role": "user", "content": user}],
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }
    if system:
        body["instructions"] = system
    url = cfg["api_base"]

    last_exc = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with _semaphore:
                t0 = time.time()
                async with httpx.AsyncClient(timeout=cfg["timeout"],
                                             follow_redirects=True) as client:
                    resp = await client.post(url, json=body, headers=headers)
                    resp.raise_for_status()
                elapsed = time.time() - t0

            resp_body = resp.text
            if not resp_body.strip():
                raise RuntimeError(f"Empty response from {cfg['display_name']}")

            # Handle SSE responses from proxies
            if resp_body.lstrip().startswith("data: "):
                text, usage = _parse_sse_to_text(resp_body)
                if not text.strip():
                    raise RuntimeError(f"SSE response parsed to empty text")
                return text, {"model": cfg["display_name"], "elapsed_s": round(elapsed, 2),
                             "input_tokens": usage.get("input_tokens", 0),
                             "output_tokens": usage.get("output_tokens", 0)}

            data = resp.json()
            if data.get("error"):
                err_msg = data["error"] if isinstance(data["error"], str) else data["error"].get("message", str(data["error"]))
                raise RuntimeError(f"API error: {err_msg}")

            output = data.get("output", [])
            text = output[0]["content"][0]["text"] if output and output[0].get("content") else ""
            if not text.strip():
                raise RuntimeError(f"Responses API returned empty content")
            usage = data.get("usage", {})
            return text, {"model": cfg["display_name"], "elapsed_s": round(elapsed, 2),
                         "input_tokens": usage.get("input_tokens", 0),
                         "output_tokens": usage.get("output_tokens", 0)}

        except Exception as e:
            last_exc = e
            if is_rate_limited(e):
                retry_after = 5.0
                if isinstance(e, httpx.HTTPStatusError):
                    retry_after = float(e.response.headers.get("retry-after", str(RATE_LIMIT_WAIT)))
                print(f"    [!!] 429限流, 等待{retry_after}s (Retry-After respected)...", flush=True)
                await asyncio.sleep(retry_after)
                continue
            if is_retryable(e) or isinstance(e, RuntimeError):
                if attempt < MAX_RETRIES:
                    wait = RETRY_WAIT_BASE * (attempt + 1)
                    # R20: 500/503 用指数退避
                    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (500, 503):
                        wait = 2 ** attempt * 5
                        print(f"    [!!] {e.response.status_code} 指数退避 {wait}s (attempt {attempt+1})...", flush=True)
                    else:
                        print(f"    [!!] 重试 {attempt+1}/{MAX_RETRIES}, 等待{wait}s: {type(e).__name__}: {e}", flush=True)
                    await asyncio.sleep(wait)
                    continue
            raise
    raise last_exc


def _parse_sse_to_text(body: str) -> tuple[str, dict]:
    """将 SSE 流式响应体拼装为完整文本 + usage。"""
    chunks = []
    usage = {}
    for line in body.split("\n"):
        line = line.strip()
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            break
        try:
            obj = json.loads(payload)
            choices = obj.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    chunks.append(content)
            if obj.get("usage"):
                usage = obj["usage"]
        except json.JSONDecodeError:
            continue
    return "".join(chunks), usage


async def stream_api_call(system: str, user: str,
                          temperature: float = 0.5, max_tokens: int = 32000):
    """流式 API 调用 — async generator, yield text chunks."""
    cfg = MODEL_CFG
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    body = {
        "model": cfg["model_id"],
        "input": [{"role": "user", "content": user}],
        "temperature": temperature,
        "max_output_tokens": max_tokens,
        "stream": True,
    }
    if system:
        body["instructions"] = system
    url = cfg["api_base"]

    # R20: 使用 stall 超时 (60s)
    STALL_TIMEOUT = 60

    async with _semaphore:
        async with httpx.AsyncClient(timeout=cfg["timeout"],
                                     follow_redirects=True) as client:
            async with client.stream("POST", url, json=body, headers=headers) as resp:
                resp.raise_for_status()
                last_chunk_time = time.time()

                async for line in resp.aiter_lines():
                    # R20: stall timeout check
                    now = time.time()
                    if now - last_chunk_time > STALL_TIMEOUT:
                        raise TimeoutError(f"Stream stalled: no data for {STALL_TIMEOUT}s")

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

                    # Responses API format
                    if data.get("type") == "response.output_text.delta":
                        delta_text = data.get("delta", "")
                        if delta_text:
                            last_chunk_time = time.time()
                            yield delta_text

                    # OpenAI Chat format (via proxy fallback)
                    elif "choices" in data:
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            last_chunk_time = time.time()
                            yield content


async def smart_call(system: str, user: str,
                     temperature: float = 0.5, max_tokens: int = 8192) -> tuple[str, dict]:
    """智能调用: 流式优先，降级非流式。"""
    full_text = ""
    t0 = time.time()
    try:
        async for chunk in stream_api_call(system, user, temperature, max_tokens):
            full_text += chunk
    except Exception as e:
        print(f"    [!] smart_call 流式异常: {type(e).__name__}: {e}", flush=True)
        if not full_text:
            return await call_api(system, user, temperature, max_tokens)
    elapsed = time.time() - t0
    if not full_text.strip():
        print(f"    [!] smart_call 流式返回空文本, 降级非流式...", flush=True)
        return await call_api(system, user, temperature, max_tokens)
    return full_text, {"model": MODEL_CFG["display_name"], "elapsed_s": round(elapsed, 2),
                      "input_tokens": 0, "output_tokens": len(full_text) // 2}


# ===================================================================
#  辅助函数
# ===================================================================

def _safe(name: str) -> str:
    return re.sub(r'[^\w\u4e00-\u9fff-]', '_', name)[:30]

def _is_valid_char(c: dict) -> bool:
    """R29: 严格校验 — 必须有 name + 至少一个角色专属字段."""
    name = c.get("name")
    if not name or not isinstance(name, str) or len(name.strip()) == 0:
        return False
    # 垃圾对象(关系/嵌套)的键集: target, type, dynamic, function
    # 真角色必须有至少一个角色专属字段
    char_fields = {"role", "age_range", "personality", "appearance", "visual_reference", "arc"}
    return bool(char_fields & set(c.keys()))

def _save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _clean_scene_files(scenes_dir: Path):
    for old_f in scenes_dir.glob("scene_*.json"):
        old_f.unlink()

def _dedup_scenes(scenes: list) -> list:
    seen = set()
    unique = []
    removed = 0
    for s in scenes:
        if not isinstance(s, dict):
            continue
        loc = s.get("location", "")
        event = s.get("core_event", "")[:30]
        heading = s.get("heading", "")
        fingerprint = f"{loc}|{event}|{heading}"
        if fingerprint in seen:
            removed += 1
            continue
        seen.add(fingerprint)
        unique.append(s)
    if removed > 0:
        print(f"    [OK] 场景去重: {len(scenes)} -> {len(unique)} (移除{removed}个重复)")
        for i, s in enumerate(unique):
            s["scene_id"] = f"scene_{i + 1:03d}"
            s["order"] = i
    return unique

def _source_text_coverage(scenes: list) -> dict:
    total = len(scenes)
    if total == 0:
        return {"total": 0, "count_with_start": 0, "count_with_end": 0,
                "count_with_both": 0, "coverage_pct": 0.0}
    with_start = sum(1 for s in scenes if s.get("source_text_start"))
    with_end = sum(1 for s in scenes if s.get("source_text_end"))
    with_both = sum(1 for s in scenes
                    if s.get("source_text_start") and s.get("source_text_end"))
    return {
        "total": total,
        "count_with_start": with_start,
        "count_with_end": with_end,
        "count_with_both": with_both,
        "coverage_pct": round(with_both / total * 100, 1) if total else 0.0,
    }

def _retier_props(raw_prop_data: dict, top_n: int) -> dict:
    all_props = {}
    for name, info in raw_prop_data.get("major", {}).items():
        all_props[name] = info
    for name, info in raw_prop_data.get("minor", {}).items():
        all_props[name] = info
    sorted_props = sorted(all_props.items(), key=lambda x: x[1].get("count", 0), reverse=True)
    major = dict(sorted_props[:top_n])
    minor = dict(sorted_props[top_n:])
    return {
        "major": major,
        "minor": minor,
        "total_unique": len(all_props),
        "major_count": len(major),
        "minor_count": len(minor),
    }


# ===================================================================
#  R20 加固验证: streaming_parser 单元测试
# ===================================================================

def test_streaming_parser_hardening():
    """验证 R20 加固点: code fence 剥离 + GPT token 预估."""
    print("\n  [R20 单元测试] streaming_parser 加固验证")

    # Test 1: markdown code fence 剥离
    parser = ProgressiveAssetParser()
    raw_with_fence = '```json\n{"characters": [{"name": "测试角色"}], "scenes": []}\n```'
    result = parser.feed(raw_with_fence)
    assert len(parser.found_chars) >= 1, f"FAIL: code fence 剥离后应提取角色, got {len(parser.found_chars)}"
    print(f"    [PASS] _clean() 正确剥离 ```json...``` code fence")

    # Test 2: GPT token 预估
    gpt_tokens = estimate_max_tokens(10000, "gpt-5.4")
    claude_tokens = estimate_max_tokens(10000, "claude-sonnet-4-6")
    assert gpt_tokens < claude_tokens, f"FAIL: GPT tokens ({gpt_tokens}) should < Claude ({claude_tokens})"
    print(f"    [PASS] estimate_max_tokens: GPT={gpt_tokens}, Claude={claude_tokens} (GPT < Claude)")

    # Test 3: 响应缓冲上限常量
    from services.import_pipeline import MAX_RESPONSE_BUFFER_CHARS, CHAR_FLUSH_BATCH, SCENE_FLUSH_BATCH
    assert MAX_RESPONSE_BUFFER_CHARS == 500_000, f"FAIL: buffer cap should be 500K, got {MAX_RESPONSE_BUFFER_CHARS}"
    assert CHAR_FLUSH_BATCH == 5, f"FAIL: char batch should be 5"
    assert SCENE_FLUSH_BATCH == 10, f"FAIL: scene batch should be 10"
    print(f"    [PASS] 缓冲区常量: MAX_RESPONSE_BUFFER={MAX_RESPONSE_BUFFER_CHARS}, CHAR_BATCH={CHAR_FLUSH_BATCH}, SCENE_BATCH={SCENE_FLUSH_BATCH}")

    # Test 4: 并发常量下降
    from services.import_pipeline import MAX_SCENE_CONCURRENCY, MAX_PROMPT_CONCURRENCY
    assert MAX_SCENE_CONCURRENCY == 2, f"FAIL: MAX_SCENE_CONCURRENCY should be 2, got {MAX_SCENE_CONCURRENCY}"
    assert MAX_PROMPT_CONCURRENCY == 2, f"FAIL: MAX_PROMPT_CONCURRENCY should be 2, got {MAX_PROMPT_CONCURRENCY}"
    print(f"    [PASS] 并发常量: SCENE={MAX_SCENE_CONCURRENCY}, PROMPT={MAX_PROMPT_CONCURRENCY}")

    # Test 5: RateLimitError 存在
    from services.ai_engine import RateLimitError
    e = RateLimitError("test", retry_after=5.0)
    assert e.retry_after == 5.0
    print(f"    [PASS] RateLimitError 异常类正常")

    # Test 6: ProviderAdapter.close() 存在
    from services.providers.base import ProviderAdapter
    assert hasattr(ProviderAdapter, "close"), "FAIL: ProviderAdapter missing close()"
    print(f"    [PASS] ProviderAdapter.close() 方法存在")

    # Test 7: event_bus 模块可导入
    from services.event_bus import push_event, get_events, subscribe, event_count
    print(f"    [PASS] event_bus 模块可导入 (push_event, get_events, subscribe)")

    # Test 8: rate_limiter 模块可导入
    from services.rate_limiter import acquire, record_actual_tokens
    print(f"    [PASS] rate_limiter 模块可导入 (acquire, record_actual_tokens)")

    # Test 9: config.py 新字段
    from config import settings
    assert hasattr(settings, 'db_pool_size'), "FAIL: missing db_pool_size"
    assert hasattr(settings, 'redis_url'), "FAIL: missing redis_url"
    assert hasattr(settings, 'max_concurrent_imports'), "FAIL: missing max_concurrent_imports"
    assert hasattr(settings, 'ai_rpm_limit'), "FAIL: missing ai_rpm_limit"
    assert hasattr(settings, 'ai_tpm_limit'), "FAIL: missing ai_tpm_limit"
    assert settings.debug == False, f"FAIL: debug should default to False, got {settings.debug}"
    print(f"    [PASS] config.py 新字段: pool_size={settings.db_pool_size}, "
          f"max_imports={settings.max_concurrent_imports}, rpm={settings.ai_rpm_limit}")

    # Test 10: ImportPipeline.cancel_all 存在
    from services.import_pipeline import ImportPipeline
    assert hasattr(ImportPipeline, 'cancel_all'), "FAIL: ImportPipeline missing cancel_all()"
    assert hasattr(ImportPipeline, '_active_pipelines'), "FAIL: ImportPipeline missing _active_pipelines"
    print(f"    [PASS] ImportPipeline.cancel_all() 类方法存在")

    print(f"\n  [R20] 全部 10 项单元测试通过 ✓\n")


# ===================================================================
#  Stage 1: 流式合并提取 (GPT-5.4)
# ===================================================================

async def stage1_streaming(novel_text: str, out_dir: Path) -> tuple[list, list, dict]:
    """Stage 1: 真流式 + ProgressiveAssetParser 渐进导出."""
    parser = ProgressiveAssetParser()
    chars_dir = out_dir / "characters"
    scenes_dir = out_dir / "narrative_scenes"
    chars_dir.mkdir(parents=True, exist_ok=True)
    scenes_dir.mkdir(parents=True, exist_ok=True)

    char_export_log = []
    scene_export_log = []
    response_chunks: list[str] = []
    response_total_chars = 0
    MAX_BUFFER = 500_000  # R20: 响应缓冲区上限
    chunk_count = 0
    char_count = 0
    scene_count = 0

    rendered = render_prompt("P_COMBINED_EXTRACT", text=novel_text[:80000])
    rendered["user"] += _R13_STAGE1_SUPPLEMENT
    adaptive_tokens = estimate_max_tokens(len(novel_text[:80000]), MODEL_CFG["model_id"])
    max_tokens = max(rendered["max_tokens"], adaptive_tokens)

    print(f"    -> 阶段1: 流式提取中 (max_tokens={max_tokens}, GPT adaptive)...", flush=True)
    t0 = time.time()

    try:
        async for chunk in stream_api_call(
            rendered["system"], rendered["user"],
            temperature=rendered["temperature"], max_tokens=max_tokens,
        ):
            # R20: 缓冲区上限
            if response_total_chars < MAX_BUFFER:
                response_chunks.append(chunk)
                response_total_chars += len(chunk)
            chunk_count += 1

            result = parser.feed(chunk)

            for char in result["characters"]:
                t_now = time.time() - t0
                name = char.get("name", f"unknown_{char_count}")
                char_export_log.append({"name": name, "time_s": round(t_now, 2)})
                _save_json(chars_dir / f"char_{char_count:02d}_{_safe(name)}.json", char)
                print(f"      [OK] 角色卡导出: {name} @ {t_now:.1f}s")
                char_count += 1

            for scene_obj in result["scenes"]:
                t_now = time.time() - t0
                scene_id = f"scene_{scene_count + 1:03d}"
                scene_obj["scene_id"] = scene_id
                if "order" not in scene_obj:
                    scene_obj["order"] = scene_count
                loc = scene_obj.get("location", f"unnamed_{scene_count}")
                event = scene_obj.get("core_event", "")[:30]
                scene_export_log.append({"scene_id": scene_id, "location": loc, "time_s": round(t_now, 2)})
                _save_json(scenes_dir / f"{scene_id}_{_safe(loc)}.json", scene_obj)
                print(f"      [OK] 叙事场景导出: [{scene_id}] {loc} - {event} @ {t_now:.1f}s")
                scene_count += 1

    except Exception as e:
        print(f"      [!!] 流式异常: {type(e).__name__}: {e}")
        if chunk_count == 0:
            print(f"      -> 降级为非流式调用...")
            return await stage1_non_streaming(novel_text, out_dir)

    total_time = time.time() - t0
    print(f"    流式完成 {total_time:.1f}s ({chunk_count} chunks, {response_total_chars} chars buffered)")
    if response_total_chars >= MAX_BUFFER:
        print(f"    [R20] 响应缓冲区已达上限 {MAX_BUFFER}, 后续chunks未存储")

    # 保存 debug
    dbg = out_dir / "_debug"
    dbg.mkdir(exist_ok=True)
    full_response = "".join(response_chunks)
    (dbg / "stage1_raw.txt").write_text(full_response, encoding="utf-8")

    if chunk_count == 0 or response_total_chars == 0:
        print(f"    -> 降级为非流式调用（无响应）...")
        return await stage1_non_streaming(novel_text, out_dir)

    # 流式chunks过少且场景不足 → 降级
    if chunk_count < 1000 and len(parser.found_scenes) < 5:
        print(f"    [!!] 流式仅收到 {chunk_count} chunks 且场景不足({len(parser.found_scenes)}个)，降级为非流式重试...")
        return await stage1_non_streaming(novel_text, out_dir)

    characters = parser.found_chars
    scenes = parser.found_scenes

    # Post-stream: 尝试从完整响应中恢复更多资产
    print(f"    -> 尝试从完整响应中恢复资产...")
    try:
        parsed = extract_json_robust(full_response)
        if isinstance(parsed, dict):
            parsed_chars = parsed.get("characters", [])
            parsed_scenes = parsed.get("scenes", [])
            if len(parsed_chars) > len(characters):
                print(f"    [OK] 完整解析恢复更多角色: {len(characters)} -> {len(parsed_chars)}")
                characters = parsed_chars
                for i, c in enumerate(characters):
                    _save_json(chars_dir / f"char_{i:02d}_{_safe(c.get('name', ''))}.json", c)
            if len(parsed_scenes) > len(scenes):
                print(f"    [OK] 完整解析恢复更多场景: {len(scenes)} -> {len(parsed_scenes)}")
                scenes = parsed_scenes
                _clean_scene_files(scenes_dir)
                for i, s in enumerate(scenes):
                    s["scene_id"] = f"scene_{i + 1:03d}"
                    if "order" not in s:
                        s["order"] = i
                    _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)
    except Exception as e:
        print(f"    [!] 完整JSON解析失败(可能截断): {e}")

    # 场景去重
    scenes = _dedup_scenes(scenes)
    if scenes:
        _clean_scene_files(scenes_dir)
        for i, s in enumerate(scenes):
            _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)

    # R20 修复: 场景不足 OR 响应截断 → 独立提取
    SCENE_MIN_THRESHOLD = 15
    truncated = is_truncated(full_response)
    need_fallback = False
    if truncated and len(characters) > 0:
        reason = f"响应被截断(当前{len(scenes)}个场景, 可能有遗漏)"
        need_fallback = True
    elif len(scenes) < SCENE_MIN_THRESHOLD and len(characters) > 0:
        reason = f"场景过少({len(scenes)}个, 阈值={SCENE_MIN_THRESHOLD})"
        need_fallback = True

    if need_fallback:
        print(f"    [!!] {reason} -> 触发独立场景提取")
        try:
            fallback_scenes = await stage1_scene_fallback(novel_text, characters, scenes_dir)
            if len(fallback_scenes) > len(scenes):
                print(f"    [OK] 独立提取恢复更多场景: {len(scenes)} -> {len(fallback_scenes)}")
                scenes = fallback_scenes
            else:
                print(f"    [--] 独立提取未获得更多场景({len(fallback_scenes)} vs {len(scenes)}), 保留原结果")
        except Exception as e:
            print(f"    [X] 独立场景提取异常 (保留已有{len(scenes)}个场景): {type(e).__name__}: {e}")

    char_names = [c.get("name", "?") for c in characters]
    chars_with_vneg = sum(1 for c in characters if c.get("visual_prompt_negative"))
    chars_with_vref = sum(1 for c in characters if c.get("visual_reference"))
    print(f"    [OK] 阶段1完成: {len(characters)} 角色, {len(scenes)} 叙事场景")
    print(f"      角色视觉: {chars_with_vref}/{len(characters)} 有 visual_reference, "
          f"{chars_with_vneg}/{len(characters)} 有 visual_prompt_negative")

    st_coverage = _source_text_coverage(scenes)
    print(f"      原文定位: 覆盖率 {st_coverage['coverage_pct']:.0f}%")

    meta = {
        "streaming": True,
        "total_time_s": round(total_time, 2),
        "time_to_first_char_s": char_export_log[0]["time_s"] if char_export_log else None,
        "num_characters": len(characters),
        "num_scenes": len(scenes),
        "num_chars_streamed": len(char_export_log),
        "num_scenes_streamed": len(scene_export_log),
        "character_names": char_names,
        "stream_chunks": chunk_count,
        "response_buffer_chars": response_total_chars,
        "buffer_capped": response_total_chars >= MAX_BUFFER,
        "source_text_coverage": st_coverage,
        "r20_gpt_adaptive_tokens": adaptive_tokens,
    }
    return characters, scenes, meta


async def stage1_non_streaming(novel_text: str, out_dir: Path) -> tuple[list, list, dict]:
    """Stage 1 降级: 非流式 + 模拟渐进解析."""
    chars_dir = out_dir / "characters"
    scenes_dir = out_dir / "narrative_scenes"
    chars_dir.mkdir(parents=True, exist_ok=True)
    scenes_dir.mkdir(parents=True, exist_ok=True)

    rendered = render_prompt("P_COMBINED_EXTRACT", text=novel_text[:80000])
    rendered["user"] += _R13_STAGE1_SUPPLEMENT
    adaptive_tokens = estimate_max_tokens(len(novel_text[:80000]), MODEL_CFG["model_id"])
    max_tokens = max(rendered["max_tokens"], adaptive_tokens)

    print(f"    -> 阶段1(降级): 非流式调用...", end="", flush=True)
    t0 = time.time()

    raw, cost = await smart_call(
        rendered["system"], rendered["user"],
        temperature=rendered["temperature"], max_tokens=max_tokens,
    )
    total_time = time.time() - t0
    print(f" {total_time:.1f}s")

    parser = ProgressiveAssetParser()
    char_count = 0
    scene_count = 0

    for ch in raw:
        result = parser.feed(ch)
        for char in result["characters"]:
            name = char.get("name", f"unknown_{char_count}")
            _save_json(chars_dir / f"char_{char_count:02d}_{_safe(name)}.json", char)
            print(f"      [OK] 角色卡(模拟): {name}")
            char_count += 1
        for scene_obj in result["scenes"]:
            scene_id = f"scene_{scene_count + 1:03d}"
            scene_obj["scene_id"] = scene_id
            if "order" not in scene_obj:
                scene_obj["order"] = scene_count
            loc = scene_obj.get("location", f"unnamed_{scene_count}")
            _save_json(scenes_dir / f"{scene_id}_{_safe(loc)}.json", scene_obj)
            print(f"      [OK] 叙事场景(模拟): [{scene_id}] {loc}")
            scene_count += 1

    characters = parser.found_chars
    scenes = parser.found_scenes

    dbg = out_dir / "_debug"
    dbg.mkdir(exist_ok=True)
    (dbg / "stage1_raw.txt").write_text(raw, encoding="utf-8")

    # 从完整响应恢复
    try:
        parsed = extract_json_robust(raw)
        if isinstance(parsed, dict):
            parsed_chars = parsed.get("characters", [])
            parsed_scenes = parsed.get("scenes", [])
            if len(parsed_chars) > len(characters):
                characters = parsed_chars
                for i, c in enumerate(characters):
                    _save_json(chars_dir / f"char_{i:02d}_{_safe(c.get('name', ''))}.json", c)
            if len(parsed_scenes) > len(scenes):
                scenes = parsed_scenes
                _clean_scene_files(scenes_dir)
                for i, s in enumerate(scenes):
                    s["scene_id"] = f"scene_{i + 1:03d}"
                    if "order" not in s:
                        s["order"] = i
                    _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)
    except Exception as e:
        print(f"    [!] JSON解析失败: {e}")

    scenes = _dedup_scenes(scenes)
    if scenes:
        _clean_scene_files(scenes_dir)
        for i, s in enumerate(scenes):
            _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)

    SCENE_MIN_THRESHOLD = 15
    truncated_ns = is_truncated(raw)
    need_fallback_ns = False
    if truncated_ns and len(characters) > 0:
        reason_ns = f"响应被截断(当前{len(scenes)}个场景)"
        need_fallback_ns = True
    elif len(scenes) < SCENE_MIN_THRESHOLD and len(characters) > 0:
        reason_ns = f"场景过少({len(scenes)}个, 阈值={SCENE_MIN_THRESHOLD})"
        need_fallback_ns = True

    if need_fallback_ns:
        print(f"    [!!] {reason_ns} -> 触发独立场景提取")
        try:
            fallback_scenes = await stage1_scene_fallback(novel_text, characters, scenes_dir)
            if len(fallback_scenes) > len(scenes):
                print(f"    [OK] 独立提取恢复更多场景: {len(scenes)} -> {len(fallback_scenes)}")
                scenes = fallback_scenes
            else:
                print(f"    [--] 独立提取未获得更多场景, 保留原结果")
        except Exception as e:
            print(f"    [X] 独立场景提取异常: {e}")

    char_names = [c.get("name", "?") for c in characters]
    chars_with_vneg = sum(1 for c in characters if c.get("visual_prompt_negative"))
    chars_with_vref = sum(1 for c in characters if c.get("visual_reference"))
    print(f"    [OK] 阶段1完成: {len(characters)} 角色, {len(scenes)} 叙事场景")
    print(f"      角色视觉: {chars_with_vref}/{len(characters)} 有 visual_reference, "
          f"{chars_with_vneg}/{len(characters)} 有 visual_prompt_negative")

    st_coverage = _source_text_coverage(scenes)
    meta = {
        "streaming": False,
        "total_time_s": round(total_time, 2),
        "num_characters": len(characters),
        "num_scenes": len(scenes),
        "character_names": char_names,
        "costs": [cost],
        "source_text_coverage": st_coverage,
    }
    return characters, scenes, meta


async def stage1_scene_fallback(novel_text: str, characters: list,
                                 scenes_dir: Path) -> list:
    """独立场景提取 fallback."""
    char_names = [c.get("name", "") for c in characters]
    names_str = ", ".join(char_names)

    rendered = render_prompt(
        "P04_SCENE_EXTRACT",
        text=novel_text[:80000],
        character_names=names_str,
        previous_scene_summary="无（独立场景提取模式）",
        window_index="0",
    )

    fallback_max_tokens = max(rendered["max_tokens"], 16000)
    print(f"      -> 独立场景提取中 (max_tokens={fallback_max_tokens})...", end="", flush=True)
    raw, cost = await smart_call(
        rendered["system"], rendered["user"],
        temperature=rendered["temperature"], max_tokens=fallback_max_tokens,
    )
    print(f" {cost.get('elapsed_s', '?')}s")

    scenes = []
    try:
        parsed = extract_json_robust(raw)
        if isinstance(parsed, dict):
            scenes = parsed.get("scenes", [parsed])
        elif isinstance(parsed, list):
            scenes = parsed
    except Exception as e:
        print(f"      [X] 场景解析失败: {e}")
        scenes = []

    _clean_scene_files(scenes_dir)
    for i, s in enumerate(scenes):
        if isinstance(s, dict):
            s["scene_id"] = f"scene_{i + 1:03d}"
            if "order" not in s:
                s["order"] = i
            _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)

    print(f"      [OK] 独立提取: {len(scenes)} 叙事场景")
    return scenes


# ===================================================================
#  Stage 2: 位置卡 + 道具卡 (并行)
# ===================================================================

async def _gen_location_batch(batch_groups: dict, novel_text: str,
                              out_dir: Path, batch_idx: int) -> list:
    """生成一批位置卡 (R20: 分批并行)."""
    snippets = []
    for loc_name in batch_groups:
        for m in re.finditer(re.escape(loc_name), novel_text):
            start = max(0, m.start() - 150)
            end = min(len(novel_text), m.end() + 150)
            snippets.append(f"[{loc_name}] ...{novel_text[start:end]}...")
            if len(snippets) >= 10:
                break
        if len(snippets) >= 10:
            break

    groups_json = json.dumps(batch_groups, ensure_ascii=False, indent=2)
    rendered = render_prompt(
        "P_LOCATION_CARD",
        location_groups_json=groups_json,
        relevant_text_snippets="\n".join(snippets[:10]),
    )

    t0 = time.time()
    raw, cost = await smart_call(
        rendered["system"], rendered["user"],
        temperature=rendered["temperature"], max_tokens=rendered["max_tokens"],
    )
    elapsed = time.time() - t0
    print(f"      [batch {batch_idx+1}] 位置卡批次完成: {len(batch_groups)}个位置, {elapsed:.1f}s", flush=True)

    dbg = out_dir / "_debug"
    dbg.mkdir(exist_ok=True)
    (dbg / f"stage2_locations_batch{batch_idx}.txt").write_text(raw, encoding="utf-8")

    try:
        cards = extract_json_robust(raw)
        if not isinstance(cards, list):
            cards = [cards]
        return cards
    except Exception as e:
        print(f"      [batch {batch_idx+1}] 位置卡解析失败: {e}")
        return []


async def _gen_location_cards(groups: dict, novel_text: str, out_dir: Path) -> list:
    """R20: 位置卡分批并行生成."""
    if not groups:
        return []

    # 分批: 每批最多 4 个位置 (R23: 从5降到4, 减小单批负载)
    BATCH_SIZE = 4
    loc_names = list(groups.keys())
    batches = []
    for i in range(0, len(loc_names), BATCH_SIZE):
        batch_keys = loc_names[i:i + BATCH_SIZE]
        batch_groups = {k: groups[k] for k in batch_keys}
        batches.append(batch_groups)

    print(f"      -> R20 位置卡分批并行: {len(groups)}个位置, 分{len(batches)}批(每批≤{BATCH_SIZE}个)...", flush=True)
    t0 = time.time()

    tasks = [
        asyncio.create_task(_gen_location_batch(batch, novel_text, out_dir, idx))
        for idx, batch in enumerate(batches)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_cards = []
    for r in results:
        if isinstance(r, list):
            all_cards.extend(r)
        elif isinstance(r, Exception):
            print(f"      [!!] 批次异常: {type(r).__name__}: {r}")

    loc_dir = out_dir / "locations"
    loc_dir.mkdir(exist_ok=True)
    for old_f in loc_dir.glob("loc_*.json"):
        old_f.unlink()
    for i, c in enumerate(all_cards):
        c["location_id"] = f"loc_{i + 1:03d}"
        _save_json(loc_dir / f"{c['location_id']}_{_safe(c.get('name', ''))}.json", c)

    total_time = time.time() - t0
    print(f"      [OK] 位置卡: {len(all_cards)} 张 (并行总耗时 {total_time:.1f}s)", flush=True)
    return all_cards


async def _gen_prop_cards(prop_data: dict, novel_text: str, out_dir: Path):
    props_dir = out_dir / "props"
    props_dir.mkdir(exist_ok=True)
    _save_json(props_dir / "prop_index.json", prop_data)

    if not prop_data["major"]:
        print(f"      无major道具，跳过道具卡生成")
        return

    prop_list_str = json.dumps(prop_data["major"], ensure_ascii=False, indent=2)
    snippets = []
    for prop_name in prop_data["major"]:
        for m in re.finditer(re.escape(prop_name), novel_text):
            start = max(0, m.start() - 100)
            end = min(len(novel_text), m.end() + 100)
            snippets.append(f"[{prop_name}] ...{novel_text[start:end]}...")
            if len(snippets) >= 20:
                break
        if len(snippets) >= 20:
            break

    rendered = render_prompt(
        "P_PROP_CARD",
        prop_list_with_scenes=prop_list_str,
        relevant_text_snippets="\n".join(snippets[:20]),
    )

    print(f"      -> 道具卡生成中...", end="", flush=True)
    raw, cost = await smart_call(
        rendered["system"], rendered["user"],
        temperature=rendered["temperature"], max_tokens=rendered["max_tokens"],
    )
    print(f" {cost.get('elapsed_s', '?')}s")

    dbg = out_dir / "_debug"
    dbg.mkdir(exist_ok=True)
    (dbg / "stage2_props_raw.txt").write_text(raw, encoding="utf-8")

    try:
        prop_cards = extract_json_robust(raw)
        if not isinstance(prop_cards, list):
            prop_cards = [prop_cards]
        for c in prop_cards:
            _save_json(props_dir / f"prop_major_{_safe(c.get('name', ''))}.json", c)
        print(f"      [OK] 道具卡: {len(prop_cards)} 张")
    except Exception as e:
        print(f"      [!!] 道具卡解析失败: {e}")


async def stage2_enrichment(characters: list, scenes: list,
                            novel_text: str, out_dir: Path) -> tuple[list, dict]:
    print(f"\n    阶段2: 后处理 (并行模式)...")

    groups = group_scenes_by_location(scenes)
    print(f"      地点分组: {len(groups)} 个唯一地点")

    raw_prop_data = collect_and_tier_props(scenes)
    prop_data = _retier_props(raw_prop_data, MAJOR_PROP_TOP_N)
    print(f"      道具 (Top{MAJOR_PROP_TOP_N}): {prop_data['total_unique']} 种 "
          f"(major: {prop_data['major_count']}, minor: {prop_data['minor_count']})")

    loc_task = asyncio.create_task(_gen_location_cards(groups, novel_text, out_dir))
    prop_task = asyncio.create_task(_gen_prop_cards(prop_data, novel_text, out_dir))

    location_cards = await loc_task
    await prop_task

    return location_cards, prop_data


# ===================================================================
#  Stage 3: 角色变体
# ===================================================================

async def stage3_variants(characters: list, scenes: list, out_dir: Path) -> list:
    print(f"\n    阶段3: 角色变体生成...")

    eligible = []
    for char in characters:
        role = char.get("role", "")
        name = char.get("name", "")
        sc = sum(1 for s in scenes if name in s.get("characters_present", []))
        if role in ("protagonist", "antagonist"):
            eligible.append((char, sc))
        elif role == "supporting" and sc >= 5:
            eligible.append((char, sc))

    if not eligible:
        print(f"      无符合条件的角色")
        return []

    print(f"      符合条件: {len(eligible)} 个角色")
    variants_dir = out_dir / "variants"
    variants_dir.mkdir(exist_ok=True)

    all_variants = []
    variant_sem = asyncio.Semaphore(4)  # R20: 从2提升到4

    async def gen_variant(char, sc):
        name = char.get("name", "unnamed")
        char_scenes = [s for s in scenes if name in s.get("characters_present", [])]

        rendered = render_prompt(
            "P_CHARACTER_VARIANT",
            character_card_json=json.dumps(char, ensure_ascii=False, indent=2),
            character_scenes_json=json.dumps(char_scenes, ensure_ascii=False, indent=2),
        )

        async with variant_sem:
            raw, cost = await smart_call(
                rendered["system"], rendered["user"],
                temperature=rendered["temperature"], max_tokens=rendered["max_tokens"],
            )

        try:
            variants = extract_json_robust(raw)
            if not isinstance(variants, list):
                variants = [variants]
            for v in variants:
                v_type = v.get("variant_type", "unknown")
                _save_json(variants_dir / f"variant_{_safe(name)}_{_safe(v_type)}.json", v)
            print(f"      -> {name}: {len(variants)} 个变体")
            return variants
        except Exception as e:
            print(f"      [!!] {name} 变体解析失败: {e}")
            return []

    tasks = [gen_variant(char, sc) for char, sc in eligible]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, list):
            all_variants.extend(r)

    total = len(all_variants)
    vars_with_vneg = sum(1 for v in all_variants if v.get("visual_prompt_negative"))
    vars_with_vref = sum(1 for v in all_variants if v.get("visual_reference"))
    print(f"      [OK] 变体总计: {total} 个")
    print(f"        变体视觉: {vars_with_vref}/{total} 有 visual_reference, "
          f"{vars_with_vneg}/{total} 有 visual_prompt_negative")
    return all_variants


# ===================================================================
#  R25: 双流式流水线管线
# ===================================================================

async def _stream_characters(novel_text: str, out_dir: Path) -> tuple[list, dict]:
    """R25: 角色独立流式提取."""
    parser = ProgressiveAssetParser()
    chars_dir = out_dir / "characters"
    chars_dir.mkdir(parents=True, exist_ok=True)
    char_export_log = []
    response_chunks: list[str] = []
    response_total_chars = 0
    MAX_BUFFER = 500_000
    chunk_count = 0
    char_count = 0

    user_text = _CHAR_ONLY_USER.replace("{text}", novel_text[:80000])
    max_tokens = 25000

    print(f"    [角色流] 启动 (max_tokens={max_tokens})...", flush=True)
    t0 = time.time()

    try:
        async for chunk in stream_api_call(_CHAR_ONLY_SYSTEM, user_text, 0.5, max_tokens):
            if response_total_chars < MAX_BUFFER:
                response_chunks.append(chunk)
                response_total_chars += len(chunk)
            chunk_count += 1
            result = parser.feed(chunk)
            for char in result["characters"]:
                # R29: 严格过滤垃圾对象
                if not _is_valid_char(char):
                    continue
                t_now = time.time() - t0
                name = char.get("name")
                char_export_log.append({"name": name, "time_s": round(t_now, 2)})
                _save_json(chars_dir / f"char_{char_count:02d}_{_safe(name)}.json", char)
                print(f"      [角色] {name} @ {t_now:.1f}s")
                char_count += 1
    except Exception as e:
        print(f"      [角色流] 异常: {type(e).__name__}: {e}")

    total_time = time.time() - t0
    full_response = "".join(response_chunks)

    # 完整响应恢复 (优先用 robust 解析, 质量更高)
    characters = [c for c in parser.found_chars if _is_valid_char(c)]  # R29: 严格过滤
    try:
        parsed = extract_json_robust(full_response)
        parsed_chars = []
        if isinstance(parsed, dict):
            parsed_chars = parsed.get("characters", [])
        elif isinstance(parsed, list):
            parsed_chars = parsed

        # R29: 严格过滤
        parsed_chars = [c for c in parsed_chars if _is_valid_char(c)]

        if len(parsed_chars) >= len(characters) and parsed_chars:
            if len(parsed_chars) > len(characters):
                print(f"      [角色流] 恢复: {len(characters)} -> {len(parsed_chars)} 有效角色")
            characters = parsed_chars
    except Exception:
        pass

    # R29: 统一清理并重写 — 确保磁盘只有有效角色文件
    for old_f in chars_dir.glob("char_*.json"):
        old_f.unlink()
    for i, c in enumerate(characters):
        _save_json(chars_dir / f"char_{i:02d}_{_safe(c.get('name', ''))}.json", c)

    # 保存 debug
    dbg = out_dir / "_debug"
    dbg.mkdir(exist_ok=True)
    (dbg / "r24_chars_raw.txt").write_text(full_response, encoding="utf-8")

    chars_with_vref = sum(1 for c in characters if c.get("visual_reference"))
    chars_with_vneg = sum(1 for c in characters if c.get("visual_prompt_negative"))
    print(f"    [角色流] 完成: {len(characters)} 角色, {total_time:.1f}s "
          f"({chunk_count} chunks, {response_total_chars} chars)")
    print(f"      视觉: {chars_with_vref}/{len(characters)} vref, "
          f"{chars_with_vneg}/{len(characters)} vneg")

    meta = {
        "char_stream_time_s": round(total_time, 2),
        "char_stream_chunks": chunk_count,
        "char_stream_chars": response_total_chars,
        "time_to_first_char_s": char_export_log[0]["time_s"] if char_export_log else None,
    }
    return characters, meta


async def _stream_scenes_progressive(
    novel_text: str, out_dir: Path,
    loc_batch_tasks: list, loc_all_cards: list,
    streaming_scenes: list | None = None,
) -> tuple[list, dict]:
    """R25: 场景独立流式提取 + 渐进位置卡发射. R29: streaming_scenes 共享列表."""
    parser = ProgressiveAssetParser()
    parser._chars_closed = True  # 跳过角色扫描，直接扫场景

    scenes_dir = out_dir / "narrative_scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    scene_export_log = []
    response_chunks: list[str] = []
    response_total_chars = 0
    MAX_BUFFER = 500_000
    chunk_count = 0
    scene_count = 0

    # 渐进位置分组
    loc_groups = {}  # location -> group data
    unfired_locs = []  # 还没发批次的地点
    fired_locs = set()
    batch_idx = [0]
    LOC_BATCH_SIZE = 4

    def _add_scene_to_groups(scene_obj):
        """将场景加入位置分组，凑齐则发批次."""
        loc = scene_obj.get("location", "未知地点")
        if loc not in loc_groups:
            loc_groups[loc] = {
                "scene_ids": [],
                "time_variations": set(),
                "all_props": set(),
                "all_characters": set(),
                "events": [],
                "emotional_peaks": [],
            }
            if loc not in fired_locs:
                unfired_locs.append(loc)

        g = loc_groups[loc]
        g["scene_ids"].append(scene_obj.get("scene_id", ""))
        g["time_variations"].add(scene_obj.get("time_of_day", ""))
        g["all_props"].update(scene_obj.get("key_props", []))
        g["all_characters"].update(scene_obj.get("characters_present", []))
        g["events"].append(scene_obj.get("core_event", ""))
        g["emotional_peaks"].append(scene_obj.get("emotional_peak", ""))

        # 凑齐一批就发
        if len(unfired_locs) >= LOC_BATCH_SIZE:
            _fire_loc_batch()

    def _fire_loc_batch():
        """发射一批位置卡."""
        batch_locs = unfired_locs[:LOC_BATCH_SIZE]
        del unfired_locs[:LOC_BATCH_SIZE]
        batch_groups = {}
        for loc_name in batch_locs:
            g = loc_groups[loc_name]
            batch_groups[loc_name] = {
                "scene_ids": g["scene_ids"],
                "time_variations": sorted(g["time_variations"]),
                "all_props": sorted(g["all_props"]),
                "all_characters": sorted(g["all_characters"]),
                "events": g["events"],
                "emotional_peaks": g["emotional_peaks"],
            }
            fired_locs.add(loc_name)

        idx = batch_idx[0]
        batch_idx[0] += 1
        print(f"      [位置流水线] 发射 batch {idx+1}: {list(batch_groups.keys())}", flush=True)
        task = asyncio.create_task(
            _gen_location_batch(batch_groups, novel_text, out_dir, idx)
        )

        async def _collect(t, i):
            try:
                cards = await t
                loc_all_cards.extend(cards)
            except Exception as e:
                print(f"      [位置流水线] batch {i+1} 异常: {e}")

        loc_batch_tasks.append(asyncio.create_task(_collect(task, idx)))

    user_text = _SCENE_ONLY_USER.replace("{text}", novel_text[:80000])
    max_tokens = 36000  # R28: 精细切分修正, 场景更多

    print(f"    [场景流] 启动 (max_tokens={max_tokens})...", flush=True)
    t0 = time.time()

    try:
        async for chunk in stream_api_call(_SCENE_ONLY_SYSTEM, user_text, 0.5, max_tokens):
            if response_total_chars < MAX_BUFFER:
                response_chunks.append(chunk)
                response_total_chars += len(chunk)
            chunk_count += 1
            result = parser.feed(chunk)
            for scene_obj in result["scenes"]:
                t_now = time.time() - t0
                scene_id = f"scene_{scene_count + 1:03d}"
                scene_obj["scene_id"] = scene_id
                if "order" not in scene_obj:
                    scene_obj["order"] = scene_count
                loc = scene_obj.get("location", f"unnamed_{scene_count}")
                event = scene_obj.get("core_event", "")[:30]
                scene_export_log.append({"scene_id": scene_id, "location": loc, "time_s": round(t_now, 2)})
                _save_json(scenes_dir / f"{scene_id}_{_safe(loc)}.json", scene_obj)
                print(f"      [场景] [{scene_id}] {loc} - {event} @ {t_now:.1f}s")
                scene_count += 1
                _add_scene_to_groups(scene_obj)
                # R29: 实时共享给变体流水线
                if streaming_scenes is not None:
                    streaming_scenes.append(scene_obj)
    except Exception as e:
        print(f"      [场景流] 异常: {type(e).__name__}: {e}")

    total_time = time.time() - t0
    full_response = "".join(response_chunks)

    # 完整响应恢复
    scenes = parser.found_scenes
    try:
        parsed = extract_json_robust(full_response)
        if isinstance(parsed, dict):
            parsed_scenes = parsed.get("scenes", [])
            if len(parsed_scenes) > len(scenes):
                print(f"      [场景流] 恢复: {len(scenes)} -> {len(parsed_scenes)}")
                scenes = parsed_scenes
                _clean_scene_files(scenes_dir)
                for i, s in enumerate(scenes):
                    s["scene_id"] = f"scene_{i + 1:03d}"
                    if "order" not in s:
                        s["order"] = i
                    _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)
                    # 补充位置分组（恢复出来的新场景）
                    _add_scene_to_groups(s)
    except Exception:
        pass

    scenes = _dedup_scenes(scenes)
    if scenes:
        _clean_scene_files(scenes_dir)
        for i, s in enumerate(scenes):
            _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)

    # 发射剩余未满批次的位置
    if unfired_locs:
        _fire_loc_batch()

    # 保存 debug
    dbg = out_dir / "_debug"
    dbg.mkdir(exist_ok=True)
    (dbg / "r24_scenes_raw.txt").write_text(full_response, encoding="utf-8")

    st_coverage = _source_text_coverage(scenes)
    print(f"    [场景流] 完成: {len(scenes)} 场景, {total_time:.1f}s "
          f"({chunk_count} chunks, {response_total_chars} chars)")
    print(f"      原文覆盖: {st_coverage['coverage_pct']:.0f}%")
    print(f"      位置卡已发射: {batch_idx[0]} 批次, {len(fired_locs)} 个地点")

    meta = {
        "scene_stream_time_s": round(total_time, 2),
        "scene_stream_chunks": chunk_count,
        "scene_stream_chars": response_total_chars,
        "source_text_coverage": st_coverage,
        "loc_batches_fired": batch_idx[0],
    }
    return scenes, meta


async def run_mode_c(novel_text: str, out_dir: Path) -> dict:
    """R29: 变体提前启动(仅等角色) + loc_id 修复 + Event 解耦流水线."""
    print(f"\n{'=' * 60}")
    print(f"  [R32] 变体提前启动 + loc_id 修复 — GPT-5.4")
    print(f"  角色完成→立刻启动变体(不等场景) | 场景完成→启动道具+位置卡")
    print(f"{'=' * 60}")

    t0_total = time.time()
    characters = []
    scenes = []
    char_meta = {}
    scene_meta = {}
    location_cards = []
    prop_data = {"total_unique": 0, "major_count": 0, "minor_count": 0}
    all_variants = []
    status = "OK"
    error_msg = ""

    # 共享状态
    loc_batch_tasks = []
    loc_all_cards = []
    streaming_scenes = []  # R29: 场景实时共享给变体

    # Event 信号
    scenes_done = asyncio.Event()
    chars_done = asyncio.Event()

    t_scenes_done = [0.0]
    t_chars_done = [0.0]

    # R27: 时间表
    timeline = []
    def _ts(event_name):
        timeline.append({"event": event_name, "t": round(time.time() - t0_total, 2)})

    # ─── 角色流 ───
    async def _char_stream():
        nonlocal characters, char_meta
        _ts("char_stream_start")
        try:
            characters, char_meta = await _stream_characters(novel_text, out_dir)
        except Exception as e:
            print(f"    [!!] 角色流失败: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
        t_chars_done[0] = time.time() - t0_total
        _ts("char_stream_done")
        chars_done.set()

    # ─── 场景流 (含渐进位置卡发射) ───
    async def _scene_stream():
        nonlocal scenes, scene_meta
        _ts("scene_stream_start")
        try:
            scenes, scene_meta = await _stream_scenes_progressive(
                novel_text, out_dir, loc_batch_tasks, loc_all_cards,
                streaming_scenes=streaming_scenes)
        except Exception as e:
            print(f"    [!!] 场景流失败: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
        t_scenes_done[0] = time.time() - t0_total
        _ts("scene_stream_done")
        scenes_done.set()
        print(f"    [Event] 场景完成 @ {t_scenes_done[0]:.1f}s → 道具卡可启动", flush=True)

    # ─── 道具卡: 仅等场景 ───
    async def _run_props():
        nonlocal prop_data
        await scenes_done.wait()
        _ts("props_start")
        if scenes:
            try:
                raw_prop_data = collect_and_tier_props(scenes)
                prop_data = _retier_props(raw_prop_data, MAJOR_PROP_TOP_N)
                print(f"      道具 (Top{MAJOR_PROP_TOP_N}): {prop_data['total_unique']} 种 "
                      f"(major: {prop_data['major_count']}, minor: {prop_data['minor_count']})")
                await _gen_prop_cards(prop_data, novel_text, out_dir)
            except Exception as e:
                print(f"    [!!] 道具卡失败: {type(e).__name__}: {e}")
        _ts("props_done")

    # ─── 变体: R29 仅等角色完成, 用 streaming_scenes 快照 ───
    async def _run_variants():
        nonlocal all_variants
        await chars_done.wait()
        _ts("variants_start")
        # R29: 快照当前已到位的场景 (角色流结束时约75%场景已到位)
        snap_scenes = list(streaming_scenes)
        snap_count = len(snap_scenes)
        print(f"      [变体] 角色完成后启动, 当前已有 {snap_count} 个场景可用", flush=True)
        if characters and snap_scenes:
            try:
                all_variants = await stage3_variants(characters, snap_scenes, out_dir)
            except Exception as e:
                print(f"    [!!] 变体失败: {type(e).__name__}: {e}")
        elif characters and not snap_scenes:
            # 极端情况: 角色流比场景流快太多, 等场景到位
            print(f"      [变体] 场景尚未到位, 等待场景流...", flush=True)
            await scenes_done.wait()
            if scenes:
                try:
                    all_variants = await stage3_variants(characters, scenes, out_dir)
                except Exception as e:
                    print(f"    [!!] 变体失败: {type(e).__name__}: {e}")
        _ts("variants_done")

    # ─── 位置卡收尾: 仅等场景 (批次在场景流中已发射) ───
    async def _wait_loc_batches():
        await scenes_done.wait()
        _ts("loc_wait_start")
        if loc_batch_tasks:
            await asyncio.gather(*loc_batch_tasks, return_exceptions=True)
        loc_dir = out_dir / "locations"
        loc_dir.mkdir(exist_ok=True)
        # R29-fix: 强制覆盖 location_id, 避免 GPT 返回的批次内序号重复
        for old_f in loc_dir.glob("loc_*.json"):
            old_f.unlink()
        for i, c in enumerate(loc_all_cards):
            c["location_id"] = f"loc_{i + 1:03d}"
            _save_json(loc_dir / f"{c['location_id']}_{_safe(c.get('name', ''))}.json", c)
        _ts("loc_wait_done")
        print(f"      [OK] 位置卡: {len(loc_all_cards)} 张", flush=True)

    # ─── 全部并行: 流式 + 后处理同时跑 ───
    _ts("pipeline_start")
    print(f"\n    [R32] 全流水线启动...", flush=True)
    await asyncio.gather(
        _char_stream(),
        _scene_stream(),
        _run_props(),
        _run_variants(),
        _wait_loc_batches(),
    )
    _ts("pipeline_done")

    total_time = time.time() - t0_total
    location_cards = loc_all_cards

    status_mark = "OK" if status == "OK" else "FAIL"
    print(f"\n  [{status_mark}] R30 流水线完成: {total_time:.1f}s 总耗时")
    print(f"    角色流完成 @ {t_chars_done[0]:.1f}s | 场景流完成 @ {t_scenes_done[0]:.1f}s")
    print(f"    角色: {len(characters)}, 场景: {len(scenes)}, "
          f"位置卡: {len(location_cards)}, 变体: {len(all_variants)}")
    print(f"    道具 (Top{MAJOR_PROP_TOP_N}): {prop_data.get('total_unique', 0)} 种 "
          f"(major: {prop_data.get('major_count', 0)}, minor: {prop_data.get('minor_count', 0)})")

    # 文件一致性检查
    scenes_dir = out_dir / "narrative_scenes"
    if scenes_dir.exists():
        disk_files = list(scenes_dir.glob("scene_*.json"))
        if len(disk_files) != len(scenes):
            print(f"    [!!] 文件一致性: 磁盘{len(disk_files)}个 != manifest{len(scenes)}个 场景")
        else:
            print(f"    [OK] 文件一致性: 磁盘{len(disk_files)}个 == manifest{len(scenes)}个 场景")

    st_coverage = scene_meta.get("source_text_coverage", _source_text_coverage(scenes))

    if len(characters) == 0 or len(scenes) == 0:
        status = "FAILED"
        error_msg = f"pipeline_empty: chars={len(characters)}, scenes={len(scenes)}"

    result = {
        "model": MODEL_CFG["display_name"],
        "status": status,
        "test_round": "R32",
        "r32_architecture": "variants_early_start",
        "r32_optimizations": [
            "scene_fine_split_35_50_corrected",
            "flashback_independent",
            "emotion_turn_split",
            "scene_max_tokens_36k",
            "char_scene_parallel_stream",
            "progressive_loc_card_firing",
            "event_decoupled_props",
            "variants_after_chars_only",
            "streaming_scenes_snapshot",
            "loc_id_forced_sequential",
            "elastic_concurrency_10",
            "variant_sem_4",
        ],
        "streaming": True,
        "num_characters": len(characters),
        "num_scenes": len(scenes),
        "character_names": [c.get("name", "?") for c in characters],
        **char_meta,
        **scene_meta,
        "num_locations": len(location_cards),
        "num_props_total": prop_data.get("total_unique", 0),
        "num_props_major": prop_data.get("major_count", 0),
        "num_props_minor": prop_data.get("minor_count", 0),
        "num_variants": len(all_variants),
        "pipeline_total_time_s": round(total_time, 2),
        "char_done_at_s": round(t_chars_done[0], 2),
        "scenes_done_at_s": round(t_scenes_done[0], 2),
        "r20_major_prop_top_n": MAJOR_PROP_TOP_N,
        "r20_source_text_coverage": st_coverage,
        "r32_timeline": timeline,
    }
    if error_msg:
        result["error"] = error_msg

    _save_json(out_dir / "manifest.json", result)

    # R27: 输出时间表并保存到独立文件
    _save_json(out_dir.parent / "r32_timeline.json", timeline)
    print(f"\n  [R30 时间表]")
    for entry in timeline:
        print(f"    {entry['t']:>7.1f}s  {entry['event']}")

    return result


# ===================================================================
#  Main
# ===================================================================

async def main():
    print(f"{'=' * 70}")
    print(f"  R32 GPT-5.4 (OpenClaudeCode) 全流水线测试 (gpt-5.4)")
    print(f"  日期: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 70}")

    # Phase 0: 单元测试
    test_streaming_parser_hardening()

    # 加载小说
    novel_path = Path(__file__).parent.parent / "我和沈词的长子.txt"
    if not novel_path.exists():
        novel_path = Path(__file__).parent / "我和沈词的长子.txt"
    if not novel_path.exists():
        print(f"找不到测试小说文件: 我和沈词的长子.txt")
        sys.exit(1)

    novel_text = novel_path.read_text(encoding="gb18030")
    print(f"小说加载完成: {len(novel_text)} 字符")

    # 输出目录
    out_dir = Path(__file__).parent / "chatgpt"
    out_dir.mkdir(exist_ok=True)

    # 运行管线
    result = await run_mode_c(novel_text, out_dir)

    # 打印最终汇总
    print(f"\n{'=' * 70}")
    print(f"  R32 测试总结 — GPT-5.4 (OpenClaudeCode)")
    print(f"{'=' * 70}")
    print(f"  状态:    {result['status']}")
    print(f"  角色:    {result.get('num_characters', 0)}")
    print(f"  场景:    {result.get('num_scenes', 0)}")
    print(f"  位置卡:  {result.get('num_locations', 0)}")
    print(f"  道具M:   {result.get('num_props_major', 0)}")
    print(f"  变体:    {result.get('num_variants', 0)}")
    print(f"  原文%:   {result.get('r20_source_text_coverage', {}).get('coverage_pct', 0):.0f}%")
    print(f"  总耗时:  {result.get('pipeline_total_time_s', 0):.1f}s")
    print(f"  角色完成: {result.get('char_done_at_s', 0):.1f}s")
    print(f"  场景完成: {result.get('scenes_done_at_s', 0):.1f}s")
    if result.get("char_stream_time_s"):
        print(f"  角色流:  {result.get('char_stream_time_s', 0):.1f}s, "
              f"首卡 {result.get('time_to_first_char_s', '?')}s")
    if result.get("scene_stream_time_s"):
        print(f"  场景流:  {result.get('scene_stream_time_s', 0):.1f}s, "
              f"位置卡批次={result.get('loc_batches_fired', 0)}")

    print(f"\n  R31 基线 (DeepSeek): 角色=10, 场景=32, 位置卡=25, 变体=14, 原文=100%, 耗时=422.7s")
    print(f"  R32 合格标准: 角色>=6, 场景>=25, 位置>0, 变体>=8, 原文覆盖>=80%")

    # 合格判定
    passed = True
    checks = []
    if result.get("num_characters", 0) < 6:
        checks.append(f"角色不足: {result.get('num_characters', 0)} < 6")
        passed = False
    if result.get("num_scenes", 0) < 35:
        checks.append(f"场景不足: {result.get('num_scenes', 0)} < 35")
        passed = False
    if result.get("num_locations", 0) == 0:
        checks.append("位置卡为0")
        passed = False
    if result.get("num_variants", 0) < 8:
        checks.append(f"变体不足: {result.get('num_variants', 0)} < 8")
        passed = False
    cov = result.get("r20_source_text_coverage", {}).get("coverage_pct", 0)
    if cov < 80:
        checks.append(f"原文覆盖不足: {cov:.0f}% < 80%")
        passed = False

    if passed:
        print(f"\n  >> R32 GPT-5.4 全流水线测试 PASSED <<")
    else:
        print(f"\n  >> R32 GPT-5.4 全流水线测试 FAILED <<")
        for c in checks:
            print(f"    - {c}")

    print(f"{'=' * 70}")

    # 保存汇总
    _save_json(Path(__file__).parent / "r32_summary.json", result)
    print(f"\n结果已保存到: {Path(__file__).parent}")


if __name__ == "__main__":
    asyncio.run(main())
