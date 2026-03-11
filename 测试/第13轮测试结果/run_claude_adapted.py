"""Claude 专属适配管道 — R13.

问题: Claude (Opus via comfly代理) 流式输出在~1120 chunks后截断,
导致场景只提取到11个(基线21-25)。

适配策略:
1. Stage 1 分两段提取: 前半段 + 后半段，各自独立提取角色+场景
2. 角色去重合并（按name）
3. 场景去重合并（按location+core_event指纹）
4. 后续 Stage 2/3 用合并后的完整数据

非流式模式，避免 comfly 代理的流式截断问题。
"""

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
os.environ["PYTHONIOENCODING"] = "utf-8"

import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from services.streaming_parser import extract_json_robust, estimate_max_tokens
from services.asset_enrichment import group_scenes_by_location, collect_and_tier_props
from services.prompt_templates import render_prompt

# ── Claude 配置 (强制非流式) ──
_COMFLY_KEY = "sk-4f5dNlvbRjwcwjsxGeWU2NqY8Yp4u9SaYZUeuAhQVrofzD6R"
MAJOR_PROP_THRESHOLD = 3
MAX_RETRIES = 3
RETRY_WAIT_BASE = 10
RATE_LIMIT_WAIT = 30

MODEL_CFG = {
    "model_id": "claude-opus-4-6",
    "display_name": "Claude (claude-opus-4-6) [Adapted]",
    "api_base": "https://ai.comfly.chat/v1",
    "api_key": _COMFLY_KEY,
    "timeout": 600,
}


def is_retryable(exc):
    if isinstance(exc, (httpx.ReadTimeout, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (500, 502, 524, 503, 504)
    return False


async def call_api(system: str, user: str,
                   temperature: float = 0.5, max_tokens: int = 16000) -> tuple[str, dict]:
    """非流式 API 调用 — 强制非流式，规避 comfly 代理流式截断。"""
    headers = {"Authorization": f"Bearer {MODEL_CFG['api_key']}", "Content-Type": "application/json"}
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    body = {
        "model": MODEL_CFG["model_id"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    url = f"{MODEL_CFG['api_base']}/chat/completions"

    last_exc = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            t0 = time.time()
            async with httpx.AsyncClient(timeout=MODEL_CFG["timeout"],
                                         follow_redirects=True) as client:
                resp = await client.post(url, json=body, headers=headers)
                resp.raise_for_status()
            elapsed = time.time() - t0

            resp_body = resp.text
            if not resp_body.strip():
                raise RuntimeError("Empty response")

            # SSE 代理情况
            if resp_body.lstrip().startswith("data: "):
                chunks = []
                for line in resp_body.split("\n"):
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
                    except json.JSONDecodeError:
                        continue
                text = "".join(chunks)
                if not text.strip():
                    raise RuntimeError("SSE parsed to empty")
                return text, {"elapsed_s": round(elapsed, 2)}

            data = resp.json()
            if data.get("error"):
                err_msg = data["error"] if isinstance(data["error"], str) else data["error"].get("message", str(data["error"]))
                raise RuntimeError(f"API error: {err_msg}")

            choices = data.get("choices", [])
            text = choices[0]["message"]["content"] if choices else ""
            if not text.strip():
                raise RuntimeError("Empty content")
            usage = data.get("usage", {})
            return text, {"elapsed_s": round(elapsed, 2),
                         "input_tokens": usage.get("prompt_tokens", 0),
                         "output_tokens": usage.get("completion_tokens", 0)}

        except Exception as e:
            last_exc = e
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429:
                print(f"    [!!] 429限流, 等待{RATE_LIMIT_WAIT}s...", flush=True)
                await asyncio.sleep(RATE_LIMIT_WAIT)
                continue
            if is_retryable(e) or isinstance(e, RuntimeError):
                if attempt < MAX_RETRIES:
                    wait = RETRY_WAIT_BASE * (attempt + 1)
                    print(f"    [!!] 重试 {attempt+1}/{MAX_RETRIES}, 等待{wait}s: {e}", flush=True)
                    await asyncio.sleep(wait)
                    continue
            raise
    raise last_exc


# ─── Stage 1: 分段提取 ───

_R13_SUPPLEMENT = (
    "\n\n【重要补充要求 — R13】\n"
    "1. 确保提取尽可能多的叙事场景，仔细检查是否遗漏了时空跳转点\n"
    "2. key_props 只列出推动剧情或揭示角色的核心道具（每场景2-5个），"
    "不要列出纯环境装饰物\n"
    "3. visual_reference 和 visual_prompt_negative 必须使用中文\n"
    "4. 每个场景必须包含 source_text_start 和 source_text_end 字段：\n"
    "   - source_text_start: 该场景对应原文段落的前20个字（精确复制原文）\n"
    "   - source_text_end: 该场景对应原文段落的最后20个字（精确复制原文）\n"
)


async def extract_segment(novel_segment: str, segment_label: str,
                          out_dir: Path) -> tuple[list, list]:
    """对一段小说文本执行非流式提取。"""
    rendered = render_prompt("P_COMBINED_EXTRACT", text=novel_segment)
    rendered["user"] += _R13_SUPPLEMENT
    max_tokens = max(rendered["max_tokens"], 16000)

    print(f"    -> [{segment_label}] 非流式提取 (len={len(novel_segment)}, max_tokens={max_tokens})...",
          end="", flush=True)
    raw, cost = await call_api(
        rendered["system"], rendered["user"],
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


def _safe(name: str) -> str:
    return re.sub(r'[^\w\u4e00-\u9fff-]', '_', name)[:30]


def _save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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


def _retier_props(raw_prop_data: dict, threshold: int) -> dict:
    all_props = {}
    for name, info in raw_prop_data.get("major", {}).items():
        all_props[name] = info
    for name, info in raw_prop_data.get("minor", {}).items():
        all_props[name] = info
    major = {p: info for p, info in all_props.items() if info.get("count", 0) >= threshold}
    minor = {p: info for p, info in all_props.items() if info.get("count", 0) < threshold}
    return {
        "major": major, "minor": minor,
        "total_unique": len(all_props),
        "major_count": len(major), "minor_count": len(minor),
    }


# ─── Stage 2: 位置卡 + 道具 ───

async def stage2_enrichment(characters: list, scenes: list,
                            novel_text: str, out_dir: Path) -> tuple[list, dict]:
    print(f"\n    阶段2: 后处理...")

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
        raw, cost = await call_api(
            rendered["system"], rendered["user"],
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
            location_cards = cards
            loc_dir = out_dir / "locations"
            loc_dir.mkdir(exist_ok=True)
            for i, c in enumerate(cards):
                c.setdefault("location_id", f"loc_{i + 1:03d}")
                _save_json(loc_dir / f"{c['location_id']}_{_safe(c.get('name', ''))}.json", c)
            print(f"      [OK] 位置卡: {len(cards)} 张")
        except Exception as e:
            print(f"      [!!] 位置卡解析失败: {e}")

    raw_prop_data = collect_and_tier_props(scenes)
    prop_data = _retier_props(raw_prop_data, MAJOR_PROP_THRESHOLD)
    print(f"      道具 (阈值≥{MAJOR_PROP_THRESHOLD}): {prop_data['total_unique']} 种 "
          f"(major: {prop_data['major_count']}, minor: {prop_data['minor_count']})")

    props_dir = out_dir / "props"
    props_dir.mkdir(exist_ok=True)
    _save_json(props_dir / "prop_index.json", prop_data)

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
        raw, cost = await call_api(
            rendered["system"], rendered["user"],
            temperature=rendered["temperature"], max_tokens=rendered["max_tokens"],
        )
        print(f" {cost.get('elapsed_s', '?')}s")
        try:
            prop_cards = extract_json_robust(raw)
            if not isinstance(prop_cards, list):
                prop_cards = [prop_cards]
            for c in prop_cards:
                _save_json(props_dir / f"prop_major_{_safe(c.get('name', ''))}.json", c)
            print(f"      [OK] 道具卡: {len(prop_cards)} 张")
        except Exception as e:
            print(f"      [!!] 道具卡解析失败: {e}")

    print(f"      [R13] 跳过 Stage 2D: minor 道具视觉生成")
    return location_cards, prop_data


# ─── Stage 3: 角色变体 ───

async def stage3_variants(characters: list, scenes: list, out_dir: Path) -> list:
    print(f"\n    阶段3: 角色变体生成...")
    eligible = []
    for char in characters:
        role = char.get("role", "")
        name = char.get("name", "")
        sc = sum(1 for s in scenes if name in s.get("characters_present", []))
        if role in ("protagonist", "antagonist"):
            eligible.append((char, sc))
        elif role == "supporting" and sc >= 3:  # 适配：降低阈值因为场景总数可能偏少
            eligible.append((char, sc))

    if not eligible:
        print(f"      无符合条件的角色")
        return []

    print(f"      符合条件: {len(eligible)} 个角色")
    variants_dir = out_dir / "variants"
    variants_dir.mkdir(exist_ok=True)

    all_variants = []
    for char, sc in eligible:
        name = char.get("name", "unnamed")
        char_scenes = [s for s in scenes if name in s.get("characters_present", [])]
        rendered = render_prompt(
            "P_CHARACTER_VARIANT",
            character_card_json=json.dumps(char, ensure_ascii=False, indent=2),
            character_scenes_json=json.dumps(char_scenes, ensure_ascii=False, indent=2),
        )
        try:
            raw, cost = await call_api(
                rendered["system"], rendered["user"],
                temperature=rendered["temperature"], max_tokens=rendered["max_tokens"],
            )
            variants = extract_json_robust(raw)
            if not isinstance(variants, list):
                variants = [variants]
            for v in variants:
                v_type = v.get("variant_type", "unknown")
                _save_json(variants_dir / f"variant_{_safe(name)}_{_safe(v_type)}.json", v)
            print(f"      -> {name}: {len(variants)} 个变体")
            all_variants.extend(variants)
        except Exception as e:
            print(f"      [!!] {name} 变体失败: {e}")

    print(f"      [OK] 变体总计: {len(all_variants)} 个")
    return all_variants


# ─── Main ───

async def main():
    novel_path = Path(__file__).parent / "我和沈词的长子.txt"
    if not novel_path.exists():
        novel_path = Path(__file__).parent.parent / "我和沈词的长子.txt"
    if not novel_path.exists():
        print("找不到测试小说"); sys.exit(1)

    novel_text = novel_path.read_text(encoding="gb18030")
    print(f"小说加载完成: {len(novel_text)} 字符")
    print(f"Claude 适配管道: 分两段提取 + 强制非流式 + 合并去重")

    out_dir = Path(__file__).parent / "backend_mode_c_results" / "claude"
    out_dir.mkdir(parents=True, exist_ok=True)

    t0_total = time.time()

    # ── Stage 1: 分两段提取 ──
    mid = len(novel_text) // 2
    # 找到mid附近的换行符作为分割点，避免截断句子
    split_pos = novel_text.rfind('\n', mid - 500, mid + 500)
    if split_pos == -1:
        split_pos = mid

    part_a = novel_text[:split_pos]
    part_b = novel_text[split_pos:]
    print(f"  分段: A={len(part_a)} 字符, B={len(part_b)} 字符, 分割点={split_pos}")

    chars_a, scenes_a = await extract_segment(part_a, "前半段", out_dir)
    chars_b, scenes_b = await extract_segment(part_b, "后半段", out_dir)

    # 合并
    characters = merge_characters(chars_a, chars_b)
    scenes = merge_scenes(scenes_a, scenes_b)
    print(f"\n  合并结果: {len(characters)} 角色, {len(scenes)} 场景")

    # 保存
    chars_dir = out_dir / "characters"
    scenes_dir = out_dir / "narrative_scenes"
    chars_dir.mkdir(exist_ok=True)
    scenes_dir.mkdir(exist_ok=True)
    # 清理旧文件
    for f in chars_dir.glob("*.json"):
        f.unlink()
    for f in scenes_dir.glob("*.json"):
        f.unlink()
    for i, c in enumerate(characters):
        _save_json(chars_dir / f"char_{i:02d}_{_safe(c.get('name', ''))}.json", c)
    for s in scenes:
        _save_json(scenes_dir / f"{s['scene_id']}_{_safe(s.get('location', ''))}.json", s)

    st_coverage = _source_text_coverage(scenes)
    print(f"  原文定位: 覆盖率 {st_coverage['coverage_pct']:.0f}%")

    # ── Stage 2 ──
    location_cards, prop_data = await stage2_enrichment(characters, scenes, novel_text, out_dir)

    # ── Stage 3 ──
    all_variants = await stage3_variants(characters, scenes, out_dir)

    total_time = time.time() - t0_total
    print(f"\n  [OK] Claude 适配管道完成: {total_time:.1f}s")
    print(f"    角色: {len(characters)}, 场景: {len(scenes)}, "
          f"位置: {len(location_cards)}, 变体: {len(all_variants)}")

    result = {
        "model": MODEL_CFG["display_name"],
        "status": "OK",
        "adapted_pipeline": "split_2_segments_non_streaming",
        "num_characters": len(characters),
        "num_scenes": len(scenes),
        "character_names": [c.get("name", "?") for c in characters],
        "num_locations": len(location_cards),
        "num_props_total": prop_data.get("total_unique", 0),
        "num_props_major": prop_data.get("major_count", 0),
        "num_props_minor": prop_data.get("minor_count", 0),
        "minor_props_with_visual": 0,
        "num_variants": len(all_variants),
        "pipeline_total_time_s": round(total_time, 2),
        "r13_major_prop_threshold": MAJOR_PROP_THRESHOLD,
        "r13_source_text_coverage": st_coverage,
        "segment_a_chars": len(chars_a),
        "segment_a_scenes": len(scenes_a),
        "segment_b_chars": len(chars_b),
        "segment_b_scenes": len(scenes_b),
    }
    _save_json(out_dir / "manifest.json", result)
    print(f"  manifest.json 已更新")


if __name__ == "__main__":
    asyncio.run(main())
