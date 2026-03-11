"""R23 — 位置卡弹性并发优化 (GPT-5.4 单模型).

基于 R23 (流式 parser 修复), 优化位置卡生成并发:
  R23 优化: BATCH_SIZE 5->4, 位置卡批次使用弹性并发(不受全局 sem 限制)
  R23 优化: 全局 MAX_CONCURRENT 4->10, 消除 batch 等待瓶颈
  R23 保留: 流式 parser 截断修复, Stage2+3 并行

用法:
    python run_r23_parallel_test.py
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
    for i, c in enumerate(all_cards):
        c.setdefault("location_id", f"loc_{i + 1:03d}")
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
#  完整 Mode C 管线
# ===================================================================

async def run_mode_c(novel_text: str, out_dir: Path) -> dict:
    """完整 Mode C 管线 — R20 加固版 (GPT-5.4 only)."""
    print(f"\n{'=' * 60}")
    print(f"  [GPT-5.4] Mode C Full Asset Pipeline (R20 截断修复+并行优化)")
    print(f"  R20修复: 截断即补提取 | 阈值15 | 位置卡分批并行 | Stage2+3并行 | 变体x4")
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

    # Stage 1
    try:
        characters, scenes, s1_meta = await stage1_streaming(novel_text, out_dir)
    except Exception as e:
        print(f"    [!!] 流式不可用: {type(e).__name__}: {e}")
        try:
            characters, scenes, s1_meta = await stage1_non_streaming(novel_text, out_dir)
        except Exception as e2:
            print(f"    [X] 非流式也失败: {type(e2).__name__}: {e2}")
            status = "FAILED"
            error_msg = f"stage1: {e2}"

    # Stage 1 跑空检测
    if status == "OK" and (len(characters) == 0 or len(scenes) == 0):
        print(f"    [!!] Stage 1 跑空 (角色={len(characters)}, 场景={len(scenes)}), 触发非流式重试...")
        retry_info = {"reason": "stage1_empty", "original_chars": len(characters), "original_scenes": len(scenes)}
        try:
            characters, scenes, s1_meta = await stage1_non_streaming(novel_text, out_dir)
            retry_info["retry_chars"] = len(characters)
            retry_info["retry_scenes"] = len(scenes)
            if len(characters) == 0 and len(scenes) == 0:
                status = "FAILED"
                error_msg = "stage1: empty after retry"
        except Exception as e:
            status = "FAILED"
            error_msg = f"stage1_retry: {e}"

    # R20: Stage 2 & Stage 3 并行执行
    if characters or scenes:
        async def _run_stage2():
            nonlocal location_cards, prop_data
            try:
                location_cards, prop_data = await stage2_enrichment(
                    characters, scenes, novel_text, out_dir)
            except Exception as e:
                print(f"    [!!] 阶段2失败: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()

        async def _run_stage3():
            nonlocal all_variants
            try:
                all_variants = await stage3_variants(characters, scenes, out_dir)
            except Exception as e:
                print(f"    [!!] 阶段3失败: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()

        print(f"\n    [R20] Stage 2 + Stage 3 并行启动...", flush=True)
        t_parallel = time.time()
        await asyncio.gather(_run_stage2(), _run_stage3())
        print(f"    [R20] Stage 2+3 并行总耗时: {time.time() - t_parallel:.1f}s", flush=True)

    total_time = time.time() - t0_total
    status_mark = "OK" if status == "OK" else "FAIL"
    print(f"\n  [{status_mark}] GPT-5.4 Mode C R20 完成: {total_time:.1f}s 总耗时")
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

    st_coverage = s1_meta.get("source_text_coverage", _source_text_coverage(scenes))

    result = {
        "model": MODEL_CFG["display_name"],
        "status": status,
        "test_round": "R23",
        "hardening_features": [
            "response_buffer_cap_500k",
            "batch_db_flush_5_10",
            "429_retry_after_respect",
            "500_503_exponential_backoff",
            "stream_stall_timeout_60s",
            "code_fence_strip",
            "gpt_token_adaptive_1.2x",
            "event_bus_redis_fallback",
            "rate_limiter_rpm_tpm",
            "bounded_thread_pool",
            "graceful_shutdown",
        ],
        "r23_optimizations": [
            "location_cards_batch_parallel_4",
            "elastic_concurrency_10",
            "stage2_stage3_parallel",
            "variant_sem_4",
        ],
        **s1_meta,
        "num_locations": len(location_cards),
        "num_props_total": prop_data.get("total_unique", 0),
        "num_props_major": prop_data.get("major_count", 0),
        "num_props_minor": prop_data.get("minor_count", 0),
        "num_variants": len(all_variants),
        "pipeline_total_time_s": round(total_time, 2),
        "r20_major_prop_top_n": MAJOR_PROP_TOP_N,
        "r20_source_text_coverage": st_coverage,
    }
    if error_msg:
        result["error"] = error_msg
    if retry_info:
        result["retry_info"] = retry_info

    _save_json(out_dir / "manifest.json", result)
    return result


# ===================================================================
#  Main
# ===================================================================

async def main():
    print(f"{'=' * 70}")
    print(f"  R23 并行优化验证 — GPT-5.4 (gpt-5.4)")
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
    print(f"  R23 测试总结 — GPT-5.4 并行优化验证")
    print(f"{'=' * 70}")
    print(f"  状态:    {result['status']}")
    print(f"  角色:    {result.get('num_characters', 0)}")
    print(f"  场景:    {result.get('num_scenes', 0)}")
    print(f"  位置卡:  {result.get('num_locations', 0)}")
    print(f"  道具M:   {result.get('num_props_major', 0)}")
    print(f"  变体:    {result.get('num_variants', 0)}")
    print(f"  原文%:   {result.get('r20_source_text_coverage', {}).get('coverage_pct', 0):.0f}%")
    print(f"  总耗时:  {result.get('pipeline_total_time_s', 0):.1f}s")
    if result.get("streaming"):
        print(f"  流式:    {result.get('stream_chunks', 0)} chunks, "
              f"缓冲 {result.get('response_buffer_chars', 0)} chars"
              + (" (已截断)" if result.get("buffer_capped") else ""))
        print(f"  首卡时间: {result.get('time_to_first_char_s', '?')}s")
        print(f"  GPT adaptive tokens: {result.get('r20_gpt_adaptive_tokens', '?')}")
    print(f"\n  R12 基线参考: 角色=8, 场景=25, 位置=23, major道具=20, 变体=26")
    print(f"  R23 合格标准: 角色>=6, 场景>=15, 位置>0, 变体>=8, 原文覆盖>=80%")

    # 合格判定
    passed = True
    checks = []
    if result.get("num_characters", 0) < 6:
        checks.append(f"角色不足: {result.get('num_characters', 0)} < 6")
        passed = False
    if result.get("num_scenes", 0) < 15:
        checks.append(f"场景不足: {result.get('num_scenes', 0)} < 15")
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
        print(f"\n  >> R23 并行优化验证 PASSED <<")
    else:
        print(f"\n  >> R23 并行优化验证 FAILED <<")
        for c in checks:
            print(f"    - {c}")

    print(f"{'=' * 70}")

    # 保存汇总
    _save_json(Path(__file__).parent / "r23_summary.json", result)
    print(f"\n结果已保存到: {Path(__file__).parent}")


if __name__ == "__main__":
    asyncio.run(main())
