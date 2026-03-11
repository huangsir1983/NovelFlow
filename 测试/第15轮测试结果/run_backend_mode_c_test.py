"""Mode C 后端全面重构 -- 4模型验证测试 (R15 正式版).

测试新管线: streaming -> locations+props(并行) -> variants
4个模型: ChatGPT (gpt-5.4), Claude (claude-opus-4-6), Gemini (gemini-2.5-pro), Grok (grok-4.20-beta)

R15 变更 (基于 R14):
  - 统一流式管线: 所有模型同GPT流程 (流式→非流式降级), 去掉Claude特殊分支
  - 全模型 needs_stream=True: Stage 2 也走流式 smart_call
  - Stage 2 并行: 位置卡 + 道具卡 asyncio.create_task 并发生成
  - 道具筛选: 从阈值制(≥3)改为频率 Top 10
  - 场景文件去重: _clean_scene_files 在所有写场景路径前调用

用法:
    python run_backend_mode_c_test.py                # 跑全部4个模型
    python run_backend_mode_c_test.py chatgpt        # 只跑ChatGPT
    python run_backend_mode_c_test.py claude gemini   # 跑Claude和Gemini
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

# 从后端导入新代码
from services.streaming_parser import (
    ProgressiveAssetParser, extract_json_robust,
    is_truncated, estimate_max_tokens,
)
from services.asset_enrichment import (
    group_scenes_by_location, collect_and_tier_props,
)
from services.prompt_templates import render_prompt

# ===================================================================
#  模型注册表
# ===================================================================

# API Keys
_OCC_KEY = "sk-S2HdTVByFCfJcZ3oM3BUBQio0CGtty7xA2aTHdCP9occt50e"
_COMFLY_KEY = "sk-4f5dNlvbRjwcwjsxGeWU2NqY8Yp4u9SaYZUeuAhQVrofzD6R"
_GCLI_KEY = "ghitavjlksjkvnklghrvjog"
_GROK_KEY = "V378STSBi6jAC9Gk"

MAX_RETRIES = 3
RETRY_WAIT_BASE = 20  # R14: 从10提升到20，代理断连恢复需要更长时间
RATE_LIMIT_WAIT = 30
MAX_CONCURRENT = 4

# R14: 道具筛选 — 从阈值制改为频率 Top N
MAJOR_PROP_TOP_N = 10

_semaphore = asyncio.Semaphore(MAX_CONCURRENT)

MODELS = {
    "chatgpt": {
        "model_id": "gpt-5.4",
        "display_name": "ChatGPT (gpt-5.4)",
        "api_type": "responses",  # Responses API
        "api_base": "https://www.openclaudecode.cn/v1/responses",
        "api_key": _OCC_KEY,
        "timeout": 600,
        "needs_stream": True,
    },
    "claude": {
        "model_id": "claude-opus-4-6",
        "display_name": "Claude (claude-opus-4-6)",
        "api_type": "openai_chat",  # OpenAI Chat Completions
        "api_base": "https://ai.comfly.chat/v1",
        "api_key": _COMFLY_KEY,
        "timeout": 600,
        "needs_stream": True,  # R14v2: 统一流式，同GPT
    },
    "gemini": {
        "model_id": "gemini-2.5-pro",
        "display_name": "Gemini (gemini-2.5-pro via comfly)",
        "api_type": "openai_chat",
        "api_base": "https://ai.comfly.chat/v1",
        "api_key": _COMFLY_KEY,
        "timeout": 600,
        "needs_stream": True,  # R14v2: 统一流式，同GPT
        "max_tokens_override": 32000,
    },
    "grok": {
        "model_id": "grok-4.20-beta",
        "display_name": "Grok (grok-4.20-beta)",
        "api_type": "openai_chat",
        "api_base": "https://yhgrok.xuhuanai.cn/v1",
        "api_key": _GROK_KEY,
        "timeout": 600,
        "needs_stream": True,  # R14v2: 统一流式，同GPT
        "max_tokens_override": 32000,
    },
}


# ===================================================================
#  API 调用函数 -- 同步 + 流式
# ===================================================================

def is_retryable(exc):
    if isinstance(exc, (httpx.ReadTimeout, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (500, 502, 524, 503, 504)
    return False


def is_rate_limited(exc):
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429
    return False


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


async def call_api(model_key: str, system: str, user: str,
                   temperature: float = 0.5, max_tokens: int = 8192) -> tuple[str, dict]:
    """非流式 API 调用 -- 带重试。"""
    cfg = MODELS[model_key]

    # R13: 模型特异化 max_tokens 上限
    if cfg.get("max_tokens_override"):
        max_tokens = min(max_tokens, cfg["max_tokens_override"])

    if cfg["api_type"] == "responses":
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
    else:
        headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        body = {
            "model": cfg["model_id"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        url = f"{cfg['api_base']}/chat/completions"

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
                    raise RuntimeError(f"SSE response parsed to empty text from {cfg['display_name']}")
                return text, {"model": cfg["display_name"], "elapsed_s": round(elapsed, 2),
                             "input_tokens": usage.get("prompt_tokens", usage.get("input_tokens", 0)),
                             "output_tokens": usage.get("completion_tokens", usage.get("output_tokens", 0))}

            data = resp.json()

            # Check for API-level errors
            if data.get("error"):
                err_msg = data["error"] if isinstance(data["error"], str) else data["error"].get("message", str(data["error"]))
                raise RuntimeError(f"API error from {cfg['display_name']}: {err_msg}")

            if cfg["api_type"] == "responses":
                output = data.get("output", [])
                text = output[0]["content"][0]["text"] if output and output[0].get("content") else ""
                if not text.strip():
                    raise RuntimeError(f"Responses API returned empty content from {cfg['display_name']}")
                usage = data.get("usage", {})
                return text, {"model": cfg["display_name"], "elapsed_s": round(elapsed, 2),
                             "input_tokens": usage.get("input_tokens", 0),
                             "output_tokens": usage.get("output_tokens", 0)}
            else:
                choices = data.get("choices", [])
                text = choices[0]["message"]["content"] if choices else ""
                if not text.strip():
                    raise RuntimeError(f"Chat API returned empty content from {cfg['display_name']}")
                usage = data.get("usage", {})
                return text, {"model": cfg["display_name"], "elapsed_s": round(elapsed, 2),
                             "input_tokens": usage.get("prompt_tokens", 0),
                             "output_tokens": usage.get("completion_tokens", 0)}

        except Exception as e:
            last_exc = e
            if is_rate_limited(e):
                print(f"    [!!] 429限流 ({cfg['display_name']}), 等待{RATE_LIMIT_WAIT}s...", flush=True)
                await asyncio.sleep(RATE_LIMIT_WAIT)
                continue
            # RuntimeError (empty response / API error) 也可重试
            if is_retryable(e) or isinstance(e, RuntimeError):
                if attempt < MAX_RETRIES:
                    wait = RETRY_WAIT_BASE * (attempt + 1)
                    print(f"    [!!] 重试 {attempt+1}/{MAX_RETRIES} ({cfg['display_name']}), 等待{wait}s: {type(e).__name__}: {e}", flush=True)
                    await asyncio.sleep(wait)
                    continue
            raise
    raise last_exc  # type: ignore


async def stream_api_call(model_key: str, system: str, user: str,
                          temperature: float = 0.5, max_tokens: int = 32000):
    """流式 API 调用 -- async generator, yield text chunks。"""
    cfg = MODELS[model_key]

    if cfg["api_type"] == "responses":
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
    else:
        headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        body = {
            "model": cfg["model_id"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        url = f"{cfg['api_base']}/chat/completions"

    async with _semaphore:
        async with httpx.AsyncClient(timeout=cfg["timeout"],
                                     follow_redirects=True) as client:
            async with client.stream("POST", url, json=body, headers=headers) as resp:
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

                    # OpenAI Chat format (Claude/Gemini/Grok via proxy)
                    if "choices" in data:
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content

                    # Responses API format (ChatGPT)
                    elif data.get("type") == "response.output_text.delta":
                        delta_text = data.get("delta", "")
                        if delta_text:
                            yield delta_text

                    # Anthropic Messages format (直连 Claude)
                    elif data.get("type") == "content_block_delta":
                        delta_obj = data.get("delta", {})
                        if delta_obj.get("type") == "text_delta":
                            text = delta_obj.get("text", "")
                            if text:
                                yield text


async def smart_call(model_key: str, system: str, user: str,
                     temperature: float = 0.5, max_tokens: int = 8192) -> tuple[str, dict]:
    """智能调用: 需要流式的模型用流式(拼全文返回), 其余用普通调用。

    流式返回空文本时也降级为非流式。
    """
    cfg = MODELS[model_key]
    if cfg.get("needs_stream"):
        full_text = ""
        t0 = time.time()
        try:
            async for chunk in stream_api_call(model_key, system, user, temperature, max_tokens):
                full_text += chunk
        except Exception as e:
            print(f"    [!] smart_call 流式异常: {type(e).__name__}: {e}", flush=True)
            if not full_text:
                return await call_api(model_key, system, user, temperature, max_tokens)
        elapsed = time.time() - t0
        # 流式成功但返回空文本 → 降级非流式
        if not full_text.strip():
            print(f"    [!] smart_call 流式返回空文本, 降级非流式...", flush=True)
            return await call_api(model_key, system, user, temperature, max_tokens)
        return full_text, {"model": cfg["display_name"], "elapsed_s": round(elapsed, 2),
                          "input_tokens": 0, "output_tokens": len(full_text) // 2}
    return await call_api(model_key, system, user, temperature, max_tokens)


# ===================================================================
#  R13 Stage 1 补充 prompt — 道具精简 + 原文定位
# ===================================================================

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
#  R14 修复一: 场景文件去重 — 清理函数
# ===================================================================

def _clean_scene_files(scenes_dir: Path):
    """清理旧场景文件，避免文件重复。在每次写场景文件前调用。"""
    for old_f in scenes_dir.glob("scene_*.json"):
        old_f.unlink()


# ===================================================================
#  R14 修复二: Claude 分段合并函数
# ===================================================================

def merge_characters(chars_a: list, chars_b: list) -> list:
    """合并两段的角色，按 name 去重，优先保留更完整的。"""
    by_name = {}
    for c in chars_a + chars_b:
        name = c.get("name", "")
        if not name:
            continue
        existing = by_name.get(name)
        if not existing:
            by_name[name] = c
        else:
            # 保留字段更多的那个
            if len(json.dumps(c, ensure_ascii=False)) > len(json.dumps(existing, ensure_ascii=False)):
                by_name[name] = c
    return list(by_name.values())


def merge_scenes(scenes_a: list, scenes_b: list) -> list:
    """合并两段的场景，去重，按 order 重新编号。"""
    seen = set()
    merged = []
    for s in scenes_a + scenes_b:
        if not isinstance(s, dict):
            continue
        loc = s.get("location", "")
        event = s.get("core_event", "")[:30]
        heading = s.get("heading", "")
        fp = f"{loc}|{event}|{heading}"
        if fp in seen:
            continue
        seen.add(fp)
        merged.append(s)
    # 重新编号
    for i, s in enumerate(merged):
        s["scene_id"] = f"scene_{i + 1:03d}"
        s["order"] = i
    return merged


async def _extract_segment(model_key: str, novel_segment: str,
                           segment_label: str, out_dir: Path) -> tuple[list, list]:
    """对一段小说文本执行非流式提取 (Claude 分段专用)。

    R14: 外层额外重试2次 (带30s冷却)，应对 comfly 代理频繁断连。
    """
    rendered = render_prompt("P_COMBINED_EXTRACT", text=novel_segment)
    rendered["user"] += _R13_STAGE1_SUPPLEMENT
    max_tokens = max(rendered["max_tokens"], 16000)

    OUTER_RETRIES = 2  # call_api 内部已有3次重试，外层再包2次
    last_exc = None
    for outer in range(OUTER_RETRIES + 1):
        try:
            if outer > 0:
                wait = 30 * outer
                print(f"    [!!] [{segment_label}] 外层重试 {outer}/{OUTER_RETRIES}, 冷却{wait}s...", flush=True)
                await asyncio.sleep(wait)

            print(f"    -> [{segment_label}] 非流式提取 (len={len(novel_segment)}, max_tokens={max_tokens})...",
                  end="", flush=True)
            raw, cost = await call_api(
                model_key, rendered["system"], rendered["user"],
                temperature=rendered["temperature"], max_tokens=max_tokens,
            )
            print(f" {cost.get('elapsed_s', '?')}s")

            # 保存 debug
            dbg = out_dir / "_debug"
            dbg.mkdir(exist_ok=True)
            (dbg / f"stage1_{segment_label}_raw.txt").write_text(raw, encoding="utf-8")

            characters = []
            scenes = []
            try:
                parsed = extract_json_robust(raw)
                if isinstance(parsed, dict):
                    characters = parsed.get("characters", [])
                    scenes = parsed.get("scenes", [])
            except Exception as e:
                print(f"    [!!] [{segment_label}] JSON解析失败: {e}")

            print(f"    [{segment_label}] 提取结果: {len(characters)} 角色, {len(scenes)} 场景")
            return characters, scenes

        except Exception as e:
            last_exc = e
            print(f"\n    [!!] [{segment_label}] 提取失败: {type(e).__name__}: {e}", flush=True)

    # 全部重试用完，抛出最后异常
    raise last_exc  # type: ignore


async def stage1_claude_split(model_key: str, novel_text: str,
                              out_dir: Path) -> tuple[list, list, dict]:
    """R14 Claude 专用: 分2段非流式提取 + 合并去重。

    规避 comfly 代理流式截断问题 (R13 中~1120 chunks截断，只提取到11个场景)。
    """
    chars_dir = out_dir / "characters"
    scenes_dir = out_dir / "narrative_scenes"
    chars_dir.mkdir(parents=True, exist_ok=True)
    scenes_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()

    # 从中间找换行符分割，避免截断句子
    mid = len(novel_text) // 2
    split_pos = novel_text.rfind('\n', mid - 500, mid + 500)
    if split_pos == -1:
        split_pos = mid

    part_a = novel_text[:split_pos]
    part_b = novel_text[split_pos:]
    print(f"    [R14 Claude分段] A={len(part_a)} 字符, B={len(part_b)} 字符, 分割点={split_pos}")

    # 各段独立提取 (段间冷却15s，避免comfly代理连续长请求断连)
    chars_a, scenes_a = await _extract_segment(model_key, part_a, "前半段", out_dir)
    print(f"    [冷却] 段间等待15s避免代理断连...")
    await asyncio.sleep(15)
    chars_b, scenes_b = await _extract_segment(model_key, part_b, "后半段", out_dir)

    # 合并去重
    characters = merge_characters(chars_a, chars_b)
    scenes = merge_scenes(scenes_a, scenes_b)
    total_time = time.time() - t0
    print(f"\n    [R14 Claude合并] {len(characters)} 角色, {len(scenes)} 场景 ({total_time:.1f}s)")

    # 清理并保存角色文件
    for f in chars_dir.glob("*.json"):
        f.unlink()
    for i, c in enumerate(characters):
        _save_json(chars_dir / f"char_{i:02d}_{_safe(c.get('name', ''))}.json", c)

    # R14: 清理旧场景文件再写入
    _clean_scene_files(scenes_dir)
    for s in scenes:
        _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)

    # source_text 覆盖率
    st_coverage = _source_text_coverage(scenes)
    print(f"    原文定位: 覆盖率 {st_coverage['coverage_pct']:.0f}%")

    char_names = [c.get("name", "?") for c in characters]
    chars_with_vneg = sum(1 for c in characters if c.get("visual_prompt_negative"))
    chars_with_vref = sum(1 for c in characters if c.get("visual_reference"))
    print(f"    [OK] 阶段1完成: {len(characters)} 角色, {len(scenes)} 叙事场景")
    print(f"      角色视觉: {chars_with_vref}/{len(characters)} 有 visual_reference, "
          f"{chars_with_vneg}/{len(characters)} 有 visual_prompt_negative")

    meta = {
        "streaming": False,
        "adapted_pipeline": "claude_split_2_segments",
        "total_time_s": round(total_time, 2),
        "num_characters": len(characters),
        "num_scenes": len(scenes),
        "character_names": char_names,
        "source_text_coverage": st_coverage,
        "segment_a_chars": len(chars_a),
        "segment_a_scenes": len(scenes_a),
        "segment_b_chars": len(chars_b),
        "segment_b_scenes": len(scenes_b),
    }
    return characters, scenes, meta


# ===================================================================
#  Stage 1: 流式合并提取 (角色+叙事场景)
# ===================================================================

async def stage1_streaming(model_key: str, novel_text: str,
                           out_dir: Path) -> tuple[list, list, dict]:
    """Stage 1: 真流式 + ProgressiveAssetParser 渐进导出。"""
    cfg = MODELS[model_key]
    parser = ProgressiveAssetParser()
    chars_dir = out_dir / "characters"
    scenes_dir = out_dir / "narrative_scenes"
    chars_dir.mkdir(parents=True, exist_ok=True)
    scenes_dir.mkdir(parents=True, exist_ok=True)

    char_export_log = []
    scene_export_log = []
    full_response = ""
    chunk_count = 0
    char_count = 0
    scene_count = 0

    rendered = render_prompt("P_COMBINED_EXTRACT", text=novel_text[:80000])
    # R13: 追加道具精简 + 原文定位要求
    rendered["user"] += _R13_STAGE1_SUPPLEMENT
    adaptive_tokens = estimate_max_tokens(len(novel_text[:80000]), cfg["model_id"])
    max_tokens = max(rendered["max_tokens"], adaptive_tokens)

    print(f"    -> 阶段1: 流式提取中 (max_tokens={max_tokens})...", flush=True)
    t0 = time.time()

    try:
        async for chunk in stream_api_call(
            model_key, rendered["system"], rendered["user"],
            temperature=rendered["temperature"], max_tokens=max_tokens,
        ):
            full_response += chunk
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
            return await stage1_non_streaming(model_key, novel_text, out_dir)

    total_time = time.time() - t0
    print(f"    流式完成 {total_time:.1f}s ({chunk_count} chunks)")

    # 立即保存 debug 原始响应
    dbg = out_dir / "_debug"
    dbg.mkdir(exist_ok=True)
    (dbg / "stage1_raw.txt").write_text(full_response, encoding="utf-8")

    if chunk_count == 0 or not full_response.strip():
        print(f"    -> 降级为非流式调用（无响应）...")
        return await stage1_non_streaming(model_key, novel_text, out_dir)

    # 流式chunks过少（<1000），且场景不足，降级为非流式重试
    if chunk_count < 1000 and len(parser.found_scenes) < 5:
        print(f"    [!!] 流式仅收到 {chunk_count} chunks 且场景不足({len(parser.found_scenes)}个)，降级为非流式重试...")
        return await stage1_non_streaming(model_key, novel_text, out_dir)

    characters = parser.found_chars
    scenes = parser.found_scenes

    # Post-stream: 总是尝试从完整响应中恢复更多资产
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
                # R14: 已有清理逻辑，保留
                for old_f in scenes_dir.glob("scene_*.json"):
                    old_f.unlink()
                for i, s in enumerate(scenes):
                    s["scene_id"] = f"scene_{i + 1:03d}"
                    if "order" not in s:
                        s["order"] = i
                    _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)
    except Exception as e:
        print(f"    [!] 完整JSON解析失败(可能截断): {e}")
        try:
            import re as _re
            scene_pattern = r'\{\s*"scene_id"\s*:\s*"[^"]*"[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            found = _re.findall(scene_pattern, full_response)
            recovered_scenes = []
            for s_text in found:
                try:
                    s_obj = json.loads(s_text)
                    recovered_scenes.append(s_obj)
                except:
                    pass
            if len(recovered_scenes) > len(scenes):
                print(f"    [OK] 正则恢复更多场景: {len(scenes)} -> {len(recovered_scenes)}")
                scenes = recovered_scenes
                # R14: 正则恢复路径 — 写文件前清理
                _clean_scene_files(scenes_dir)
                for i, s in enumerate(scenes):
                    if not s.get("scene_id"):
                        s["scene_id"] = f"scene_{i + 1:03d}"
                    if "order" not in s:
                        s["order"] = i
                    _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)
        except Exception as e2:
            print(f"    [!] 正则恢复也失败: {e2}")

    # 场景去重
    scenes = _dedup_scenes(scenes)
    if scenes:
        # R14: _dedup_scenes 后重写 — 写文件前清理
        _clean_scene_files(scenes_dir)
        for i, s in enumerate(scenes):
            _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)

    SCENE_MIN_THRESHOLD = 12
    if len(scenes) < SCENE_MIN_THRESHOLD and len(characters) > 0:
        reason = ""
        if is_truncated(full_response):
            reason = f"响应截断且场景不足({len(scenes)}个)"
        else:
            reason = f"场景过少({len(scenes)}个, 阈值={SCENE_MIN_THRESHOLD})"
        print(f"    [!!] {reason} -> 触发独立场景提取")
        try:
            fallback_scenes = await stage1_scene_fallback(model_key, novel_text, characters, scenes_dir)
            if len(fallback_scenes) > len(scenes):
                print(f"    [OK] 独立提取恢复更多场景: {len(scenes)} -> {len(fallback_scenes)}")
                scenes = fallback_scenes
            else:
                print(f"    [!] 独立提取未能恢复更多场景 ({len(fallback_scenes)} <= {len(scenes)})")
        except Exception as e:
            print(f"    [X] 独立场景提取异常 (保留已有{len(scenes)}个场景): {type(e).__name__}: {e}")

    char_names = [c.get("name", "?") for c in characters]

    # 验证 visual_prompt_negative 字段
    chars_with_vneg = sum(1 for c in characters if c.get("visual_prompt_negative"))
    chars_with_vref = sum(1 for c in characters if c.get("visual_reference"))
    print(f"    [OK] 阶段1完成: {len(characters)} 角色, {len(scenes)} 叙事场景")
    print(f"      角色视觉: {chars_with_vref}/{len(characters)} 有 visual_reference, "
          f"{chars_with_vneg}/{len(characters)} 有 visual_prompt_negative")

    # R13: source_text 覆盖率统计
    st_coverage = _source_text_coverage(scenes)
    print(f"      原文定位: {st_coverage['count_with_start']}/{len(scenes)} 有 source_text_start, "
          f"{st_coverage['count_with_end']}/{len(scenes)} 有 source_text_end "
          f"(覆盖率 {st_coverage['coverage_pct']:.0f}%)")

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
        "source_text_coverage": st_coverage,
    }
    return characters, scenes, meta


async def stage1_non_streaming(model_key: str, novel_text: str,
                                out_dir: Path) -> tuple[list, list, dict]:
    """Stage 1 降级: 非流式 + 模拟渐进解析。"""
    chars_dir = out_dir / "characters"
    scenes_dir = out_dir / "narrative_scenes"
    chars_dir.mkdir(parents=True, exist_ok=True)
    scenes_dir.mkdir(parents=True, exist_ok=True)

    rendered = render_prompt("P_COMBINED_EXTRACT", text=novel_text[:80000])
    # R13: 追加道具精简 + 原文定位要求
    rendered["user"] += _R13_STAGE1_SUPPLEMENT
    adaptive_tokens = estimate_max_tokens(len(novel_text[:80000]))
    max_tokens = max(rendered["max_tokens"], adaptive_tokens)

    print(f"    -> 阶段1(降级): 非流式调用...", end="", flush=True)
    t0 = time.time()

    raw, cost = await smart_call(
        model_key, rendered["system"], rendered["user"],
        temperature=rendered["temperature"], max_tokens=max_tokens,
    )
    total_time = time.time() - t0
    print(f" {total_time:.1f}s")

    # Simulated progressive parse
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

    # 立即保存 debug 原始响应
    dbg = out_dir / "_debug"
    dbg.mkdir(exist_ok=True)
    (dbg / "stage1_raw.txt").write_text(raw, encoding="utf-8")

    # 总是尝试从完整响应中恢复更多资产
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
                print(f"    [OK] 完整解析恢复更多场景: {len(scenes)} -> {len(parsed_scenes)}")
                scenes = parsed_scenes
                # R14: 非流式恢复路径 — 写文件前清理
                _clean_scene_files(scenes_dir)
                for i, s in enumerate(scenes):
                    s["scene_id"] = f"scene_{i + 1:03d}"
                    if "order" not in s:
                        s["order"] = i
                    _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)
    except Exception as e:
        print(f"    [!] JSON解析失败(可能截断): {e}")

    # 场景去重
    scenes = _dedup_scenes(scenes)
    # R14: _dedup_scenes 后重写场景文件 — 写文件前清理
    if scenes:
        _clean_scene_files(scenes_dir)
        for i, s in enumerate(scenes):
            _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)

    # 场景不足时触发独立场景提取
    SCENE_MIN_THRESHOLD = 12
    if len(scenes) < SCENE_MIN_THRESHOLD and len(characters) > 0:
        print(f"    [!!] 场景过少({len(scenes)}个, 阈值={SCENE_MIN_THRESHOLD}) -> 触发独立场景提取")
        try:
            fallback_scenes = await stage1_scene_fallback(model_key, novel_text, characters, scenes_dir)
            if len(fallback_scenes) > len(scenes):
                print(f"    [OK] 独立提取恢复更多场景: {len(scenes)} -> {len(fallback_scenes)}")
                scenes = fallback_scenes
            else:
                print(f"    [!] 独立提取未能恢复更多场景 ({len(fallback_scenes)} <= {len(scenes)})")
        except Exception as e:
            print(f"    [X] 独立场景提取异常 (保留已有{len(scenes)}个场景): {type(e).__name__}: {e}")

    char_names = [c.get("name", "?") for c in characters]

    # 验证 visual_prompt_negative 字段
    chars_with_vneg = sum(1 for c in characters if c.get("visual_prompt_negative"))
    chars_with_vref = sum(1 for c in characters if c.get("visual_reference"))
    print(f"    [OK] 阶段1完成: {len(characters)} 角色, {len(scenes)} 叙事场景")
    print(f"      角色视觉: {chars_with_vref}/{len(characters)} 有 visual_reference, "
          f"{chars_with_vneg}/{len(characters)} 有 visual_prompt_negative")

    # R13: source_text 覆盖率统计
    st_coverage = _source_text_coverage(scenes)
    print(f"      原文定位: {st_coverage['count_with_start']}/{len(scenes)} 有 source_text_start, "
          f"{st_coverage['count_with_end']}/{len(scenes)} 有 source_text_end "
          f"(覆盖率 {st_coverage['coverage_pct']:.0f}%)")

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


async def stage1_scene_fallback(model_key: str, novel_text: str,
                                 characters: list, scenes_dir: Path) -> list:
    """独立场景提取 fallback。"""
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
        model_key, rendered["system"], rendered["user"],
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
        else:
            scenes = [parsed]
    except Exception as e:
        print(f"      [X] 场景解析失败: {e}")
        try:
            dbg_path = scenes_dir.parent / "_debug"
            dbg_path.mkdir(exist_ok=True)
            (dbg_path / "scene_fallback_raw.txt").write_text(raw, encoding="utf-8")
        except:
            pass
        scenes = []

    # R14: 独立场景提取写文件前清理
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
#  Stage 2: 位置卡 + 道具收集 + 道具卡
#  R14v2: 位置卡 + 道具卡 并行生成
# ===================================================================

async def _gen_location_cards(model_key: str, groups: dict,
                               novel_text: str, out_dir: Path) -> list:
    """位置卡生成子任务 (可并行)。"""
    if not groups:
        return []

    SNIPPET_LIMIT = 15
    snippets = []
    for loc_name in groups:
        for m in re.finditer(re.escape(loc_name), novel_text):
            start = max(0, m.start() - 150)
            end = min(len(novel_text), m.end() + 150)
            snippets.append(f"[{loc_name}] ...{novel_text[start:end]}...")
            if len(snippets) >= SNIPPET_LIMIT:
                break
        if len(snippets) >= SNIPPET_LIMIT:
            break

    groups_json = json.dumps(groups, ensure_ascii=False, indent=2)
    rendered = render_prompt(
        "P_LOCATION_CARD",
        location_groups_json=groups_json,
        relevant_text_snippets="\n".join(snippets[:SNIPPET_LIMIT]),
    )

    print(f"      -> 位置卡生成中(流式)...", end="", flush=True)
    try:
        raw, cost = await smart_call(
            model_key, rendered["system"], rendered["user"],
            temperature=rendered["temperature"], max_tokens=rendered["max_tokens"],
        )
    except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ReadTimeout) as e:
        print(f"\n      [!!] 代理断连, 等待15s重试... ({type(e).__name__})")
        await asyncio.sleep(15)
        raw, cost = await smart_call(
            model_key, rendered["system"], rendered["user"],
            temperature=rendered["temperature"], max_tokens=rendered["max_tokens"],
        )
    print(f" {cost.get('elapsed_s', '?')}s")

    dbg = out_dir / "_debug"
    dbg.mkdir(exist_ok=True)
    (dbg / "stage2_locations_raw.txt").write_text(raw, encoding="utf-8")

    try:
        cards = extract_json_robust(raw)
        if not isinstance(cards, list):
            cards = [cards]
        loc_dir = out_dir / "locations"
        loc_dir.mkdir(exist_ok=True)
        for i, c in enumerate(cards):
            c.setdefault("location_id", f"loc_{i + 1:03d}")
            _save_json(loc_dir / f"{c['location_id']}_{_safe(c.get('name', ''))}.json", c)
        print(f"      [OK] 位置卡: {len(cards)} 张")
        return cards
    except Exception as e:
        print(f"      [!!] 位置卡解析失败: {e}, 重试1次...")
        try:
            await asyncio.sleep(10)
            raw2, cost2 = await smart_call(
                model_key, rendered["system"], rendered["user"],
                temperature=rendered["temperature"], max_tokens=rendered["max_tokens"],
            )
            (dbg / "stage2_locations_raw_retry.txt").write_text(raw2, encoding="utf-8")
            cards = extract_json_robust(raw2)
            if not isinstance(cards, list):
                cards = [cards]
            loc_dir = out_dir / "locations"
            loc_dir.mkdir(exist_ok=True)
            for i, c in enumerate(cards):
                c.setdefault("location_id", f"loc_{i + 1:03d}")
                _save_json(loc_dir / f"{c['location_id']}_{_safe(c.get('name', ''))}.json", c)
            print(f"      [OK] 位置卡(重试): {len(cards)} 张")
            return cards
        except Exception as e2:
            print(f"      [X] 位置卡重试也失败: {e2}")
            return []


async def _gen_prop_cards(model_key: str, prop_data: dict,
                           novel_text: str, out_dir: Path):
    """道具卡生成子任务 (可并行)。"""
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

    print(f"      -> 道具卡生成中(流式)...", end="", flush=True)
    raw, cost = await smart_call(
        model_key, rendered["system"], rendered["user"],
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


async def stage2_enrichment(model_key: str, characters: list, scenes: list,
                            novel_text: str, out_dir: Path) -> tuple[list, dict]:
    """Stage 2: Location cards + Prop cards — 并行生成。

    R14v2: 位置卡和道具卡并行调用，减少 Stage 间等待时间。
    """
    print(f"\n    阶段2: 后处理 (并行模式)...")

    # 即时计算: 地点分组 + 道具统计
    groups = group_scenes_by_location(scenes)
    print(f"      地点分组: {len(groups)} 个唯一地点")

    raw_prop_data = collect_and_tier_props(scenes)
    prop_data = _retier_props(raw_prop_data, MAJOR_PROP_TOP_N)
    print(f"      道具 (R14 Top{MAJOR_PROP_TOP_N}): {prop_data['total_unique']} 种 "
          f"(major: {prop_data['major_count']}, minor: {prop_data['minor_count']})")

    # 并行: 位置卡 + 道具卡同时生成
    loc_task = asyncio.create_task(_gen_location_cards(model_key, groups, novel_text, out_dir))
    prop_task = asyncio.create_task(_gen_prop_cards(model_key, prop_data, novel_text, out_dir))

    location_cards = await loc_task
    await prop_task

    print(f"      [R13] 跳过 Stage 2D: minor 道具视觉生成（已精简）")

    return location_cards, prop_data


# ===================================================================
#  Stage 3: 角色变体
# ===================================================================

async def stage3_variants(model_key: str, characters: list, scenes: list,
                          out_dir: Path) -> list:
    """Stage 3: Character variant generation."""
    print(f"\n    阶段3: 角色变体生成...")

    # Filter eligible characters
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
    variant_sem = asyncio.Semaphore(2)

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
                model_key, rendered["system"], rendered["user"],
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
#  完整 Mode C 管线
# ===================================================================

async def run_mode_c(model_key: str, novel_text: str, out_dir: Path) -> dict:
    """完整 Mode C 管线: Stage 1 + Stage 2 + Stage 3.

    R14v2 优化:
    - 统一管线: 所有模型同GPT流程 (流式 → 非流式降级)
    - Stage 2 并行: 位置卡 + 道具卡同时生成
    - 全模型流式: needs_stream=True, smart_call 走流式
    - 场景文件去重: _clean_scene_files
    """
    cfg = MODELS[model_key]
    print(f"\n{'=' * 60}")
    print(f"  [{cfg['display_name']}] Mode C Full Asset Pipeline (R15)")
    print(f"{'=' * 60}")

    t0_total = time.time()
    characters = []
    scenes = []
    s1_meta = {}
    location_cards = []
    prop_data = {"total_unique": 0, "major_count": 0, "minor_count": 0}
    all_variants = []
    status = "OK"
    error_msg = ""
    retry_info = None

    # Stage 1: 统一流式管线 (所有模型同GPT流程: 流式 → 非流式降级)
    try:
        characters, scenes, s1_meta = await stage1_streaming(model_key, novel_text, out_dir)
    except Exception as e:
        print(f"    [!!] 流式不可用: {type(e).__name__}: {e}")
        try:
            characters, scenes, s1_meta = await stage1_non_streaming(model_key, novel_text, out_dir)
        except Exception as e2:
            print(f"    [X] 非流式也失败: {type(e2).__name__}: {e2}")
            status = "FAILED"
            error_msg = f"stage1: {e2}"

    # R13: Stage 1 跑空检测 — 角色或场景数为0，自动触发非流式重试
    if status == "OK" and (len(characters) == 0 or len(scenes) == 0):
        print(f"    [!!] Stage 1 跑空 (角色={len(characters)}, 场景={len(scenes)}), 触发非流式重试...")
        retry_info = {"reason": "stage1_empty", "original_chars": len(characters), "original_scenes": len(scenes)}
        try:
            characters, scenes, s1_meta = await stage1_non_streaming(model_key, novel_text, out_dir)
            retry_info["retry_chars"] = len(characters)
            retry_info["retry_scenes"] = len(scenes)
            if len(characters) == 0 and len(scenes) == 0:
                status = "FAILED"
                error_msg = "stage1: empty after retry"
        except Exception as e:
            print(f"    [X] 重试也失败: {type(e).__name__}: {e}")
            status = "FAILED"
            error_msg = f"stage1_retry: {e}"

    # Stage 2: Location cards + Props (only if stage 1 produced data)
    if characters or scenes:
        try:
            location_cards, prop_data = await stage2_enrichment(
                model_key, characters, scenes, novel_text, out_dir)
        except Exception as e:
            print(f"    [!!] 阶段2失败: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

        # Stage 3: Character variants
        try:
            all_variants = await stage3_variants(model_key, characters, scenes, out_dir)
        except Exception as e:
            print(f"    [!!] 阶段3失败: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    total_time = time.time() - t0_total
    status_emoji = "OK" if status == "OK" else "FAIL"
    print(f"\n  [{status_emoji}] {cfg['display_name']} Mode C 完成: {total_time:.1f}s 总耗时")
    print(f"    角色: {len(characters)}, 场景: {len(scenes)}, "
          f"位置卡: {len(location_cards)}, 变体: {len(all_variants)}")
    print(f"    道具 (Top{MAJOR_PROP_TOP_N}): {prop_data.get('total_unique', 0)} 种 "
          f"(major: {prop_data.get('major_count', 0)}, minor: {prop_data.get('minor_count', 0)})")

    # R14: 文件一致性检查
    scenes_dir = out_dir / "narrative_scenes"
    if scenes_dir.exists():
        disk_files = list(scenes_dir.glob("scene_*.json"))
        if len(disk_files) != len(scenes):
            print(f"    [!!] 文件一致性: 磁盘{len(disk_files)}个 != manifest{len(scenes)}个 场景")
        else:
            print(f"    [OK] 文件一致性: 磁盘{len(disk_files)}个 == manifest{len(scenes)}个 场景")

    # R13/R14: source_text 覆盖率
    st_coverage = s1_meta.get("source_text_coverage", _source_text_coverage(scenes))

    result = {
        "model": cfg["display_name"],
        "status": status,
        **s1_meta,
        "num_locations": len(location_cards),
        "num_props_total": prop_data.get("total_unique", 0),
        "num_props_major": prop_data.get("major_count", 0),
        "num_props_minor": prop_data.get("minor_count", 0),
        "minor_props_with_visual": 0,  # R13: 跳过 Stage 2D
        "num_variants": len(all_variants),
        "pipeline_total_time_s": round(total_time, 2),
        "r14_major_prop_top_n": MAJOR_PROP_TOP_N,
        "r13_source_text_coverage": st_coverage,
        "r14_fixes": ["unified_streaming_pipeline", "clean_scene_files", "parallel_stage2", "prop_top_n"],
    }
    if error_msg:
        result["error"] = error_msg
    if retry_info:
        result["retry_info"] = retry_info

    # manifest 始终写入
    _save_json(out_dir / "manifest.json", result)

    return result


# ===================================================================
#  工具函数
# ===================================================================

def _safe(name: str) -> str:
    """Sanitize string for filename."""
    return re.sub(r'[^\w\u4e00-\u9fff-]', '_', name)[:30]


def _save_json(path: Path, data):
    """Save JSON to file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _dedup_scenes(scenes: list) -> list:
    """去重场景 — 基于 (location, core_event) 指纹去重。"""
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
    """R13: 计算 source_text_start / source_text_end 覆盖率。"""
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
    """R14: 按出现频率取 Top N 作为 major 道具，其余为 minor。"""
    # 合并所有道具到一个字典
    all_props = {}
    for name, info in raw_prop_data.get("major", {}).items():
        all_props[name] = info
    for name, info in raw_prop_data.get("minor", {}).items():
        all_props[name] = info

    # 按 count 降序排序，取前 top_n 个作为 major
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
#  Main
# ===================================================================

async def main():
    # 解析命令行参数
    model_shortcuts = {
        "chatgpt": "chatgpt", "gpt": "chatgpt",
        "claude": "claude",
        "gemini": "gemini",
        "grok": "grok",
    }

    if len(sys.argv) > 1:
        requested = []
        for arg in sys.argv[1:]:
            key = model_shortcuts.get(arg.lower())
            if key:
                requested.append(key)
            else:
                print(f"未知模型: {arg}, 可用: {list(model_shortcuts.keys())}")
                sys.exit(1)
    else:
        requested = ["chatgpt", "claude", "gemini", "grok"]

    # 加载小说
    novel_path = Path(__file__).parent / "我和沈词的长子.txt"
    if not novel_path.exists():
        novel_path = Path(__file__).parent.parent / "我和沈词的长子.txt"
    if not novel_path.exists():
        print(f"找不到测试小说文件: 我和沈词的长子.txt")
        sys.exit(1)

    novel_text = novel_path.read_text(encoding="gb18030")
    print(f"小说加载完成: {len(novel_text)} 字符")
    print(f"模型: {', '.join(MODELS[k]['display_name'] for k in requested)}")
    print(f"R15 配置: 统一流式管线, Stage2并行, 道具Top{MAJOR_PROP_TOP_N}, 场景文件去重")

    # 创建输出目录
    base_out = Path(__file__).parent / "backend_mode_c_results"
    base_out.mkdir(exist_ok=True)

    # 逐个运行
    all_results = []
    for model_key in requested:
        out_dir = base_out / model_key
        out_dir.mkdir(exist_ok=True)

        result = await run_mode_c(model_key, novel_text, out_dir)
        all_results.append(result)

    # 打印汇总
    print(f"\n{'=' * 80}")
    print(f"  Summary -- Mode C Backend Pipeline R15 (4-Model Test)")
    print(f"  R15: 统一流式管线 | Stage2并行 | 道具Top{MAJOR_PROP_TOP_N} | 场景去重")
    print(f"  道具: Top{MAJOR_PROP_TOP_N} | minor视觉: 跳过 | 原文定位: 启用")
    print(f"{'=' * 80}")
    print(f"{'模型':<30} {'状态':<8} {'角色':<6} {'场景':<6} "
          f"{'位置':<6} {'道具M':<7} {'变体':<6} {'原文%':>6} {'耗时':>8}")
    print("-" * 80)
    for r in all_results:
        status = r.get("status", "?")
        model = r.get("model", "?")
        st_cov = r.get("r13_source_text_coverage", {})
        if status == "OK":
            print(f"{model:<30} {'OK':<8} "
                  f"{r.get('num_characters', 0):<6} "
                  f"{r.get('num_scenes', 0):<6} "
                  f"{r.get('num_locations', 0):<6} "
                  f"{r.get('num_props_major', 0):<7} "
                  f"{r.get('num_variants', 0):<6} "
                  f"{st_cov.get('coverage_pct', 0):>5.0f}% "
                  f"{r.get('pipeline_total_time_s', 0):>7.1f}s")
        else:
            err = r.get("error", "")[:40]
            print(f"{model:<30} {'FAIL':<8} "
                  f"{r.get('num_characters', '--'):<6} "
                  f"{r.get('num_scenes', '--'):<6} "
                  f"{'--':<6} {'--':<7} {'--':<6} "
                  f"{'--':>6} "
                  f"[ERR] {err}")
    print("=" * 80)

    # R12 基线对比 + R14 验证标准
    print(f"\n  R12 ChatGPT 基线参考: 角色=8, 场景=25, 位置=23, major道具=20, 变体=26")
    print(f"  R15 合格标准: 角色≥6, 场景≥15, 位置>0, 变体≥8, 原文覆盖≥80%, 文件数==场景数")

    # Save summary
    _save_json(base_out / "summary.json", all_results)
    print(f"\n结果已保存到: {base_out}")


if __name__ == "__main__":
    asyncio.run(main())
