"""Mode C 后端全面重构 -- 4模型验证测试 (R13 加固版).

测试新管线: streaming -> locations -> props -> variants
4个模型: ChatGPT (gpt-5.4), Claude (claude-opus-4-6), Gemini (gemini-3.1-pro-preview), Grok (grok-4.20-beta)

R13 加固:
  - Fix: Gemini 流式失败时 fallback 更健壮，增加空响应检测与重试
  - Fix: stage1 debug 文件在流式完成后立即写入（不再等到 post-processing 之后）
  - Fix: 场景 fallback 独立提取用 try/except 包裹，防止 stage1 整体崩溃
  - Fix: 场景不足阈值从 10 提高到 12，匹配 R10 水平
  - Fix: run_mode_c 保证 manifest.json 始终写入（即使 stage2/3 崩溃）

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
#  模型注册表 -- 直接从 model_adapters.py / run_test_round10.py 移植
# ===================================================================

# API Keys
_OCC_KEY = "sk-S2HdTVByFCfJcZ3oM3BUBQio0CGtty7xA2aTHdCP9occt50e"
_COMFLY_KEY = "sk-4f5dNlvbRjwcwjsxGeWU2NqY8Yp4u9SaYZUeuAhQVrofzD6R"
_GCLI_KEY = "ghitavjlksjkvnklghrvjog"
_GROK_KEY = "V378STSBi6jAC9Gk"

MAX_RETRIES = 3
RETRY_WAIT_BASE = 10
RATE_LIMIT_WAIT = 30
MAX_CONCURRENT = 4

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
        "needs_stream": True,
    },
    "gemini": {
        "model_id": "gemini-3.1-pro-preview",
        "display_name": "Gemini (gemini-3.1-pro-preview)",
        "api_type": "openai_chat",
        "api_base": "https://yhgcli.xuhuanai.cn/v1",
        "api_key": _GCLI_KEY,
        "timeout": 600,
        "needs_stream": False,  # R13: GCLI 代理流式不稳定，改为非流式 + smart_call fallback
    },
    "grok": {
        "model_id": "grok-4.20-beta",
        "display_name": "Grok (grok-4.20-beta)",
        "api_type": "openai_chat",
        "api_base": "https://yhgrok.xuhuanai.cn/v1",
        "api_key": _GROK_KEY,
        "timeout": 600,
        "needs_stream": False,
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

            # R13: Check for API-level errors
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
            # R13: RuntimeError (empty response / API error) 也可重试
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

    R13: 流式返回空文本时也降级为非流式。
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
        # R13: 流式成功但返回空文本 → 降级非流式
        if not full_text.strip():
            print(f"    [!] smart_call 流式返回空文本, 降级非流式...", flush=True)
            return await call_api(model_key, system, user, temperature, max_tokens)
        return full_text, {"model": cfg["display_name"], "elapsed_s": round(elapsed, 2),
                          "input_tokens": 0, "output_tokens": len(full_text) // 2}
    return await call_api(model_key, system, user, temperature, max_tokens)


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
    # 追加场景数量强调到用户提示词
    rendered["user"] += (
        "\n\n【重要补充要求】\n"
        "1. 确保至少提取15个以上的叙事场景，仔细检查是否遗漏了时空跳转点\n"
        "2. 每个场景的 key_props 列出所有可见道具，但同类道具归为一组（如'各色酒盏'而非分列每个杯子）\n"
        "3. visual_reference 和 visual_prompt_negative 必须使用中文\n"
    )
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
            # 加固6: 降级为非流式
            print(f"      -> 降级为非流式调用...")
            return await stage1_non_streaming(model_key, novel_text, out_dir)

    total_time = time.time() - t0
    print(f"    流式完成 {total_time:.1f}s ({chunk_count} chunks)")

    # R13: 立即保存 debug 原始响应（无论后续处理是否成功）
    dbg = out_dir / "_debug"
    dbg.mkdir(exist_ok=True)
    (dbg / "stage1_raw.txt").write_text(full_response, encoding="utf-8")

    if chunk_count == 0 or not full_response.strip():
        print(f"    -> 降级为非流式调用（无响应）...")
        return await stage1_non_streaming(model_key, novel_text, out_dir)

    # 加固: 流式chunks过少（<1000），且场景不足，降级为非流式重试
    if chunk_count < 1000 and len(parser.found_scenes) < 5:
        print(f"    [!!] 流式仅收到 {chunk_count} chunks 且场景不足({len(parser.found_scenes)}个)，降级为非流式重试...")
        return await stage1_non_streaming(model_key, novel_text, out_dir)

    characters = parser.found_chars
    scenes = parser.found_scenes

    # Post-stream: 总是尝试从完整响应中恢复更多资产（处理截断/渐进解析遗漏）
    print(f"    -> 尝试从完整响应中恢复资产...")
    try:
        parsed = extract_json_robust(full_response)
        if isinstance(parsed, dict):
            parsed_chars = parsed.get("characters", [])
            parsed_scenes = parsed.get("scenes", [])
            # 如果完整解析得到更多角色，用完整解析的结果
            if len(parsed_chars) > len(characters):
                print(f"    [OK] 完整解析恢复更多角色: {len(characters)} -> {len(parsed_chars)}")
                characters = parsed_chars
                for i, c in enumerate(characters):
                    _save_json(chars_dir / f"char_{i:02d}_{_safe(c.get('name', ''))}.json", c)
            # 如果完整解析得到更多场景，用完整解析的结果
            if len(parsed_scenes) > len(scenes):
                print(f"    [OK] 完整解析恢复更多场景: {len(scenes)} -> {len(parsed_scenes)}")
                scenes = parsed_scenes
                # R13: 清理旧的流式场景文件，避免目录中残留不一致的旧文件
                for old_f in scenes_dir.glob("scene_*.json"):
                    old_f.unlink()
                for i, s in enumerate(scenes):
                    s["scene_id"] = f"scene_{i + 1:03d}"
                    if "order" not in s:
                        s["order"] = i
                    _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)
    except Exception as e:
        print(f"    [!] 完整JSON解析失败(可能截断): {e}")
        # 截断情况: 尝试从原始文本中逐个提取完整的scene对象
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
                for i, s in enumerate(scenes):
                    if not s.get("scene_id"):
                        s["scene_id"] = f"scene_{i + 1:03d}"
                    if "order" not in s:
                        s["order"] = i
                    _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)
        except Exception as e2:
            print(f"    [!] 正则恢复也失败: {e2}")

    # R13: 场景去重（LLM 可能输出完全相同的场景）
    scenes = _dedup_scenes(scenes)
    if scenes:
        for i, s in enumerate(scenes):
            _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)

    # R13: 合并截断检测和场景不足检测（阈值从10提升到12，匹配R10水平）
    SCENE_MIN_THRESHOLD = 12  # R10 平均 15+ 场景
    if len(scenes) < SCENE_MIN_THRESHOLD and len(characters) > 0:
        reason = ""
        if is_truncated(full_response):
            reason = f"响应截断且场景不足({len(scenes)}个)"
        else:
            reason = f"场景过少({len(scenes)}个, 阈值={SCENE_MIN_THRESHOLD})"
        print(f"    [!!] {reason} -> 触发独立场景提取")
        # R13: 用 try/except 包裹 fallback，防止崩溃拖垮整个 stage1
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
    # 追加场景数量强调到用户提示词
    rendered["user"] += (
        "\n\n【重要补充要求】\n"
        "1. 确保至少提取15个以上的叙事场景，仔细检查是否遗漏了时空跳转点\n"
        "2. 每个场景的 key_props 列出所有可见道具，但同类道具归为一组（如'各色酒盏'而非分列每个杯子）\n"
        "3. visual_reference 和 visual_prompt_negative 必须使用中文\n"
    )
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

    # R13: 立即保存 debug 原始响应
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
                for i, s in enumerate(scenes):
                    s["scene_id"] = f"scene_{i + 1:03d}"
                    if "order" not in s:
                        s["order"] = i
                    _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)
    except Exception as e:
        print(f"    [!] JSON解析失败(可能截断): {e}")

    # R13: 场景去重
    scenes = _dedup_scenes(scenes)

    # R13: 场景不足时触发独立场景提取（阈值提升到12，与流式一致）
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

    meta = {
        "streaming": False,
        "total_time_s": round(total_time, 2),
        "num_characters": len(characters),
        "num_scenes": len(scenes),
        "character_names": char_names,
        "costs": [cost],
    }
    return characters, scenes, meta


async def stage1_scene_fallback(model_key: str, novel_text: str,
                                 characters: list, scenes_dir: Path) -> list:
    """加固5: 独立场景提取。

    R13 加固: max_tokens 提升到 16000（8192 不够提取 15+ 场景），增加重试。
    """
    char_names = [c.get("name", "") for c in characters]
    names_str = ", ".join(char_names)

    rendered = render_prompt(
        "P04_SCENE_EXTRACT",
        text=novel_text[:80000],
        character_names=names_str,
        previous_scene_summary="无（独立场景提取模式）",
        window_index="0",
    )

    # R13: 提升 max_tokens 到 16000（8192 不够 15+ 场景的完整JSON输出）
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
        # R13: 写入 fallback debug 以便事后分析
        try:
            dbg_path = scenes_dir.parent / "_debug"
            dbg_path.mkdir(exist_ok=True)
            (dbg_path / "scene_fallback_raw.txt").write_text(raw, encoding="utf-8")
        except:
            pass
        scenes = []

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
# ===================================================================

async def stage2_enrichment(model_key: str, characters: list, scenes: list,
                            novel_text: str, out_dir: Path) -> tuple[list, dict, list]:
    """Stage 2: Location cards + Prop collection + Prop cards + Minor prop visuals."""
    print(f"\n    阶段2: 后处理...")

    # 2A: Location cards
    groups = group_scenes_by_location(scenes)
    print(f"      地点分组: {len(groups)} 个唯一地点")

    location_cards = []
    if groups:
        snippets = []
        for loc_name in groups:
            for m in re.finditer(re.escape(loc_name), novel_text):
                start = max(0, m.start() - 150)
                end = min(len(novel_text), m.end() + 150)
                snippets.append(f"[{loc_name}] ...{novel_text[start:end]}...")
                if len(snippets) >= 30:
                    break
            if len(snippets) >= 30:
                break

        groups_json = json.dumps(groups, ensure_ascii=False, indent=2)
        rendered = render_prompt(
            "P_LOCATION_CARD",
            location_groups_json=groups_json,
            relevant_text_snippets="\n".join(snippets[:30]),
        )

        print(f"      -> 位置卡生成中...", end="", flush=True)
        raw, cost = await smart_call(
            model_key, rendered["system"], rendered["user"],
            temperature=rendered["temperature"], max_tokens=rendered["max_tokens"],
        )
        print(f" {cost.get('elapsed_s', '?')}s")

        # 保存位置卡原始响应到 _debug
        dbg = out_dir / "_debug"
        dbg.mkdir(exist_ok=True)
        (dbg / "stage2_locations_raw.txt").write_text(raw, encoding="utf-8")

        try:
            cards = extract_json_robust(raw)
            if not isinstance(cards, list):
                cards = [cards]
            location_cards = cards
            loc_dir = out_dir / "locations"
            loc_dir.mkdir(exist_ok=True)
            for i, c in enumerate(cards):
                c.setdefault("location_id", f"loc_{i + 1:03d}")
                _save_json(loc_dir / f"{c['location_id']}_{_safe(c.get('name', ''))}.json", c)
            print(f"      [OK] 位置卡: {len(cards)} 张")
            locs_with_vneg = sum(1 for c in cards if c.get("visual_prompt_negative"))
            locs_with_vref = sum(1 for c in cards if c.get("visual_reference"))
            print(f"        位置视觉: {locs_with_vref}/{len(cards)} 有 visual_reference, "
                  f"{locs_with_vneg}/{len(cards)} 有 visual_prompt_negative")
        except Exception as e:
            print(f"      [!!] 位置卡解析失败: {e}, 重试1次...")
            # 重试1次
            try:
                raw2, cost2 = await smart_call(
                    model_key, rendered["system"], rendered["user"],
                    temperature=rendered["temperature"], max_tokens=rendered["max_tokens"],
                )
                (dbg / "stage2_locations_raw_retry.txt").write_text(raw2, encoding="utf-8")
                cards = extract_json_robust(raw2)
                if not isinstance(cards, list):
                    cards = [cards]
                location_cards = cards
                loc_dir = out_dir / "locations"
                loc_dir.mkdir(exist_ok=True)
                for i, c in enumerate(cards):
                    c.setdefault("location_id", f"loc_{i + 1:03d}")
                    _save_json(loc_dir / f"{c['location_id']}_{_safe(c.get('name', ''))}.json", c)
                print(f"      [OK] 位置卡(重试): {len(cards)} 张")
            except Exception as e2:
                print(f"      [X] 位置卡重试也失败: {e2}")

    # 2B: Prop collection
    prop_data = collect_and_tier_props(scenes)
    print(f"      道具: {prop_data['total_unique']} 种 "
          f"(major: {prop_data['major_count']}, minor: {prop_data['minor_count']})")

    props_dir = out_dir / "props"
    props_dir.mkdir(exist_ok=True)
    _save_json(props_dir / "prop_index.json", prop_data)

    # 2C: Prop cards (major only)
    if prop_data["major"]:
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
            model_key, rendered["system"], rendered["user"],
            temperature=rendered["temperature"], max_tokens=rendered["max_tokens"],
        )
        print(f" {cost.get('elapsed_s', '?')}s")

        # 保存道具卡原始响应到 _debug
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
            props_with_vneg = sum(1 for c in prop_cards if c.get("visual_prompt_negative"))
            props_with_vref = sum(1 for c in prop_cards if c.get("visual_reference"))
            print(f"        道具视觉: {props_with_vref}/{len(prop_cards)} 有 visual_reference, "
                  f"{props_with_vneg}/{len(prop_cards)} 有 visual_prompt_negative")
        except Exception as e:
            print(f"      [!!] 道具卡解析失败: {e}")
    else:
        print(f"      无major道具，跳过道具卡生成")

    # 2D: Minor prop visual generation
    minor_prop_visuals = []
    if prop_data["minor"]:
        print(f"      -> Minor道具视觉生成中 ({prop_data['minor_count']} 个)...", end="", flush=True)
        try:
            prop_list = [
                {"name": name, "scenes": info.get("scenes", []), "count": info.get("count", 0)}
                for name, info in prop_data["minor"].items()
            ]
            rendered = render_prompt(
                "P_MINOR_PROP_VISUAL",
                era_context="从小说自动推断",
                minor_props_json=json.dumps(prop_list, ensure_ascii=False, indent=2),
            )
            raw, cost = await smart_call(
                model_key, rendered["system"], rendered["user"],
                temperature=rendered["temperature"], max_tokens=rendered["max_tokens"],
            )
            results = extract_json_robust(raw)
            if not isinstance(results, list):
                results = [results]
            minor_prop_visuals = results
            print(f" {len(minor_prop_visuals)} 个 ({cost.get('elapsed_s', '?')}s)")

            # 保存 minor prop 视觉数据
            for mpv in minor_prop_visuals:
                name = mpv.get("name", "unknown")
                _save_json(props_dir / f"prop_minor_{_safe(name)}.json", mpv)
            mpv_with_vneg = sum(1 for m in minor_prop_visuals if m.get("visual_prompt_negative"))
            mpv_with_vref = sum(1 for m in minor_prop_visuals if m.get("visual_reference"))
            print(f"        Minor道具视觉: {mpv_with_vref}/{len(minor_prop_visuals)} 有 visual_reference, "
                  f"{mpv_with_vneg}/{len(minor_prop_visuals)} 有 visual_prompt_negative")
        except Exception as e:
            print(f" 失败: {e}")
    else:
        print(f"      无minor道具，跳过minor道具视觉生成")

    return location_cards, prop_data, minor_prop_visuals


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

    R13 加固: manifest.json 始终写入，即使后续 stage 崩溃。
    """
    cfg = MODELS[model_key]
    print(f"\n{'=' * 60}")
    print(f"  [{cfg['display_name']}] Mode C Full Asset Pipeline")
    print(f"{'=' * 60}")

    t0_total = time.time()
    characters = []
    scenes = []
    s1_meta = {}
    location_cards = []
    prop_data = {"total_unique": 0, "major_count": 0, "minor_count": 0}
    minor_prop_visuals = []
    all_variants = []
    status = "OK"
    error_msg = ""

    # Stage 1: Streaming extraction
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

    # Stage 2: Location cards + Props (only if stage 1 produced data)
    if characters or scenes:
        try:
            location_cards, prop_data, minor_prop_visuals = await stage2_enrichment(
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
    print(f"    道具: {prop_data.get('total_unique', 0)} 种 "
          f"(major: {prop_data.get('major_count', 0)}, "
          f"minor_with_visual: {len(minor_prop_visuals)})")

    result = {
        "model": cfg["display_name"],
        "status": status,
        **s1_meta,
        "num_locations": len(location_cards),
        "num_props_total": prop_data.get("total_unique", 0),
        "num_props_major": prop_data.get("major_count", 0),
        "minor_props_with_visual": len(minor_prop_visuals),
        "num_variants": len(all_variants),
        "pipeline_total_time_s": round(total_time, 2),
    }
    if error_msg:
        result["error"] = error_msg

    # R13: manifest 始终写入（即使是 FAILED 状态）
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
    """R13: 去重场景 — 基于 (location, core_event) 指纹去重。

    LLM 有时会在 JSON 输出中生成完全相同的场景对象。
    用 location + core_event 前30字 作为指纹，保留首次出现的。
    """
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
        # 重新编号
        for i, s in enumerate(unique):
            s["scene_id"] = f"scene_{i + 1:03d}"
            s["order"] = i
    return unique


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
        # 尝试上级目录
        novel_path = Path(__file__).parent.parent / "我和沈词的长子.txt"
    if not novel_path.exists():
        print(f"找不到测试小说文件: 我和沈词的长子.txt")
        sys.exit(1)

    novel_text = novel_path.read_text(encoding="gb18030")
    print(f"小说加载完成: {len(novel_text)} 字符")
    print(f"模型: {', '.join(MODELS[k]['display_name'] for k in requested)}")

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
    print(f"\n{'=' * 70}")
    print(f"  Summary -- Mode C Backend Pipeline 4-Model Test")
    print(f"{'=' * 70}")
    print(f"{'模型':<30} {'状态':<8} {'角色':<6} {'场景':<6} "
          f"{'位置':<6} {'道具':<6} {'变体':<6} {'耗时':>8}")
    print("-" * 70)
    for r in all_results:
        status = r.get("status", "?")
        model = r.get("model", "?")
        if status == "OK":
            print(f"{model:<30} {'OK':<8} "
                  f"{r.get('num_characters', 0):<6} "
                  f"{r.get('num_scenes', 0):<6} "
                  f"{r.get('num_locations', 0):<6} "
                  f"{r.get('num_props_total', 0):<6} "
                  f"{r.get('num_variants', 0):<6} "
                  f"{r.get('pipeline_total_time_s', 0):>7.1f}s")
        else:
            err = r.get("error", "")[:40]
            stage = r.get("stage", "?")
            print(f"{model:<30} {'FAIL':<8} "
                  f"{'--':<6} {'--':<6} {'--':<6} {'--':<6} {'--':<6} "
                  f"[{stage}] {err}")
    print("=" * 70)

    # Save summary
    _save_json(base_out / "summary.json", all_results)
    print(f"\n结果已保存到: {base_out}")


if __name__ == "__main__":
    asyncio.run(main())
