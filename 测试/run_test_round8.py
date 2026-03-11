"""第8轮测试 — 四模型VFF V2提示词对比测试.

用法:
  py -3.14 run_test_round8.py

核心变化 vs R7:
  - 4个模型(chatgpt/gemini/claude/grok)各自独立跑完整流程
  - 只测前3章
  - VFF V2: 结构化纯文本格式(画面承接/人物位置/逐镜头/速度感/标签)
  - 两两并行: (chatgpt, gemini) → (claude, grok)
  - 每个模型输出到独立目录
"""

import asyncio
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime

import httpx

# ── 配置 ──────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NOVEL_PATH = os.path.join(SCRIPT_DIR, "我和沈词的长子.txt")
OUTPUT_BASE = os.path.join(SCRIPT_DIR, "第8次测试结果")

MAX_CHAPTERS = 3  # 只测前3章
STEP_COOLDOWN = 2
MIN_CHAPTER_WORDS = 50

sys.stdout.reconfigure(encoding="utf-8")

# prompt 模板
sys.path.insert(0, os.path.join(SCRIPT_DIR, "..", "backend"))
from services.prompt_templates import TEMPLATES

# 本地模块
from model_adapters import call_api_async, MODEL_REGISTRY

# 模型名称映射 (友好名 → MODEL_REGISTRY key)
MODEL_MAP = {
    "chatgpt": "gpt-5.4",
    "gemini":  "gemini",
    "claude":  "claude-opus-4-6",
    "grok":    "grok",
}


# ── 基础工具 ──────────────────────────────────────────────────────

def read_novel() -> str:
    with open(NOVEL_PATH, "rb") as f:
        return f.read().decode("gb18030")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def fmt_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def extract_json(text: str):
    text = text.strip()
    # Strip thinking model tags (<think>...</think>)
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
    # Strip agent thinking tags (Grok multi-agent style)
    text = re.sub(r"\[Agent \d+\]\[AgentThink\][^\n]*\n?", "", text).strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        # 尝试从第一个 [ 或 { 开始解析
        for i, ch in enumerate(text):
            if ch in ("[", "{"):
                try:
                    return json.loads(text[i:], strict=False)
                except json.JSONDecodeError:
                    continue
        # 最后尝试: 移除所有控制字符后再解析
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', text)
        for i, ch in enumerate(cleaned):
            if ch in ("[", "{"):
                try:
                    return json.loads(cleaned[i:], strict=False)
                except json.JSONDecodeError:
                    continue
        raise ValueError(f"无法提取JSON:\n{text[:500]}")


def safe_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\s]+', '_', name)
    return name.strip('_') or 'unnamed'


# ── 成本追踪 ─────────────────────────────────────────────────────

class CostTracker:
    def __init__(self):
        self.stages = {}
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_elapsed = 0.0
        self.total_api_calls = 0

    def add(self, stage: int, cost_meta: dict):
        if stage not in self.stages:
            self.stages[stage] = {
                "input_tokens": 0, "output_tokens": 0,
                "elapsed_s": 0.0, "api_calls": 0,
            }
        s = self.stages[stage]
        s["input_tokens"] += cost_meta.get("input_tokens", 0)
        s["output_tokens"] += cost_meta.get("output_tokens", 0)
        s["elapsed_s"] += cost_meta.get("elapsed_s", 0)
        s["api_calls"] += 1
        self.total_input_tokens += cost_meta.get("input_tokens", 0)
        self.total_output_tokens += cost_meta.get("output_tokens", 0)
        self.total_elapsed += cost_meta.get("elapsed_s", 0)
        self.total_api_calls += 1

    def stage_summary(self, stage: int) -> str:
        s = self.stages.get(stage, {})
        inp = s.get("input_tokens", 0)
        out = s.get("output_tokens", 0)
        elapsed = s.get("elapsed_s", 0)
        calls = s.get("api_calls", 0)
        return f"{calls}次调用, {inp+out}tokens ({inp}in+{out}out), {elapsed:.1f}s"

    def total_summary(self) -> dict:
        return {
            "total_api_calls": self.total_api_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_api_elapsed_s": round(self.total_elapsed, 1),
            "stages": self.stages,
        }


# ── 文件工具 ──────────────────────────────────────────────────────

def ensure_dir(base_dir: str, *parts) -> str:
    path = os.path.join(base_dir, *parts)
    os.makedirs(path, exist_ok=True)
    return path


def save_json(base_dir: str, filename: str, data):
    filepath = os.path.join(base_dir, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_text(base_dir: str, filename: str, content: str):
    filepath = os.path.join(base_dir, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def load_json(filepath: str) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# ══════════════════════════════════════════════════════════════════
#  单模型完整 Pipeline
# ══════════════════════════════════════════════════════════════════

async def run_single_model_pipeline(model_friendly: str, model_key: str,
                                     novel: str) -> dict:
    """单个模型跑完整 Stage 1-7v2 流程。

    Args:
        model_friendly: 友好名 (chatgpt/gemini/claude/grok)
        model_key: MODEL_REGISTRY 中的 key
        novel: 小说全文

    Returns:
        {"model": ..., "cost": ..., "stats": ..., "error": None|str}
    """
    out_dir = os.path.join(OUTPUT_BASE, model_friendly)
    os.makedirs(out_dir, exist_ok=True)
    tracker = CostTracker()

    model_display = MODEL_REGISTRY[model_key].display_name
    print(f"\n{'═' * 60}")
    print(f"  🚀 开始: {model_friendly} ({model_display})")
    print(f"{'═' * 60}")

    try:
        # ── Stage 1: 分章 ─────────────────────────────────────
        print(f"\n  [{model_friendly}] Stage 1: 分章...")
        chapters = await _stage1_chapter_split(
            novel, model_key, tracker, out_dir)
        print(f"    ✓ {len(chapters)} 个有效章节")

        # 截取前3章
        chapters = chapters[:MAX_CHAPTERS]
        print(f"    → 截取前 {len(chapters)} 章")
        await asyncio.sleep(STEP_COOLDOWN)

        # ── Stage 2: 章节摘要 ─────────────────────────────────
        print(f"\n  [{model_friendly}] Stage 2: 章节摘要 + 角色扫描...")
        synopsis, char_scan = await _stage2_summary_and_scan(
            chapters, model_key, tracker, out_dir)
        print(f"    ✓ synopsis {len(synopsis)}字, {len(char_scan)} 角色")
        await asyncio.sleep(STEP_COOLDOWN)

        # ── Stage 3: 角色详情 + 知识库 ────────────────────────
        print(f"\n  [{model_friendly}] Stage 3: 角色详情 + 知识库...")
        char_details, knowledge = await _stage3_character_and_knowledge(
            char_scan, synopsis, model_key, tracker, out_dir)
        print(f"    ✓ {len(char_details)} 角色详情, 知识库已建")
        await asyncio.sleep(STEP_COOLDOWN)

        # ── Stage 4: 场景 + 节拍 ──────────────────────────────
        print(f"\n  [{model_friendly}] Stage 4: 场景 + 节拍...")
        scenes, beats = await _stage4_scene_and_beat(
            chapters, char_scan, synopsis, model_key, tracker, out_dir)
        print(f"    ✓ {len(scenes)} 场景, {len(beats)} 节拍")
        await asyncio.sleep(STEP_COOLDOWN)

        # ── Stage 5: 知识库输出(已在Stage3完成, 这里做绑定) ───
        print(f"\n  [{model_friendly}] Stage 5: 节拍↔场景绑定...")
        bindings = await _stage5_beat_scene_bind(
            beats, scenes, model_key, tracker, out_dir)
        print(f"    ✓ {len(bindings)} 条绑定")
        await asyncio.sleep(STEP_COOLDOWN)

        # ── Stage 6: Scene→Shot 分镜 ──────────────────────────
        print(f"\n  [{model_friendly}] Stage 6: Scene→Shot...")
        all_shots = await _stage6_scene_to_shot(
            scenes, char_details, knowledge, model_key, tracker, out_dir)
        print(f"    ✓ {len(all_shots)} 镜头")
        await asyncio.sleep(STEP_COOLDOWN)

        # ── Stage 7v2: VFF V2 生成 ────────────────────────────
        print(f"\n  [{model_friendly}] Stage 7v2: VFF V2...")
        vff_count = await _stage7v2_vff_generate(
            scenes, all_shots, char_details, knowledge,
            model_key, tracker, out_dir)
        print(f"    ✓ {vff_count} 个VFF脚本")

        # ── 保存成本 ──────────────────────────────────────────
        cost_data = tracker.total_summary()
        save_json(out_dir, "cost.json", cost_data)

        stats = {
            "chapters": len(chapters),
            "characters": len(char_details),
            "scenes": len(scenes),
            "beats": len(beats),
            "shots": len(all_shots),
            "vff_prompts": vff_count,
        }

        print(f"\n  [{model_friendly}] ✅ 完成! "
              f"{cost_data['total_api_calls']}次调用, "
              f"{cost_data['total_tokens']}tokens, "
              f"{cost_data['total_api_elapsed_s']}s")

        return {"model": model_friendly, "cost": cost_data,
                "stats": stats, "error": None}

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        print(f"\n  [{model_friendly}] ❌ 失败: {error_msg}")
        traceback.print_exc()
        save_text(out_dir, "error.txt", f"{error_msg}\n\n{traceback.format_exc()}")
        cost_data = tracker.total_summary()
        save_json(out_dir, "cost.json", cost_data)
        return {"model": model_friendly, "cost": cost_data,
                "stats": {}, "error": error_msg}


# ══════════════════════════════════════════════════════════════════
#  Stage 实现
# ══════════════════════════════════════════════════════════════════

def _build_clean_map(text: str) -> tuple[str, list[int]]:
    """去掉换行符，返回 (clean_text, clean_to_orig_index_map)。"""
    clean_chars = []
    clean_to_orig = []
    for i, c in enumerate(text):
        if c != '\n':
            clean_chars.append(c)
            clean_to_orig.append(i)
    return ''.join(clean_chars), clean_to_orig


def _fuzzy_find(novel: str, marker: str,
                _cache: dict = {}) -> int:
    """先精确匹配；失败则去掉双方换行符再匹配，映射回原文位置。"""
    if not marker:
        return -1
    # 1) 精确匹配
    idx = novel.find(marker)
    if idx >= 0:
        return idx
    # 2) 去换行后匹配
    cache_id = id(novel)
    if cache_id not in _cache:
        _cache[cache_id] = _build_clean_map(novel)
    novel_clean, clean_to_orig = _cache[cache_id]
    marker_clean = marker.replace('\n', '')
    ci = novel_clean.find(marker_clean)
    if ci >= 0:
        return clean_to_orig[ci]
    return -1


def _fuzzy_find_end(novel: str, marker: str,
                    _cache: dict = {}) -> int:
    """找到 end_marker 末尾位置 (即 end_idx + len(marker))，用于切片。"""
    if not marker:
        return -1
    idx = novel.find(marker)
    if idx >= 0:
        return idx + len(marker)
    cache_id = id(novel)
    if cache_id not in _cache:
        _cache[cache_id] = _build_clean_map(novel)
    novel_clean, clean_to_orig = _cache[cache_id]
    marker_clean = marker.replace('\n', '')
    ci = novel_clean.find(marker_clean)
    if ci >= 0:
        end_ci = ci + len(marker_clean) - 1
        if end_ci < len(clean_to_orig):
            return clean_to_orig[end_ci] + 1
    return -1


async def _stage1_chapter_split(novel: str, model_key: str,
                                 tracker: CostTracker, out_dir: str) -> list:
    """Stage 1: 分章。返回 [{id, title, content, order}, ...]"""
    tmpl = TEMPLATES["P01_CHAPTER_SPLIT"]

    # 带重试
    temperatures = [tmpl["temperature"], 0.3, 0.1]
    markers = []
    last_parse_error = None
    for retry in range(3):
        temp = temperatures[min(retry, len(temperatures) - 1)]
        resp, cost = await call_api_async(
            system=tmpl["system"],
            user=tmpl["user"].format(text=novel),
            temperature=temp,
            max_tokens=tmpl["max_tokens"],
            model_name=model_key,
        )
        tracker.add(1, cost)

        # DEBUG: save raw response for inspection
        debug_dir = ensure_dir(out_dir, "_debug")
        save_text(debug_dir, f"stage1_raw_resp_retry{retry}.txt", resp)

        try:
            markers = extract_json(resp)
        except (ValueError, json.JSONDecodeError) as e:
            last_parse_error = e
            print(f"      ⚠ JSON解析失败 (retry {retry}): {e}", flush=True)
            save_text(debug_dir, f"stage1_parse_error_retry{retry}.txt",
                      f"{e}\n\nresp_len={len(resp)}\nresp_preview:\n{resp[:1000]}")
            if retry < 2:
                await asyncio.sleep(STEP_COOLDOWN)
                continue
            raise

        if not isinstance(markers, list):
            print(f"      ⚠ 标记非列表 (retry {retry}): {type(markers)}", flush=True)
            if retry < 2:
                continue
            markers = [markers] if isinstance(markers, dict) else []

        # DEBUG: save parsed markers
        save_json(debug_dir, f"stage1_markers_retry{retry}.json", markers)

        valid_count = 0
        for ch in markers:
            start = ch.get("start_marker", "")
            end = ch.get("end_marker", "")
            si = _fuzzy_find(novel, start)
            ei = _fuzzy_find_end(novel, end)
            if si >= 0 and ei >= 0:
                content_len = ei - si
                if content_len >= MIN_CHAPTER_WORDS:
                    valid_count += 1
            else:
                # DEBUG: show why marker failed
                print(f"      ⚠ 标记未匹配: title={ch.get('title','?')}, "
                      f"start_found={si>=0}, end_found={ei>=0}, "
                      f"start={start[:30]!r}...", flush=True)
        if valid_count >= 3:
            break

    chapters = []
    ch_dir = ensure_dir(out_dir, "chapters")
    for i, ch in enumerate(markers):
        ch_id = f"ch_{i:03d}"
        title = ch.get("title", f"第{i+1}章")
        start = ch.get("start_marker", "")
        end = ch.get("end_marker", "")

        si = _fuzzy_find(novel, start)
        ei = _fuzzy_find_end(novel, end)
        if si >= 0 and ei >= 0:
            content = novel[si:ei]
        else:
            continue

        if len(content) < MIN_CHAPTER_WORDS:
            continue

        ch_data = {"id": ch_id, "title": title, "content": content,
                   "order": i, "word_count": len(content)}
        chapters.append(ch_data)

        save_json(ch_dir, f"{ch_id}_{safe_filename(title)}.json", ch_data)

    return chapters


async def _stage2_summary_and_scan(chapters: list, model_key: str,
                                    tracker: CostTracker,
                                    out_dir: str) -> tuple[str, list]:
    """Stage 2: 摘要 + 角色扫描。返回 (synopsis, char_scan_list)。"""
    tmpl_summary = TEMPLATES["P01B_CHAPTER_SUMMARY"]
    tmpl_scan = TEMPLATES["P03A_CHARACTER_SCAN"]

    async def summarize_one(ch):
        resp, cost = await call_api_async(
            system=tmpl_summary["system"],
            user=tmpl_summary["user"].format(
                chapter_title=ch["title"], text=ch["content"]),
            temperature=tmpl_summary["temperature"],
            max_tokens=tmpl_summary["max_tokens"],
            model_name=model_key,
        )
        tracker.add(2, cost)
        return {"ch_id": ch["id"], "title": ch["title"],
                "summary": resp.strip()}

    summaries = await asyncio.gather(
        *[summarize_one(ch) for ch in chapters])

    synopsis = "\n\n".join(
        f"【{s['title']}】\n{s['summary']}" for s in summaries)

    # 保存
    kn_dir = ensure_dir(out_dir, "knowledge")
    save_text(kn_dir, "synopsis.txt", synopsis)
    for s in summaries:
        ch_dir = ensure_dir(out_dir, "chapters")
        save_json(ch_dir, f"{s['ch_id']}_summary.json", s)

    # 角色扫描
    resp, cost = await call_api_async(
        system=tmpl_scan["system"],
        user=tmpl_scan["user"].format(synopsis=synopsis),
        temperature=tmpl_scan["temperature"],
        max_tokens=tmpl_scan["max_tokens"],
        model_name=model_key,
    )
    tracker.add(2, cost)
    char_list = extract_json(resp)

    char_dir = ensure_dir(out_dir, "characters")
    save_json(char_dir, "_scan.json", char_list)

    return synopsis, char_list


async def _stage3_character_and_knowledge(char_scan: list, synopsis: str,
                                           model_key: str,
                                           tracker: CostTracker,
                                           out_dir: str) -> tuple[list, dict]:
    """Stage 3: 角色详情 + 知识库。返回 (char_details, knowledge)。"""
    tmpl_detail = TEMPLATES["P03B_CHARACTER_DETAIL"]
    tmpl_kb = TEMPLATES["P05_KNOWLEDGE_BASE_V2"]

    main_chars = [c for c in char_scan
                  if c.get("role") in ("protagonist", "antagonist", "supporting")]
    all_names = [c.get("name", "?") for c in char_scan]

    async def detail_one(ch, idx):
        name = ch.get("name", "?")
        brief = ch.get("brief", ch.get("description", ""))
        other_names = [n for n in all_names if n != name]
        resp, cost = await call_api_async(
            system=tmpl_detail["system"],
            user=tmpl_detail["user"].format(
                character_name=name, character_brief=brief,
                other_characters=", ".join(other_names[:10]),
                synopsis=synopsis,
            ),
            temperature=tmpl_detail["temperature"],
            max_tokens=tmpl_detail["max_tokens"],
            model_name=model_key,
        )
        tracker.add(3, cost)
        detail = extract_json(resp)
        detail["name"] = name
        detail["role"] = ch.get("role", "supporting")
        return detail

    async def build_knowledge():
        char_names = ", ".join(all_names[:10])
        resp, cost = await call_api_async(
            system=tmpl_kb["system"],
            user=tmpl_kb["user"].format(
                synopsis=synopsis, character_names=char_names,
                location_names="未知",
            ),
            temperature=tmpl_kb["temperature"],
            max_tokens=tmpl_kb["max_tokens"],
            model_name=model_key,
        )
        tracker.add(3, cost)
        return extract_json(resp)

    tasks = [detail_one(ch, i) for i, ch in enumerate(main_chars)]
    tasks.append(build_knowledge())
    results = await asyncio.gather(*tasks, return_exceptions=True)

    char_details = []
    knowledge = {}
    char_dir = ensure_dir(out_dir, "characters")
    kn_dir = ensure_dir(out_dir, "knowledge")

    for r in results:
        if isinstance(r, Exception):
            print(f"      ⚠ Stage3 子任务失败: {r}")
            continue
        if isinstance(r, dict) and "name" in r:
            char_details.append(r)
            save_json(char_dir, f"{safe_filename(r['name'])}.json", r)
        elif isinstance(r, dict):
            knowledge = r
            wb = r.get("world_building", {})
            sg = r.get("style_guide", {})
            save_json(kn_dir, "world_building.json", wb)
            save_json(kn_dir, "style_guide.json", sg)

    return char_details, knowledge


async def _stage4_scene_and_beat(chapters: list, char_scan: list,
                                  synopsis: str, model_key: str,
                                  tracker: CostTracker,
                                  out_dir: str) -> tuple[list, list]:
    """Stage 4: 场景提取 + 节拍。返回 (scenes, beats)。"""
    tmpl_scene = TEMPLATES["P04_SCENE_EXTRACT"]
    tmpl_beat = TEMPLATES["P10_NOVEL_TO_BEAT"]

    char_names = ", ".join(c.get("name", "?") for c in char_scan[:10])

    async def extract_scenes_for_chapter(ch, ch_idx):
        batch_text = f"【{ch['title']}】\n{ch['content']}"
        try:
            resp, cost = await call_api_async(
                system=tmpl_scene["system"],
                user=tmpl_scene["user"].format(
                    text=batch_text, character_names=char_names),
                temperature=tmpl_scene["temperature"],
                max_tokens=8192,
                model_name=model_key,
            )
            tracker.add(4, cost)
            scenes = extract_json(resp)
            if not isinstance(scenes, list):
                scenes = [scenes]
        except Exception as e:
            print(f"      ⚠ 场景提取跳过 {ch['title']}: {e}")
            return []

        results = []
        for local_idx, s in enumerate(scenes):
            scene_data = {
                "id": "",  # 后续按章节顺序统一编号
                "heading": s.get("heading", ""),
                "location": s.get("location", ""),
                "time_of_day": s.get("time_of_day", ""),
                "description": s.get("description", ""),
                "action": s.get("action", ""),
                "dialogue": s.get("dialogue", []),
                "characters_present": s.get("characters_present", []),
                "key_props": s.get("key_props", []),
                "dramatic_purpose": s.get("dramatic_purpose", ""),
                "tension_score": s.get("tension_score", 0.5),
                "source_chapter": ch["id"],
                "order": 0,  # 后续统一赋值
                "_ch_idx": ch_idx,
                "_local_idx": local_idx,
            }
            results.append(scene_data)
        return results

    async def extract_beats():
        try:
            resp, cost = await call_api_async(
                system=tmpl_beat["system"],
                user=tmpl_beat["user"].format(text=synopsis),
                temperature=tmpl_beat["temperature"],
                max_tokens=tmpl_beat["max_tokens"],
                model_name=model_key,
            )
            tracker.add(4, cost)
            beats = extract_json(resp)
            if not isinstance(beats, list):
                beats = [beats]
            return beats
        except Exception as e:
            print(f"      ⚠ 节拍提取失败: {e}")
            return []

    scene_tasks = [extract_scenes_for_chapter(ch, i)
                   for i, ch in enumerate(chapters)]
    all_tasks = scene_tasks + [extract_beats()]
    results = await asyncio.gather(*all_tasks, return_exceptions=True)

    all_scenes = []
    beats = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            print(f"      ⚠ Stage4 子任务失败: {r}")
        elif isinstance(r, list) and r:
            if i < len(chapters):
                # 场景结果
                all_scenes.extend(r)
            else:
                # 节拍结果
                if isinstance(r[0], dict) and "beat_type" in r[0]:
                    beats = r

    # 按章节顺序 → 章内顺序排序，然后统一编号
    all_scenes.sort(key=lambda s: (s.get("_ch_idx", 999),
                                    s.get("_local_idx", 0)))
    for idx, scene in enumerate(all_scenes):
        scene["id"] = f"scene_{idx:03d}"
        scene["order"] = idx
        scene.pop("_ch_idx", None)
        scene.pop("_local_idx", None)

    # 保存
    scene_dir = ensure_dir(out_dir, "scenes")
    for s in all_scenes:
        save_json(scene_dir, f"{s['id']}.json", s)
    save_json(scene_dir, "_index.json", {
        "count": len(all_scenes),
        "entries": [{"id": s["id"], "heading": s["heading"]}
                    for s in all_scenes],
    })

    beat_dir = ensure_dir(out_dir, "beats")
    for i, b in enumerate(beats):
        b["id"] = f"beat_{i:03d}"
        b["order"] = i
        save_json(beat_dir, f"beat_{i:03d}.json", b)
    save_json(beat_dir, "_index.json", {
        "count": len(beats),
        "entries": [{"id": b.get("id", f"beat_{i:03d}"),
                     "title": b.get("title", "")}
                    for i, b in enumerate(beats)],
    })

    return all_scenes, beats


async def _stage5_beat_scene_bind(beats: list, scenes: list,
                                   model_key: str, tracker: CostTracker,
                                   out_dir: str) -> list:
    """Stage 5: 节拍↔场景绑定。返回 binding list。"""
    tmpl = TEMPLATES["P08_BEAT_SCENE_BIND"]

    beats_summary = [
        {"id": b.get("id", f"beat_{i:03d}"),
         "title": b.get("title", ""),
         "description": b.get("description", "")[:200],
         "beat_type": b.get("beat_type", "")}
        for i, b in enumerate(beats)
    ]
    scenes_summary = [
        {"id": s["id"], "heading": s["heading"],
         "dramatic_purpose": s.get("dramatic_purpose", ""),
         "description": s.get("description", "")[:200]}
        for s in scenes
    ]

    try:
        resp, cost = await call_api_async(
            system=tmpl["system"],
            user=tmpl["user"].format(
                beats_summary=fmt_json(beats_summary),
                scenes_summary=fmt_json(scenes_summary),
            ),
            temperature=tmpl["temperature"],
            max_tokens=tmpl["max_tokens"],
            model_name=model_key,
        )
        tracker.add(5, cost)
        bindings_data = extract_json(resp)
        binding_list = bindings_data.get("bindings", [])
    except Exception as e:
        print(f"      ⚠ 绑定失败: {e}")
        binding_list = []

    save_json(out_dir, "beat_scene_bindings.json",
              {"bindings": binding_list})
    return binding_list


async def _stage6_scene_to_shot(scenes: list, char_details: list,
                                 knowledge: dict, model_key: str,
                                 tracker: CostTracker,
                                 out_dir: str) -> list:
    """Stage 6: Scene→Shot拆分。返回所有 shots。"""
    tmpl = TEMPLATES["P06_SCENE_TO_SHOT"]

    style_guide = fmt_json(knowledge.get("style_guide", {}))
    char_profiles = {}
    for cd in char_details:
        name = cd.get("name", "")
        char_profiles[name] = {
            "name": name,
            "appearance": cd.get("appearance", {}),
            "costume": cd.get("costume", {}),
            "visual_reference": cd.get("visual_reference", ""),
        }

    shot_order_counter = [0]

    async def process_scene(scene, idx):
        present_chars = scene.get("characters_present", [])
        profiles = {n: char_profiles[n]
                    for n in present_chars if n in char_profiles}

        try:
            resp, cost = await call_api_async(
                system=tmpl["system"],
                user=tmpl["user"].format(
                    scene_json=fmt_json(scene),
                    style_guide=style_guide,
                    character_profiles=fmt_json(profiles),
                ),
                temperature=tmpl["temperature"],
                max_tokens=tmpl["max_tokens"],
                model_name=model_key,
            )
            tracker.add(6, cost)
            shots = extract_json(resp)
            if not isinstance(shots, list):
                shots = [shots]
        except Exception as e:
            print(f"      ⚠ Shot跳过 {scene['id']}: {e}")
            return []

        results = []
        for s in shots:
            shot_data = {
                "id": f"shot_{shot_order_counter[0]:04d}",
                "scene_id": scene["id"],
                "shot_number": s.get("shot_number", 0),
                "goal": s.get("goal", ""),
                "composition": s.get("composition", ""),
                "camera_movement": s.get("camera_movement", "static"),
                "framing": s.get("framing", "MS"),
                "emotion_target": s.get("emotion_target", ""),
                "duration_hint": s.get("duration_hint", ""),
                "characters": s.get("characters", []),
                "transition_in": s.get("transition_in", "cut"),
                "transition_out": s.get("transition_out", "cut"),
                "dramatic_intensity": s.get("dramatic_intensity", 0),
                "order": shot_order_counter[0],
            }
            shot_order_counter[0] += 1
            results.append(shot_data)
        return results

    tasks = [process_scene(scene, i) for i, scene in enumerate(scenes)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_shots = []
    for r in results:
        if isinstance(r, Exception):
            print(f"      ⚠ Shot子任务失败: {r}")
        elif isinstance(r, list):
            all_shots.extend(r)

    # 按scene顺序重编号
    def scene_order_key(shot):
        m = re.search(r'scene_(\d+)', shot.get("scene_id", ""))
        return int(m.group(1)) if m else 9999

    all_shots.sort(key=lambda s: (scene_order_key(s), s.get("shot_number", 0)))
    for idx, shot in enumerate(all_shots):
        shot["id"] = f"shot_{idx:04d}"
        shot["order"] = idx

    # 按scene分组保存
    from collections import defaultdict
    shots_by_scene = defaultdict(list)
    for s in all_shots:
        shots_by_scene[s["scene_id"]].append(s)

    shot_dir = ensure_dir(out_dir, "shots")
    for scene_id, scene_shots in shots_by_scene.items():
        save_json(shot_dir, f"{scene_id}_shots.json", scene_shots)

    save_json(shot_dir, "_index.json", {
        "count": len(all_shots),
        "entries": [{"id": s["id"], "scene_id": s["scene_id"],
                     "framing": s["framing"]}
                    for s in all_shots],
    })

    return all_shots


async def _stage7v2_vff_generate(scenes: list, all_shots: list,
                                  char_details: list, knowledge: dict,
                                  model_key: str, tracker: CostTracker,
                                  out_dir: str) -> int:
    """Stage 7v2: VFF V2 生成（纯文本格式）。返回 VFF 数量。"""
    tmpl = TEMPLATES["P11_VFF_GENERATE_V2"]

    style_guide = fmt_json(knowledge.get("style_guide", {}))

    # 构建角色profiles (含@char_引用ID)
    char_profiles = {}
    for cd in char_details:
        name = cd.get("name", "")
        char_id = f"char_{safe_filename(name)}"
        char_profiles[name] = {
            "id": char_id,
            "name": name,
            "appearance": cd.get("appearance", {}),
            "costume": cd.get("costume", {}),
            "visual_reference": cd.get("visual_reference", ""),
            "personality": cd.get("personality", ""),
        }

    # 按scene分组shots
    from collections import defaultdict
    shots_by_scene = defaultdict(list)
    for s in all_shots:
        shots_by_scene[s["scene_id"]].append(s)

    vff_dir = ensure_dir(out_dir, "vff_prompts")
    vff_count = 0

    async def process_scene_vff(scene, idx):
        scene_id = scene["id"]
        scene_shots = shots_by_scene.get(scene_id, [])
        if not scene_shots:
            return 0

        present_chars = scene.get("characters_present", [])
        profiles = {n: char_profiles[n]
                    for n in present_chars if n in char_profiles}

        try:
            resp, cost = await call_api_async(
                system=tmpl["system"],
                user=tmpl["user"].format(
                    scene_json=fmt_json(scene),
                    shots_json=fmt_json(scene_shots),
                    character_profiles=fmt_json(profiles),
                    style_guide=style_guide,
                    scene_id=scene_id,
                ),
                temperature=tmpl["temperature"],
                max_tokens=tmpl["max_tokens"],
                model_name=model_key,
            )
            tracker.add(7, cost)
        except Exception as e:
            print(f"      ⚠ VFF跳过 {scene_id}: {e}")
            return 0

        # VFF V2 是纯文本，清理 thinking 标签后保存
        vff_text = re.sub(r"<think>[\s\S]*?</think>\s*", "", resp).strip()
        save_text(vff_dir, f"{scene_id}_vff.txt", vff_text)

        # 同时保存一份带元数据的JSON
        save_json(vff_dir, f"{scene_id}_vff_meta.json", {
            "scene_id": scene_id,
            "heading": scene.get("heading", ""),
            "model": model_key,
            "vff_text_length": len(vff_text),
            "shot_count": len(scene_shots),
            "cost": cost,
        })
        return 1

    tasks = [process_scene_vff(scene, i) for i, scene in enumerate(scenes)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, int):
            vff_count += r
        elif isinstance(r, Exception):
            print(f"      ⚠ VFF子任务失败: {r}")

    return vff_count


# ══════════════════════════════════════════════════════════════════
#  主入口: 两两并行执行
# ══════════════════════════════════════════════════════════════════

async def main():
    print("═" * 70)
    print("  第8轮测试 — 四模型 VFF V2 提示词对比")
    print("  模型: ChatGPT(gpt-5.4) / Gemini(3.1-pro) / "
          "Claude(opus-4-6) / Grok(4.20-beta)")
    print("  范围: 前3章, 完整Pipeline Stage 1→7v2")
    print("═" * 70)

    os.makedirs(OUTPUT_BASE, exist_ok=True)
    novel = read_novel()
    print(f"\n  小说长度: {len(novel)} 字")

    t0 = time.time()

    # ── 第1波: chatgpt + gemini 并行 ──────────────────────────
    print("\n" + "─" * 70)
    print("  第1波并行: ChatGPT + Gemini")
    print("─" * 70)

    wave1 = await asyncio.gather(
        run_single_model_pipeline("chatgpt", MODEL_MAP["chatgpt"], novel),
        run_single_model_pipeline("gemini", MODEL_MAP["gemini"], novel),
        return_exceptions=True,
    )

    wave1_results = []
    for r in wave1:
        if isinstance(r, Exception):
            print(f"\n  ⚠ 第1波模型异常: {r}")
            wave1_results.append({"model": "unknown", "error": str(r)})
        else:
            wave1_results.append(r)

    wave1_time = time.time() - t0
    print(f"\n  第1波完成, 耗时 {wave1_time:.0f}s")

    # ── 第2波: claude + grok 并行 ─────────────────────────────
    t1 = time.time()
    print("\n" + "─" * 70)
    print("  第2波并行: Claude + Grok")
    print("─" * 70)

    wave2 = await asyncio.gather(
        run_single_model_pipeline("claude", MODEL_MAP["claude"], novel),
        run_single_model_pipeline("grok", MODEL_MAP["grok"], novel),
        return_exceptions=True,
    )

    wave2_results = []
    for r in wave2:
        if isinstance(r, Exception):
            print(f"\n  ⚠ 第2波模型异常: {r}")
            wave2_results.append({"model": "unknown", "error": str(r)})
        else:
            wave2_results.append(r)

    wave2_time = time.time() - t1
    total_time = time.time() - t0

    print(f"\n  第2波完成, 耗时 {wave2_time:.0f}s")

    # ── 总结报告 ──────────────────────────────────────────────
    all_results = wave1_results + wave2_results

    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("  第8轮测试总结 — 四模型VFF V2对比")
    report_lines.append("=" * 70)
    report_lines.append(f"  小说: 《我和沈词的长子》 ({len(novel)} 字)")
    report_lines.append(f"  范围: 前{MAX_CHAPTERS}章")
    report_lines.append(f"  总耗时: {total_time:.0f}s "
                        f"(第1波 {wave1_time:.0f}s + 第2波 {wave2_time:.0f}s)")
    report_lines.append("")

    for r in all_results:
        model = r.get("model", "?")
        error = r.get("error")
        report_lines.append(f"  ── {model} ──")
        if error:
            report_lines.append(f"    ❌ 失败: {error}")
        else:
            stats = r.get("stats", {})
            cost = r.get("cost", {})
            report_lines.append(
                f"    章节: {stats.get('chapters', 0)}, "
                f"角色: {stats.get('characters', 0)}, "
                f"场景: {stats.get('scenes', 0)}, "
                f"镜头: {stats.get('shots', 0)}")
            report_lines.append(
                f"    VFF: {stats.get('vff_prompts', 0)} 个")
            report_lines.append(
                f"    API调用: {cost.get('total_api_calls', 0)}次, "
                f"Token: {cost.get('total_tokens', 0)}, "
                f"耗时: {cost.get('total_api_elapsed_s', 0)}s")
        report_lines.append("")

    report_lines.append("=" * 70)

    report_text = "\n".join(report_lines)
    print(f"\n{report_text}")

    save_text(OUTPUT_BASE, "00_测试总结.txt", report_text)
    save_json(OUTPUT_BASE, "00_all_results.json", all_results)

    print(f"\n  输出目录: {OUTPUT_BASE}")
    print(f"  总结文件: 00_测试总结.txt")


async def main_single(model_friendly: str):
    """只跑单个模型（用于补跑失败的模型）。"""
    model_key = MODEL_MAP.get(model_friendly)
    if not model_key:
        print(f"  未知模型: {model_friendly}, 可选: {list(MODEL_MAP.keys())}")
        return

    print("═" * 70)
    print(f"  第8轮测试 — 单模型补跑: {model_friendly}")
    print("═" * 70)

    os.makedirs(OUTPUT_BASE, exist_ok=True)
    novel = read_novel()
    print(f"\n  小说长度: {len(novel)} 字")

    t0 = time.time()
    result = await run_single_model_pipeline(model_friendly, model_key, novel)
    total_time = time.time() - t0

    print(f"\n  {model_friendly} 补跑完成, 耗时 {total_time:.0f}s")

    # 更新总结
    all_results_path = os.path.join(OUTPUT_BASE, "00_all_results.json")
    if os.path.exists(all_results_path):
        all_results = load_json(all_results_path)
        # 替换或追加
        updated = False
        for i, r in enumerate(all_results):
            if r.get("model") == model_friendly:
                all_results[i] = result
                updated = True
                break
        if not updated:
            all_results.append(result)
        save_json(OUTPUT_BASE, "00_all_results.json", all_results)
    else:
        save_json(OUTPUT_BASE, "00_all_results.json", [result])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--only":
        model_name = sys.argv[2] if len(sys.argv) > 2 else ""
        asyncio.run(main_single(model_name))
    else:
        asyncio.run(main())
