"""第7轮测试 — Phase A/B/C 三阶段Pipeline + VFF视觉融合流.

用法:
  python run_test_round7.py            # 终端模式，自动从断点续跑
  python run_test_round7.py --mode web # Web 确认模式
  python run_test_round7.py --clean    # 清空重跑

核心变化 vs R6:
  - Phase A (Stage 1-7): 必须阶段，自动连续运行，含VFF生成
  - Phase B: 确认页面，勾选可选阶段(8/9/10) + 目标模型配置
  - Phase C: 执行选中的可选阶段 + 多模型对比测试
  - Stage 7(新): 镜头合并 + VFF中文视频生产脚本（替代旧Stage 9英文prompt）
  - 多模型适配层: gpt-5.4 / claude-opus-4-6 / gemini / grok
  - @char_ / @scene_ 引用系统
"""

import asyncio
import json
import os
import re
import shutil
import sys
import time
import traceback
from datetime import datetime

import httpx

# ── 配置 ──────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NOVEL_PATH = os.path.join(SCRIPT_DIR, "我和沈词的长子.txt")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "第7次测试结果")
PROJECT_ID = "novel_shenCi_v7"

STEP_COOLDOWN = 2
MIN_CHAPTER_WORDS = 50

sys.stdout.reconfigure(encoding="utf-8")

# prompt 模板
sys.path.insert(0, os.path.join(SCRIPT_DIR, "..", "backend"))
from services.prompt_templates import TEMPLATES

# 本地模块
from pipeline_db import PipelineDB
from confirm_server import ConfirmServer
from model_adapters import (
    call_api_async, call_api_sync, DEFAULT_MODEL, get_available_models,
)


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
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for i, ch in enumerate(text):
            if ch in ("[", "{"):
                try:
                    return json.loads(text[i:])
                except json.JSONDecodeError:
                    continue
        raise ValueError(f"无法提取JSON:\n{text[:500]}")


# ── 成本追踪 ─────────────────────────────────────────────────────

class CostTracker:
    """全局成本追踪器。"""

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
                "models": {},
            }
        s = self.stages[stage]
        s["input_tokens"] += cost_meta.get("input_tokens", 0)
        s["output_tokens"] += cost_meta.get("output_tokens", 0)
        s["elapsed_s"] += cost_meta.get("elapsed_s", 0)
        s["api_calls"] += 1

        # 按模型统计
        model = cost_meta.get("model", "unknown")
        if model not in s["models"]:
            s["models"][model] = {"calls": 0, "tokens": 0}
        s["models"][model]["calls"] += 1
        s["models"][model]["tokens"] += (
            cost_meta.get("input_tokens", 0) + cost_meta.get("output_tokens", 0)
        )

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

    def to_dict(self) -> dict:
        """序列化为可持久化的字典。"""
        return {
            "stages": self.stages,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_elapsed": self.total_elapsed,
            "total_api_calls": self.total_api_calls,
        }

    def restore_from_dict(self, d: dict):
        """从字典恢复状态（跨session持久化）。"""
        self.stages = d.get("stages", {})
        # stages的key可能是字符串，需要转为int
        self.stages = {int(k) if isinstance(k, str) else k: v
                       for k, v in self.stages.items()}
        self.total_input_tokens = d.get("total_input_tokens", 0)
        self.total_output_tokens = d.get("total_output_tokens", 0)
        self.total_elapsed = d.get("total_elapsed", 0.0)
        self.total_api_calls = d.get("total_api_calls", 0)


cost_tracker = CostTracker()


# ── 文件工具 ──────────────────────────────────────────────────────

def ensure_dir(*parts):
    path = os.path.join(OUTPUT_DIR, *parts)
    os.makedirs(path, exist_ok=True)
    return path


def save_entity_json(folder: str, filename: str, meta: dict, hooks: dict, data: dict):
    dirpath = ensure_dir(folder)
    entity = {"_meta": meta, "_hooks": hooks, "data": data}
    filepath = os.path.join(dirpath, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(entity, f, ensure_ascii=False, indent=2)
    print(f"    → {folder}/{filename}")


def load_entity_json(folder: str, filename: str) -> dict:
    filepath = os.path.join(OUTPUT_DIR, folder, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_index(folder: str, entries: list):
    dirpath = ensure_dir(folder)
    index = {
        "count": len(entries),
        "updated_at": now_iso(),
        "entries": entries,
    }
    filepath = os.path.join(dirpath, "_index.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"    → {folder}/_index.json ({len(entries)} 项)")


def update_entity_hooks(folder: str, filename: str, updates: dict):
    filepath = os.path.join(OUTPUT_DIR, folder, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        entity = json.load(f)
    entity.setdefault("_hooks", {})
    for k, v in updates.items():
        if isinstance(v, list) and isinstance(entity["_hooks"].get(k), list):
            existing = set(str(x) for x in entity["_hooks"][k])
            entity["_hooks"][k].extend(x for x in v if str(x) not in existing)
        else:
            entity["_hooks"][k] = v
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(entity, f, ensure_ascii=False, indent=2)


def save_text(filename: str, content: str):
    filepath = os.path.join(OUTPUT_DIR, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"    → {filename}")


def save_json(filename: str, data):
    filepath = os.path.join(OUTPUT_DIR, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"    → {filename}")


def list_entity_files(folder: str) -> list[str]:
    dirpath = os.path.join(OUTPUT_DIR, folder)
    if not os.path.isdir(dirpath):
        return []
    return sorted(f for f in os.listdir(dirpath)
                  if f.endswith(".json") and f not in ("_index.json", "_scan.json"))


def safe_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\s]+', '_', name)
    return name.strip('_') or 'unnamed'


# ── 流水线状态 ────────────────────────────────────────────────────

STATE_FILE = os.path.join(OUTPUT_DIR, "pipeline_state.json")
TOTAL_STAGES = 11  # Phase A(1-7) + Phase C(8-10) + 报告(11)


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "project": "我和沈词的长子",
        "started_at": now_iso(),
        "current_stage": 1,
        "phase": "A",
        "stages": {str(i): {"status": "pending"} for i in range(1, TOTAL_STAGES + 1)},
        "phase_b_config": {},
    }


def save_state(state: dict):
    filepath = os.path.join(OUTPUT_DIR, "pipeline_state.json")
    # 同时保存cost_tracker
    state["cost_tracker"] = cost_tracker.to_dict()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def mark_stage(state: dict, stage: int, status: str):
    s = state["stages"][str(stage)]
    s["status"] = status
    if status == "running":
        s["started_at"] = now_iso()
    elif status == "completed":
        s["finished_at"] = now_iso()
    state["current_stage"] = stage
    save_state(state)


# ── 确认交互 ──────────────────────────────────────────────────────

def confirm_terminal(stage_name: str, summary_lines: list[str]) -> str:
    print()
    print("═" * 55)
    print(f"  {stage_name} — 完成")
    print("═" * 55)
    for line in summary_lines:
        print(f"  {line}")
    print()
    print("  [Y] 继续下一阶段  [n] 停止  [r] 重跑本阶段")

    while True:
        try:
            choice = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "stop"
        if choice in ("", "y", "yes"):
            return "continue"
        if choice in ("n", "no", "stop"):
            return "stop"
        if choice in ("r", "retry"):
            return "retry"
        print("  请输入 Y/n/r")


def confirm_terminal_phase_b(summary_lines: list[str]) -> dict:
    """终端模式的 Phase B 确认（简化版）。"""
    print()
    print("═" * 55)
    print("  Phase A 完成 — 选择可选阶段")
    print("═" * 55)
    for line in summary_lines:
        print(f"  {line}")
    print()
    print("  可选阶段:")
    print("    8 - 角色状态追踪 (~22min)")
    print("    9 - 对白提取 (~1.5min)")
    print("   10 - 视觉评估 (~3min)")
    print()
    print("  输入要执行的阶段编号 (逗号分隔, 如 8,9,10), 留空跳过, q停止:")

    while True:
        try:
            choice = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return {"action": "stop"}
        if choice == "q":
            return {"action": "stop"}
        if choice == "":
            return {"action": "skip_to_report"}
        try:
            stages = [int(x.strip()) for x in choice.split(",") if x.strip()]
            stages = [s for s in stages if s in (8, 9, 10)]
            return {
                "action": "run_selected",
                "selected_stages": stages,
                "config": {
                    "target_duration": "6s",
                    "target_model": "grok",
                    "test_models": ["gpt-5.4"],
                },
            }
        except ValueError:
            print("  请输入数字，逗号分隔")


_web_server = None


def confirm_web(stage_name: str, stage_number: int, stage_data: dict) -> str:
    global _web_server
    if _web_server is None:
        _web_server = ConfirmServer(port=5678, total_stages=TOTAL_STAGES)
    return _web_server.wait_for_confirm(stage_name, stage_number, stage_data)


def confirm_web_phase_b(stage_data: dict) -> dict:
    global _web_server
    if _web_server is None:
        _web_server = ConfirmServer(port=5678, total_stages=TOTAL_STAGES)
    return _web_server.wait_for_phase_b(stage_data)


def confirm_stage(mode: str, stage_name: str, stage_number: int,
                  summary_lines: list[str], stage_data: dict = None) -> str:
    if mode == "web":
        if stage_data is None:
            stage_data = {"cards": [{"value": line} for line in summary_lines]}
        return confirm_web(stage_name, stage_number, stage_data)
    else:
        return confirm_terminal(stage_name, summary_lines)


async def confirm_stage_async(mode: str, stage_name: str, stage_number: int,
                               summary_lines: list[str], stage_data: dict = None) -> str:
    return await asyncio.to_thread(
        confirm_stage, mode, stage_name, stage_number, summary_lines, stage_data
    )


async def confirm_phase_b_async(mode: str, summary_lines: list[str],
                                 stage_data: dict = None) -> dict:
    if mode == "web":
        return await asyncio.to_thread(confirm_web_phase_b, stage_data or {})
    else:
        return await asyncio.to_thread(confirm_terminal_phase_b, summary_lines)


# ══════════════════════════════════════════════════════════════════
#  Phase A: 必须阶段 Stage 1-7
# ══════════════════════════════════════════════════════════════════

def stage1_chapter_split(db: PipelineDB) -> dict:
    """Stage 1: 章节分割与存储。"""
    novel = read_novel()
    tmpl = TEMPLATES["P01_CHAPTER_SPLIT"]

    print(f"  小说长度: {len(novel)} 字")

    # 带重试的章节分割：如果有效章节<3个，降温重试
    MAX_SPLIT_RETRIES = 3
    temperatures = [tmpl["temperature"], 0.3, 0.1]

    for retry in range(MAX_SPLIT_RETRIES):
        temp = temperatures[min(retry, len(temperatures) - 1)]
        print(f"  调用 P01_CHAPTER_SPLIT (temperature={temp}"
              f"{', 重试' + str(retry) if retry > 0 else ''})...")

        resp, cost = call_api_sync(
            system=tmpl["system"],
            user=tmpl["user"].format(text=novel),
            temperature=temp,
            max_tokens=tmpl["max_tokens"],
        )
        cost_tracker.add(1, cost)
        markers = extract_json(resp)

        print(f"  API 返回 {len(markers)} 个章节标记 ({cost['elapsed_s']:.1f}s)")

        # 预检：计算有效章节数
        valid_count = 0
        for ch in markers:
            start = ch.get("start_marker", "")
            end = ch.get("end_marker", "")
            si = novel.find(start) if start else -1
            ei = novel.find(end) if end else -1
            if si >= 0 and ei >= 0:
                content_len = ei + len(end) - si
                if content_len >= MIN_CHAPTER_WORDS:
                    valid_count += 1

        if valid_count >= 3:
            break
        print(f"    ⚠ 仅{valid_count}个有效章节，自动降温重试...")

    print(f"  提取完整章节内容...")

    ensure_dir("chapters")
    index_entries = []
    skipped = []

    for i, ch in enumerate(markers):
        ch_id = f"ch_{i:03d}"
        title = ch.get("title", f"第{i+1}章")
        start = ch.get("start_marker", "")
        end = ch.get("end_marker", "")

        si = novel.find(start) if start else -1
        ei = novel.find(end) if end else -1
        if si >= 0 and ei >= 0:
            content = novel[si:ei + len(end)]
        else:
            content = f"（未能定位章节内容: {title}）"

        word_count = len(content)
        if word_count < MIN_CHAPTER_WORDS:
            skipped.append({"id": ch_id, "title": title, "word_count": word_count})
            print(f"    ⚠ 跳过小章节: {ch_id} {title} ({word_count}字)")
            continue

        filename = f"{ch_id}_{safe_filename(title)}.json"
        meta = {
            "id": ch_id, "type": "chapter",
            "pipeline_step": "chapter_split", "created_at": now_iso(),
        }
        hooks = {
            "ready_for": ["summary", "scene_extract", "beat_extract", "character_scan"],
            "canvas_node_type": "input_chapter",
            "downstream": {"scenes": [], "beats": [], "characters_mentioned": []},
        }
        data = {
            "title": title, "order": i, "content": content,
            "word_count": word_count, "start_marker": start,
            "end_marker": end, "summary": "",
        }

        save_entity_json("chapters", filename, meta, hooks, data)
        db.upsert_chapter(PROJECT_ID, {
            "id": ch_id, "title": title, "content": content,
            "summary": "", "word_count": word_count, "order": i,
            "start_marker": start, "end_marker": end,
        })
        index_entries.append({
            "id": ch_id, "title": title, "filename": filename,
            "word_count": word_count, "order": i,
        })

    save_index("chapters", index_entries)
    if skipped:
        save_json("skipped_chapters.json", skipped)

    summary_lines = [f"共分割 {len(markers)} 个章节, 有效 {len(index_entries)} 个:"]
    for e in index_entries:
        summary_lines.append(f"  {e['order']+1}. {e['title']} ({e['word_count']}字)")
    if skipped:
        summary_lines.append(f"  ⚠ 跳过 {len(skipped)} 个小章节")
    summary_lines.append(f"  成本: {cost_tracker.stage_summary(1)}")

    return {"summary_lines": summary_lines}


async def stage2_summary_and_scan(db: PipelineDB) -> dict:
    """Stage 2: 章节摘要 + 角色扫描。"""
    ch_files = list_entity_files("chapters")
    print(f"  共 {len(ch_files)} 个章节待摘要 + 1次角色扫描")

    tmpl_summary = TEMPLATES["P01B_CHAPTER_SUMMARY"]
    tmpl_scan = TEMPLATES["P03A_CHARACTER_SCAN"]

    async def summarize_chapter(fname, idx):
        entity = load_entity_json("chapters", fname)
        ch_data = entity["data"]
        ch_id = entity["_meta"]["id"]
        title = ch_data["title"]
        content = ch_data["content"]

        print(f"  [{idx+1}/{len(ch_files)}] 摘要: {title} ({len(content)}字)...", flush=True)

        resp, cost = await call_api_async(
            system=tmpl_summary["system"],
            user=tmpl_summary["user"].format(chapter_title=title, text=content),
            temperature=tmpl_summary["temperature"],
            max_tokens=tmpl_summary["max_tokens"],
        )
        cost_tracker.add(2, cost)

        summary = resp.strip()
        entity["data"]["summary"] = summary
        filepath = os.path.join(OUTPUT_DIR, "chapters", fname)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(entity, f, ensure_ascii=False, indent=2)

        db.update_chapter_summary(ch_id, summary)
        print(f"    ✓ {title} ({cost['elapsed_s']:.1f}s)")
        return {"ch_id": ch_id, "title": title, "summary": summary}

    summary_tasks = [summarize_chapter(fname, i) for i, fname in enumerate(ch_files)]
    summaries = await asyncio.gather(*summary_tasks)

    synopsis = "\n\n".join(f"【{s['title']}】\n{s['summary']}" for s in summaries)
    ensure_dir("knowledge")
    save_text(os.path.join("knowledge", "synopsis.txt"), synopsis)

    print(f"  角色名单扫描...")
    resp, cost = await call_api_async(
        system=tmpl_scan["system"],
        user=tmpl_scan["user"].format(synopsis=synopsis),
        temperature=tmpl_scan["temperature"],
        max_tokens=tmpl_scan["max_tokens"],
    )
    cost_tracker.add(2, cost)
    char_list = extract_json(resp)
    print(f"  ✓ 发现 {len(char_list)} 个角色 ({cost['elapsed_s']:.1f}s)")

    save_json(os.path.join("characters", "_scan.json"), char_list)

    summary_lines = [
        f"摘要: {len(summaries)} 章, synopsis {len(synopsis)} 字",
        f"角色扫描: {len(char_list)} 个角色",
        f"成本: {cost_tracker.stage_summary(2)}",
    ]
    return {"summary_lines": summary_lines}


async def stage3_character_detail_and_knowledge(db: PipelineDB) -> dict:
    """Stage 3: 角色详情 + 知识库构建。"""
    char_list = json.load(open(os.path.join(OUTPUT_DIR, "characters", "_scan.json"),
                               "r", encoding="utf-8"))
    synopsis_path = os.path.join(OUTPUT_DIR, "knowledge", "synopsis.txt")
    with open(synopsis_path, "r", encoding="utf-8") as f:
        synopsis = f.read()

    main_chars = [c for c in char_list
                  if c.get("role") in ("protagonist", "antagonist", "supporting")]
    all_names = [c.get("name", "?") for c in char_list]

    tmpl_detail = TEMPLATES["P03B_CHARACTER_DETAIL"]
    print(f"  主要角色 {len(main_chars)} 个 + 知识库构建 1次")

    async def detail_character(ch, idx):
        name = ch.get("name", "?")
        brief = ch.get("brief", ch.get("description", ""))
        other_names = [n for n in all_names if n != name]

        print(f"  [{idx+1}/{len(main_chars)}] 角色详情: {name}...", flush=True)

        resp, cost = await call_api_async(
            system=tmpl_detail["system"],
            user=tmpl_detail["user"].format(
                character_name=name, character_brief=brief,
                other_characters=", ".join(other_names[:10]),
                synopsis=synopsis,
            ),
            temperature=tmpl_detail["temperature"],
            max_tokens=tmpl_detail["max_tokens"],
        )
        cost_tracker.add(3, cost)

        detail = extract_json(resp)
        char_id = f"char_{safe_filename(name)}"
        filename = f"{safe_filename(name)}.json"

        meta = {
            "id": char_id, "type": "character",
            "pipeline_step": "character_detail", "created_at": now_iso(),
        }
        hooks = {
            "ready_for": ["visual_prompt", "arc_analysis", "casting"],
            "canvas_node_type": "character_profile",
            "appears_in_chapters": [], "appears_in_scenes": [],
        }
        data = {
            "name": name,
            "aliases": detail.get("aliases", []),
            "role": ch.get("role", "supporting"),
            "age_range": detail.get("age_range", ""),
            "appearance": detail.get("appearance", {}),
            "costume": detail.get("costume", {}),
            "casting_tags": detail.get("casting_tags", []),
            "visual_reference": detail.get("visual_reference", ""),
            "description": detail.get("description", brief),
            "personality": detail.get("personality", ""),
            "desire": detail.get("desire", ""),
            "flaw": detail.get("flaw", ""),
            "arc": detail.get("arc", ""),
            "relationships": detail.get("relationships", []),
        }

        save_entity_json("characters", filename, meta, hooks, data)
        db.upsert_character(PROJECT_ID, {"id": char_id, **data})
        print(f"    ✓ {name} ({cost['elapsed_s']:.1f}s)")
        return {"id": char_id, "name": name, "role": data["role"],
                "filename": filename, "description": data["description"][:50]}

    async def build_knowledge():
        loc_names = "未知"
        scene_index_path = os.path.join(OUTPUT_DIR, "scenes", "_index.json")
        if os.path.exists(scene_index_path):
            with open(scene_index_path, "r", encoding="utf-8") as f:
                scene_index = json.load(f)
            locs = list(set(e.get("location", "")
                           for e in scene_index["entries"] if e.get("location")))
            if locs:
                loc_names = ", ".join(locs[:10])

        char_names = ", ".join(all_names[:10])
        tmpl = TEMPLATES["P05_KNOWLEDGE_BASE_V2"]
        print(f"  知识库构建...", flush=True)

        resp, cost = await call_api_async(
            system=tmpl["system"],
            user=tmpl["user"].format(
                synopsis=synopsis, character_names=char_names,
                location_names=loc_names,
            ),
            temperature=tmpl["temperature"],
            max_tokens=tmpl["max_tokens"],
        )
        cost_tracker.add(3, cost)

        data = extract_json(resp)
        wb = data.get("world_building", {})
        sg = data.get("style_guide", {})

        ensure_dir("knowledge")
        save_json(os.path.join("knowledge", "world_building.json"), wb)
        save_json(os.path.join("knowledge", "style_guide.json"), sg)

        db.upsert_knowledge(PROJECT_ID, {
            "world_building": wb, "style_guide": sg, "synopsis": synopsis,
        })

        print(f"    ✓ 知识库 ({cost['elapsed_s']:.1f}s)")
        return {"world_building": wb, "style_guide": sg}

    detail_tasks = [detail_character(ch, i) for i, ch in enumerate(main_chars)]
    all_tasks = detail_tasks + [build_knowledge()]
    results = await asyncio.gather(*all_tasks, return_exceptions=True)

    char_results = []
    for r in results:
        if isinstance(r, Exception):
            print(f"    ⚠ 任务失败: {r}")
            traceback.print_exc()
        elif isinstance(r, dict) and "name" in r and "id" in r:
            char_results.append(r)

    index_entries = list(char_results)
    for ch in char_list:
        if ch.get("role") == "minor":
            name = ch.get("name", "?")
            index_entries.append({
                "id": f"char_{safe_filename(name)}", "name": name,
                "role": "minor", "filename": None,
                "description": ch.get("brief", "")[:50],
            })

    save_index("characters", index_entries)

    summary_lines = [
        f"角色详情: {len(char_results)} 个主要角色",
        f"成本: {cost_tracker.stage_summary(3)}",
    ]
    return {"summary_lines": summary_lines}


async def stage4_scene_and_beat(db: PipelineDB) -> dict:
    """Stage 4: 场景提取(原文) + 节拍提取。"""
    synopsis_path = os.path.join(OUTPUT_DIR, "knowledge", "synopsis.txt")
    with open(synopsis_path, "r", encoding="utf-8") as f:
        synopsis = f.read()

    char_index_path = os.path.join(OUTPUT_DIR, "characters", "_index.json")
    with open(char_index_path, "r", encoding="utf-8") as f:
        char_index = json.load(f)
    char_names = ", ".join(e["name"] for e in char_index["entries"][:10])

    ch_index_path = os.path.join(OUTPUT_DIR, "chapters", "_index.json")
    with open(ch_index_path, "r", encoding="utf-8") as f:
        ch_index = json.load(f)
    ch_entries = ch_index["entries"]

    tmpl_scene = TEMPLATES["P04_SCENE_EXTRACT"]
    tmpl_beat = TEMPLATES["P10_NOVEL_TO_BEAT"]

    scene_order_counter = [0]
    all_scenes_entries = []
    scene_lock = asyncio.Lock()

    async def extract_scenes_for_chapter(ci, ch_entry):
        ch_id = ch_entry["id"]
        ch_title = ch_entry["title"]
        ch_entity = load_entity_json("chapters", ch_entry["filename"])
        ch_content = ch_entity["data"]["content"]

        batch_text = f"【{ch_title}】\n{ch_content}"
        print(f"  [场景 {ci+1}/{len(ch_entries)}] {ch_title} ({len(ch_content)}字)...", flush=True)

        try:
            resp, cost = await call_api_async(
                system=tmpl_scene["system"],
                user=tmpl_scene["user"].format(text=batch_text, character_names=char_names),
                temperature=tmpl_scene["temperature"],
                max_tokens=8192,
            )
            cost_tracker.add(4, cost)
            scenes = extract_json(resp)
            if not isinstance(scenes, list):
                scenes = [scenes]
        except Exception as e:
            print(f"    ⚠ 场景提取跳过 {ch_title}: {e}")
            return []

        results = []
        async with scene_lock:
            for s in scenes:
                scene_id = f"scene_{scene_order_counter[0]:03d}"
                filename = f"{scene_id}.json"

                tension = s.get("tension_score", 0.5)
                dramatic_intensity = round(tension * 2 - 1, 3)

                meta = {
                    "id": scene_id, "type": "scene",
                    "pipeline_step": "scene_extract", "created_at": now_iso(),
                }
                hooks = {
                    "ready_for": ["shot_design", "vff_generate"],
                    "canvas_node_type": "scene",
                    "source_chapter": ch_id,
                    "characters_present": s.get("characters_present", []),
                }
                data = {
                    "heading": s.get("heading", ""),
                    "location": s.get("location", ""),
                    "time_of_day": s.get("time_of_day", ""),
                    "description": s.get("description", ""),
                    "action": s.get("action", ""),
                    "dialogue": s.get("dialogue", []),
                    "characters_present": s.get("characters_present", []),
                    "key_props": s.get("key_props", []),
                    "dramatic_purpose": s.get("dramatic_purpose", ""),
                    "tension_score": tension,
                    "dramatic_intensity": dramatic_intensity,
                    "order": scene_order_counter[0],
                }

                save_entity_json("scenes", filename, meta, hooks, data)
                db.upsert_scene(PROJECT_ID, {"id": scene_id, "chapter_id": ch_id, **data})
                db.update_scene_intensity(scene_id, dramatic_intensity)

                results.append({
                    "id": scene_id, "filename": filename,
                    "heading": data["heading"], "location": data["location"],
                    "tension_score": tension, "dramatic_intensity": dramatic_intensity,
                    "order": scene_order_counter[0], "source_chapter": ch_id,
                })
                scene_order_counter[0] += 1

        update_entity_hooks("chapters", ch_entry["filename"], {
            "downstream": {
                "scenes": [r["id"] for r in results],
                "beats": ch_entity["_hooks"].get("downstream", {}).get("beats", []),
                "characters_mentioned": ch_entity["_hooks"].get("downstream", {}).get("characters_mentioned", []),
            }
        })

        print(f"    ✓ {ch_title}: {len(results)} 场景 ({cost['elapsed_s']:.1f}s)")
        return results

    async def extract_beats():
        print(f"  [节拍] 调用 P10_NOVEL_TO_BEAT...", flush=True)
        resp, cost = await call_api_async(
            system=tmpl_beat["system"],
            user=tmpl_beat["user"].format(text=synopsis),
            temperature=tmpl_beat["temperature"],
            max_tokens=tmpl_beat["max_tokens"],
        )
        cost_tracker.add(4, cost)
        beats = extract_json(resp)
        if not isinstance(beats, list):
            beats = [beats]

        ensure_dir("beats")
        index_entries = []

        for i, b in enumerate(beats):
            beat_id = f"beat_{i:03d}"
            filename = f"{beat_id}.json"
            emotional_value = b.get("emotional_value", 0)

            meta = {
                "id": beat_id, "type": "beat",
                "pipeline_step": "beat_extract", "created_at": now_iso(),
            }
            hooks = {
                "ready_for": ["rhythm_analysis", "arc_mapping"],
                "canvas_node_type": "beat", "related_scenes": [],
            }
            data = {
                "title": b.get("title", f"Beat {i+1}"),
                "description": b.get("description", ""),
                "beat_type": b.get("beat_type", "event"),
                "save_the_cat": b.get("save_the_cat", ""),
                "emotional_value": emotional_value,
                "dramatic_intensity": emotional_value,
                "hook_potential": b.get("hook_potential", "medium"),
                "rhythm_warning": str(b.get("rhythm_warning", "false")),
                "order": i,
            }

            save_entity_json("beats", filename, meta, hooks, data)
            db.upsert_beat(PROJECT_ID, {"id": beat_id, **data})
            db.update_beat_intensity(beat_id, emotional_value)

            index_entries.append({
                "id": beat_id, "filename": filename,
                "title": data["title"], "beat_type": data["beat_type"],
                "save_the_cat": data["save_the_cat"],
                "emotional_value": emotional_value, "order": i,
            })

        save_index("beats", index_entries)
        print(f"    ✓ {len(beats)} 个节拍 ({cost['elapsed_s']:.1f}s)")
        return index_entries

    ensure_dir("scenes")
    scene_tasks = [extract_scenes_for_chapter(ci, ch) for ci, ch in enumerate(ch_entries)]
    all_tasks = scene_tasks + [extract_beats()]
    results = await asyncio.gather(*all_tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, Exception):
            print(f"    ⚠ 任务失败: {r}")
            traceback.print_exc()
        elif isinstance(r, list) and len(r) > 0 and isinstance(r[0], dict) and "heading" in r[0]:
            all_scenes_entries.extend(r)

    save_index("scenes", all_scenes_entries)

    beat_entries = []
    for r in results:
        if isinstance(r, list) and len(r) > 0 and isinstance(r[0], dict) and "beat_type" in r[0]:
            beat_entries = r

    summary_lines = [
        f"场景提取: {len(all_scenes_entries)} 个",
        f"节拍提取: {len(beat_entries)} 个",
        f"成本: {cost_tracker.stage_summary(4)}",
    ]
    return {"summary_lines": summary_lines}


async def stage5_beat_scene_bind(db: PipelineDB) -> dict:
    """Stage 5: 节拍↔场景绑定。"""
    beat_files = list_entity_files("beats")
    scene_files = list_entity_files("scenes")

    beats_summary = []
    for fname in beat_files:
        entity = load_entity_json("beats", fname)
        beats_summary.append({
            "id": entity["_meta"]["id"],
            "title": entity["data"]["title"],
            "description": entity["data"]["description"][:200],
            "beat_type": entity["data"]["beat_type"],
            "save_the_cat": entity["data"].get("save_the_cat", ""),
        })

    scenes_summary = []
    for fname in scene_files:
        entity = load_entity_json("scenes", fname)
        scenes_summary.append({
            "id": entity["_meta"]["id"],
            "heading": entity["data"]["heading"],
            "dramatic_purpose": entity["data"].get("dramatic_purpose", ""),
            "description": entity["data"]["description"][:200],
            "source_chapter": entity["_hooks"].get("source_chapter", ""),
        })

    tmpl = TEMPLATES["P08_BEAT_SCENE_BIND"]
    print(f"  绑定 {len(beats_summary)} 节拍 ↔ {len(scenes_summary)} 场景...")

    resp, cost = await call_api_async(
        system=tmpl["system"],
        user=tmpl["user"].format(
            beats_summary=fmt_json(beats_summary),
            scenes_summary=fmt_json(scenes_summary),
        ),
        temperature=tmpl["temperature"],
        max_tokens=tmpl["max_tokens"],
    )
    cost_tracker.add(5, cost)

    bindings = extract_json(resp)
    binding_list = bindings.get("bindings", [])
    unbound_scenes = bindings.get("unbound_scenes", [])
    unbound_beats = bindings.get("unbound_beats", [])

    for b in binding_list:
        beat_id = b.get("beat_id", "")
        scene_ids = b.get("scene_ids", [])

        for fname in beat_files:
            entity = load_entity_json("beats", fname)
            if entity["_meta"]["id"] == beat_id:
                update_entity_hooks("beats", fname, {"related_scenes": scene_ids})
                db.update_beat_intensity(
                    beat_id,
                    entity["data"].get("dramatic_intensity",
                                       entity["data"].get("emotional_value", 0)),
                    related_scenes=scene_ids,
                )
                break

        for scene_id in scene_ids:
            for sfname in scene_files:
                entity = load_entity_json("scenes", sfname)
                if entity["_meta"]["id"] == scene_id:
                    existing_beats = entity["_hooks"].get("related_beats", [])
                    if beat_id not in existing_beats:
                        existing_beats.append(beat_id)
                    update_entity_hooks("scenes", sfname, {"related_beats": existing_beats})
                    db.update_scene_intensity(
                        scene_id,
                        entity["data"].get("dramatic_intensity", 0),
                        related_beats=existing_beats,
                    )
                    break

    save_json("beat_scene_bindings.json", bindings)

    summary_lines = [
        f"绑定关系: {len(binding_list)} 条",
        f"孤立场景: {len(unbound_scenes)} 个",
        f"孤立节拍: {len(unbound_beats)} 个",
        f"成本: {cost_tracker.stage_summary(5)}",
    ]
    return {"summary_lines": summary_lines}


async def stage6_scene_to_shot(db: PipelineDB) -> dict:
    """Stage 6: Scene→Shot拆分。"""
    scene_files = list_entity_files("scenes")
    if not scene_files:
        return {"summary_lines": ["无场景数据"]}

    sg_path = os.path.join(OUTPUT_DIR, "knowledge", "style_guide.json")
    style_guide = "{}"
    if os.path.exists(sg_path):
        with open(sg_path, "r", encoding="utf-8") as f:
            style_guide = f.read()

    char_files = list_entity_files("characters")
    char_profiles = {}
    for cfname in char_files:
        entity = load_entity_json("characters", cfname)
        name = entity["data"].get("name", "")
        char_profiles[name] = {
            "name": name,
            "appearance": entity["data"].get("appearance", {}),
            "costume": entity["data"].get("costume", {}),
            "visual_reference": entity["data"].get("visual_reference", ""),
        }

    tmpl = TEMPLATES["P06_SCENE_TO_SHOT"]
    ensure_dir("shots")
    all_shots = []
    shot_order_counter = [0]

    async def process_scene(fname, idx):
        entity = load_entity_json("scenes", fname)
        scene_id = entity["_meta"]["id"]
        scene_data = entity["data"]

        present_chars = scene_data.get("characters_present", [])
        profiles_for_scene = {n: char_profiles[n] for n in present_chars if n in char_profiles}

        print(f"  [Shot {idx+1}/{len(scene_files)}] {scene_id}: "
              f"{scene_data.get('heading', '')}...", flush=True)

        try:
            resp, cost = await call_api_async(
                system=tmpl["system"],
                user=tmpl["user"].format(
                    scene_json=fmt_json(scene_data),
                    style_guide=style_guide,
                    character_profiles=fmt_json(profiles_for_scene),
                ),
                temperature=tmpl["temperature"],
                max_tokens=tmpl["max_tokens"],
            )
            cost_tracker.add(6, cost)
            shots = extract_json(resp)
            if not isinstance(shots, list):
                shots = [shots]
        except Exception as e:
            print(f"    ⚠ Shot拆分跳过 {scene_id}: {e}")
            return []

        results = []
        for s in shots:
            shot_id = f"shot_{shot_order_counter[0]:04d}"
            shot_order_counter[0] += 1

            shot_data = {
                "id": shot_id, "scene_id": scene_id,
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
                "order": shot_order_counter[0] - 1,
            }

            db.upsert_shot(PROJECT_ID, shot_data)
            results.append(shot_data)

        save_json(os.path.join("shots", f"{scene_id}_shots.json"), results)
        print(f"    ✓ {scene_id}: {len(results)} 镜头 ({cost['elapsed_s']:.1f}s)")
        return results

    tasks = [process_scene(fname, i) for i, fname in enumerate(scene_files)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, Exception):
            print(f"    ⚠ 任务失败: {r}")
        elif isinstance(r, list):
            all_shots.extend(r)

    # ── 按场景顺序重编号 shot ID 和 order ──
    # asyncio.gather 并发导致 shot_order_counter 按完成顺序递增,
    # 这里按 scene_id 数字顺序排序后重新分配连续编号.
    def scene_order_key(shot):
        m = re.search(r'scene_(\d+)', shot.get("scene_id", ""))
        return int(m.group(1)) if m else 9999

    all_shots.sort(key=lambda s: (scene_order_key(s), s.get("shot_number", 0)))

    for idx, shot in enumerate(all_shots):
        shot["id"] = f"shot_{idx:04d}"
        shot["order"] = idx

    # 重新按 scene 分组保存文件 + 更新数据库
    from collections import defaultdict
    shots_by_scene = defaultdict(list)
    for s in all_shots:
        shots_by_scene[s["scene_id"]].append(s)

    for scene_id, scene_shots in shots_by_scene.items():
        save_json(os.path.join("shots", f"{scene_id}_shots.json"), scene_shots)
        for s in scene_shots:
            db.upsert_shot(PROJECT_ID, s)

    print(f"  ✓ 镜头重编号完成: shot_0000 ~ shot_{len(all_shots)-1:04d}")

    save_index("shots", [{"id": s["id"], "scene_id": s["scene_id"],
                           "framing": s["framing"], "goal": s["goal"][:50]}
                          for s in all_shots])

    summary_lines = [
        f"Shot拆分: {len(all_shots)} 个镜头 (覆盖 {len(scene_files)} 场景)",
        f"成本: {cost_tracker.stage_summary(6)}",
    ]
    return {"summary_lines": summary_lines}


async def stage7_vff_generate(db: PipelineDB, target_duration: str = "6s",
                               target_model: str = "grok") -> dict:
    """Stage 7 (新): VFF提示词生成 — 镜头合并 + 中文Visual Fusion Flow。

    每个scene一次API调用，将该场景的所有shot合并为VFF segments。
    """
    scene_files = list_entity_files("scenes")
    if not scene_files:
        return {"summary_lines": ["无场景数据"]}

    # 加载 style_guide
    sg_path = os.path.join(OUTPUT_DIR, "knowledge", "style_guide.json")
    style_guide = "{}"
    if os.path.exists(sg_path):
        with open(sg_path, "r", encoding="utf-8") as f:
            style_guide = f.read()

    # 加载角色档案
    char_files = list_entity_files("characters")
    char_profiles = {}
    for cfname in char_files:
        entity = load_entity_json("characters", cfname)
        name = entity["data"].get("name", "")
        char_id = entity["_meta"]["id"]
        char_profiles[name] = {
            "id": char_id,
            "name": name,
            "appearance": entity["data"].get("appearance", {}),
            "costume": entity["data"].get("costume", {}),
            "visual_reference": entity["data"].get("visual_reference", ""),
            "personality": entity["data"].get("personality", ""),
        }

    tmpl = TEMPLATES["P11_VFF_GENERATE"]
    ensure_dir("segments")
    ensure_dir("vff_prompts")

    all_segments = []
    all_vff = []
    segment_counter = [0]

    async def process_scene_vff(fname, idx):
        entity = load_entity_json("scenes", fname)
        scene_id = entity["_meta"]["id"]
        scene_data = entity["data"]

        # 加载该场景的shots
        shots_path = os.path.join(OUTPUT_DIR, "shots", f"{scene_id}_shots.json")
        if not os.path.exists(shots_path):
            print(f"    ⚠ 跳过 {scene_id}: 无shot数据")
            return [], []

        with open(shots_path, "r", encoding="utf-8") as f:
            shots = json.load(f)

        if not shots:
            return [], []

        # 获取在场角色的档案
        present_chars = scene_data.get("characters_present", [])
        profiles_for_scene = {n: char_profiles[n]
                              for n in present_chars if n in char_profiles}

        print(f"  [VFF {idx+1}/{len(scene_files)}] {scene_id}: "
              f"{len(shots)} shots → VFF...", flush=True)

        try:
            resp, cost = await call_api_async(
                system=tmpl["system"],
                user=tmpl["user"].format(
                    scene_json=fmt_json(scene_data),
                    shots_json=fmt_json(shots),
                    character_profiles=fmt_json(profiles_for_scene),
                    style_guide=style_guide,
                    target_duration=target_duration,
                    target_model=target_model,
                    scene_id=scene_id,
                ),
                temperature=tmpl["temperature"],
                max_tokens=tmpl["max_tokens"],
            )
            cost_tracker.add(7, cost)

            vff_segments = extract_json(resp)
            if not isinstance(vff_segments, list):
                vff_segments = [vff_segments]
        except Exception as e:
            print(f"    ⚠ VFF生成跳过 {scene_id}: {e}")
            return [], []

        scene_segments = []
        scene_vffs = []

        for seg in vff_segments:
            seg_id = f"seg_{segment_counter[0]:04d}"
            vff_id = f"vff_{segment_counter[0]:04d}"
            segment_counter[0] += 1

            # 保存 segment
            seg_data = {
                "id": seg_id,
                "scene_id": scene_id,
                "shot_ids": seg.get("shot_ids", []),
                "segment_number": seg.get("segment_number", 0),
                "target_duration": seg.get("target_duration", target_duration),
                "target_model": target_model,
                "merge_rationale": seg.get("merge_rationale", ""),
                "order": segment_counter[0] - 1,
            }
            db.upsert_segment(PROJECT_ID, seg_data)
            scene_segments.append(seg_data)

            # 保存 VFF prompt
            vff_data = {
                "id": vff_id,
                "segment_id": seg_id,
                "scene_id": scene_id,
                "continuity": seg.get("continuity", ""),
                "time_scene_props": seg.get("time_scene_props", ""),
                "vff_body": seg.get("vff_body", ""),
                "character_refs": seg.get("character_refs", []),
                "scene_refs": seg.get("scene_refs", []),
                "merge_rationale": seg.get("merge_rationale", ""),
                "style_metadata": seg.get("style_metadata", {}),
                "raw_text": fmt_json(seg),
            }
            db.upsert_vff_prompt(PROJECT_ID, vff_data)
            scene_vffs.append(vff_data)

        # 保存文件
        save_json(os.path.join("segments", f"{scene_id}_segments.json"), scene_segments)
        save_json(os.path.join("vff_prompts", f"{scene_id}_vff.json"), scene_vffs)

        print(f"    ✓ {scene_id}: {len(shots)} shots → {len(scene_segments)} segments "
              f"({cost['elapsed_s']:.1f}s)")
        return scene_segments, scene_vffs

    tasks = [process_scene_vff(fname, i) for i, fname in enumerate(scene_files)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, Exception):
            print(f"    ⚠ 任务失败: {r}")
        elif isinstance(r, tuple) and len(r) == 2:
            segs, vffs = r
            all_segments.extend(segs)
            all_vff.extend(vffs)

    save_index("segments", [{"id": s["id"], "scene_id": s["scene_id"],
                              "shot_ids": s["shot_ids"],
                              "target_duration": s["target_duration"]}
                             for s in all_segments])
    save_index("vff_prompts", [{"id": v["id"], "segment_id": v["segment_id"],
                                 "scene_id": v["scene_id"],
                                 "vff_body": v["vff_body"][:80]}
                                for v in all_vff])

    # 统计 @引用
    total_char_refs = sum(len(v.get("character_refs", [])) for v in all_vff)
    total_scene_refs = sum(len(v.get("scene_refs", [])) for v in all_vff)

    summary_lines = [
        f"VFF生成: {len(all_vff)} 段 (从 {len(scene_files)} 场景合并)",
        f"目标时长: {target_duration}, 目标模型: {target_model}",
        f"@char_ 引用: {total_char_refs} 个, @scene_ 引用: {total_scene_refs} 个",
        f"成本: {cost_tracker.stage_summary(7)}",
    ]

    web_data = {
        "stats": {
            "章节数": db.table_count("chapters"),
            "角色数": db.table_count("characters"),
            "场景数": db.table_count("scenes"),
            "节拍数": db.table_count("beats"),
            "镜头数": db.table_count("shots"),
            "VFF段数": len(all_vff),
        },
        "cost": {
            "api_calls": cost_tracker.total_api_calls,
            "tokens": cost_tracker.total_input_tokens + cost_tracker.total_output_tokens,
            "elapsed": f"{cost_tracker.total_elapsed:.0f}",
        },
        "items_title": "VFF 样本",
        "items": [
            {"idx": i+1, "name": v["segment_id"],
             "tag": v.get("scene_id", ""),
             "desc": v.get("vff_body", "")[:100]}
            for i, v in enumerate(all_vff[:10])
        ],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


# ══════════════════════════════════════════════════════════════════
#  Phase C: 可选阶段 Stage 8-10
# ══════════════════════════════════════════════════════════════════

async def stage8_character_state(db: PipelineDB) -> dict:
    """Stage 8 (可选): 角色状态追踪。"""
    scene_files = list_entity_files("scenes")
    if not scene_files:
        return {"summary_lines": ["无场景数据"]}

    char_files = list_entity_files("characters")
    char_profiles = {}
    for cfname in char_files:
        entity = load_entity_json("characters", cfname)
        name = entity["data"].get("name", "")
        char_profiles[name] = {
            "name": name,
            "personality": entity["data"].get("personality", ""),
            "desire": entity["data"].get("desire", ""),
            "flaw": entity["data"].get("flaw", ""),
        }

    tmpl = TEMPLATES["P07_CHARACTER_STATE"]
    ensure_dir("character_states")
    all_states = []
    state_counter = [0]
    previous_states_map = {}

    for idx, fname in enumerate(scene_files):
        entity = load_entity_json("scenes", fname)
        scene_id = entity["_meta"]["id"]
        scene_data = entity["data"]

        present_chars = scene_data.get("characters_present", [])
        profiles_for_scene = {n: char_profiles[n] for n in present_chars if n in char_profiles}

        if idx > 0:
            prev_scene_id = load_entity_json("scenes", scene_files[idx-1])["_meta"]["id"]
            prev_states = previous_states_map.get(prev_scene_id, "无前一场景状态")
        else:
            prev_states = "这是第一个场景，无前序状态"

        print(f"  [状态 {idx+1}/{len(scene_files)}] {scene_id}...", flush=True)

        try:
            resp, cost = await call_api_async(
                system=tmpl["system"],
                user=tmpl["user"].format(
                    scene_json=fmt_json(scene_data),
                    character_profiles=fmt_json(profiles_for_scene),
                    previous_states=(fmt_json(prev_states)
                                     if isinstance(prev_states, (dict, list))
                                     else prev_states),
                ),
                temperature=tmpl["temperature"],
                max_tokens=tmpl["max_tokens"],
            )
            cost_tracker.add(8, cost)
            states = extract_json(resp)
            if not isinstance(states, list):
                states = [states]
        except Exception as e:
            print(f"    ⚠ 状态追踪跳过 {scene_id}: {e}")
            continue

        scene_states = []
        for s in states:
            cs_id = f"cs_{state_counter[0]:04d}"
            state_counter[0] += 1
            char_name = s.get("character", "")
            char_id = f"char_{safe_filename(char_name)}"

            cs_data = {
                "id": cs_id, "character_id": char_id,
                "scene_id": scene_id,
                "emotion": s.get("emotion", ""),
                "inner_objective": s.get("inner_objective", ""),
                "opponent_tension": s.get("opponent_tension", {}),
                "action_beat": s.get("action_beat", ""),
                "status_note": s.get("status_note", ""),
            }
            db.upsert_character_state(PROJECT_ID, cs_data)
            scene_states.append(cs_data)
            all_states.append(cs_data)

        previous_states_map[scene_id] = states
        save_json(os.path.join("character_states", f"{scene_id}_states.json"), scene_states)
        print(f"    ✓ {scene_id}: {len(scene_states)} 角色状态 ({cost['elapsed_s']:.1f}s)")

    save_index("character_states", [{"id": s["id"], "scene_id": s["scene_id"],
                                      "character_id": s["character_id"]}
                                     for s in all_states])

    summary_lines = [
        f"角色状态: {len(all_states)} 条 (覆盖 {len(scene_files)} 场景)",
        f"成本: {cost_tracker.stage_summary(8)}",
    ]
    return {"summary_lines": summary_lines}


async def stage9_dialogue_extract(db: PipelineDB) -> dict:
    """Stage 9 (可选): 对白提取。"""
    ch_index_path = os.path.join(OUTPUT_DIR, "chapters", "_index.json")
    with open(ch_index_path, "r", encoding="utf-8") as f:
        ch_index = json.load(f)
    ch_entries = ch_index["entries"]

    scene_index_path = os.path.join(OUTPUT_DIR, "scenes", "_index.json")
    with open(scene_index_path, "r", encoding="utf-8") as f:
        scene_index = json.load(f)
    scene_entries = scene_index["entries"]

    char_index_path = os.path.join(OUTPUT_DIR, "characters", "_index.json")
    with open(char_index_path, "r", encoding="utf-8") as f:
        char_index = json.load(f)
    char_names = ", ".join(e["name"] for e in char_index["entries"][:15])

    tmpl = TEMPLATES["P09_DIALOGUE_EXTRACT"]
    ensure_dir("dialogue")
    all_dialogue = []
    dialogue_counter = [0]

    async def extract_dialogue_for_chapter(ci, ch_entry):
        ch_id = ch_entry["id"]
        ch_title = ch_entry["title"]
        ch_entity = load_entity_json("chapters", ch_entry["filename"])
        ch_content = ch_entity["data"]["content"]

        ch_scenes = [s for s in scene_entries if s.get("source_chapter") == ch_id]
        scenes_list = fmt_json([{"id": s["id"], "heading": s.get("heading", "")}
                                for s in ch_scenes])

        print(f"  [对白 {ci+1}/{len(ch_entries)}] {ch_title}...", flush=True)

        try:
            resp, cost = await call_api_async(
                system=tmpl["system"],
                user=tmpl["user"].format(
                    chapter_text=ch_content,
                    scenes_list=scenes_list,
                    character_names=char_names,
                ),
                temperature=tmpl["temperature"],
                max_tokens=tmpl["max_tokens"],
            )
            cost_tracker.add(9, cost)
            dialogues = extract_json(resp)
            if not isinstance(dialogues, list):
                dialogues = [dialogues]
        except Exception as e:
            print(f"    ⚠ 对白提取跳过 {ch_title}: {e}")
            return []

        results = []
        for d in dialogues:
            dl_id = f"dl_{dialogue_counter[0]:04d}"
            dialogue_counter[0] += 1
            char_name = d.get("character", "")
            char_id = f"char_{safe_filename(char_name)}"

            dl_data = {
                "id": dl_id, "scene_id": d.get("scene_id", ""),
                "character_id": char_id,
                "line": d.get("line", ""),
                "subtext": d.get("subtext", ""),
                "emotion_intensity": d.get("emotion_intensity", 0),
                "order": d.get("order", dialogue_counter[0] - 1),
            }
            db.upsert_dialogue(PROJECT_ID, dl_data)
            results.append(dl_data)

        save_json(os.path.join("dialogue", f"{ch_id}_dialogue.json"), results)
        print(f"    ✓ {ch_title}: {len(results)} 句对白 ({cost['elapsed_s']:.1f}s)")
        return results

    tasks = [extract_dialogue_for_chapter(ci, ch) for ci, ch in enumerate(ch_entries)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, Exception):
            print(f"    ⚠ 任务失败: {r}")
        elif isinstance(r, list):
            all_dialogue.extend(r)

    save_index("dialogue", [{"id": d["id"], "scene_id": d["scene_id"],
                              "character_id": d["character_id"],
                              "line": d["line"][:50]}
                             for d in all_dialogue])

    summary_lines = [
        f"对白提取: {len(all_dialogue)} 句 (覆盖 {len(ch_entries)} 章节)",
        f"成本: {cost_tracker.stage_summary(9)}",
    ]
    return {"summary_lines": summary_lines}


async def stage10_visual_assess(db: PipelineDB) -> dict:
    """Stage 10 (可选): 全场景视觉评估。"""
    scene_files = list_entity_files("scenes")
    if not scene_files:
        return {"summary_lines": ["无场景数据"]}

    all_scenes_data = []
    for fname in scene_files:
        entity = load_entity_json("scenes", fname)
        all_scenes_data.append(entity["data"])

    tmpl_ready = TEMPLATES["PS04_VISUAL_READINESS"]
    ensure_dir("visual")

    batch_size = 6
    batches = [all_scenes_data[i:i+batch_size]
               for i in range(0, len(all_scenes_data), batch_size)]

    async def assess_batch(batch_idx, batch):
        print(f"  [评估批次 {batch_idx+1}/{len(batches)}] {len(batch)} 场景...", flush=True)
        try:
            resp, cost = await call_api_async(
                system=tmpl_ready["system"],
                user=tmpl_ready["user"].format(text=fmt_json(batch)),
                temperature=tmpl_ready["temperature"],
                max_tokens=tmpl_ready["max_tokens"],
            )
            cost_tracker.add(10, cost)
            readiness = extract_json(resp)
            print(f"    ✓ 批次 {batch_idx+1} ({cost['elapsed_s']:.1f}s)")
            return readiness
        except Exception as e:
            print(f"    ⚠ 评估批次 {batch_idx+1} 跳过: {e}")
            return None

    tasks = [assess_batch(i, batch) for i, batch in enumerate(batches)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    combined_readiness = {
        "overall_score": 0, "overall_assessment": "",
        "scenes": [], "recommendations": [],
        "batch_count": len(batches), "total_scenes": len(all_scenes_data),
    }

    scores = []
    for r in results:
        if isinstance(r, Exception):
            continue
        if r is None:
            continue
        if isinstance(r, dict):
            if "overall_score" in r:
                scores.append(r["overall_score"])
            combined_readiness["scenes"].extend(r.get("scenes", []))
            combined_readiness["recommendations"].extend(r.get("recommendations", []))

    if scores:
        combined_readiness["overall_score"] = round(sum(scores) / len(scores), 3)

    save_json(os.path.join("visual", "readiness.json"), combined_readiness)

    summary_lines = [
        f"视觉评估: 覆盖 {len(all_scenes_data)} 场景 ({len(batches)} 批次)",
        f"综合评分: {combined_readiness['overall_score']}",
        f"成本: {cost_tracker.stage_summary(10)}",
    ]
    return {"summary_lines": summary_lines}


# ══════════════════════════════════════════════════════════════════
#  多模型对比测试
# ══════════════════════════════════════════════════════════════════

async def run_multi_model_vff_test(db: PipelineDB, test_models: list[str],
                                    target_duration: str = "6s",
                                    target_model: str = "grok") -> dict:
    """挑选代表性场景，对多模型分别生成VFF，保存对比报告。"""
    scene_files = list_entity_files("scenes")
    if len(scene_files) < 3:
        return {"summary_lines": ["场景不足，跳过多模型测试"]}

    # 挑选5个代表性场景（高/中/低tension）
    scene_with_tension = []
    for fname in scene_files:
        entity = load_entity_json("scenes", fname)
        scene_with_tension.append({
            "fname": fname,
            "id": entity["_meta"]["id"],
            "tension": entity["data"].get("tension_score", 0.5),
        })

    scene_with_tension.sort(key=lambda x: x["tension"])
    n = len(scene_with_tension)
    sample_indices = [0, n//4, n//2, 3*n//4, n-1]
    sample_indices = list(dict.fromkeys(sample_indices))[:5]
    sample_scenes = [scene_with_tension[i] for i in sample_indices]

    print(f"  多模型VFF测试: {len(test_models)} 模型 x {len(sample_scenes)} 场景")

    # 加载所需数据
    sg_path = os.path.join(OUTPUT_DIR, "knowledge", "style_guide.json")
    style_guide = "{}"
    if os.path.exists(sg_path):
        with open(sg_path, "r", encoding="utf-8") as f:
            style_guide = f.read()

    char_files = list_entity_files("characters")
    char_profiles = {}
    for cfname in char_files:
        entity = load_entity_json("characters", cfname)
        name = entity["data"].get("name", "")
        char_profiles[name] = {
            "id": entity["_meta"]["id"],
            "name": name,
            "appearance": entity["data"].get("appearance", {}),
        }

    tmpl = TEMPLATES["P11_VFF_GENERATE"]
    comparison_results = {}

    for model_name in test_models:
        model_dir = ensure_dir("vff_prompts", model_name)
        comparison_results[model_name] = []

        for sample in sample_scenes:
            scene_entity = load_entity_json("scenes", sample["fname"])
            scene_id = sample["id"]
            scene_data = scene_entity["data"]

            shots_path = os.path.join(OUTPUT_DIR, "shots", f"{scene_id}_shots.json")
            if not os.path.exists(shots_path):
                continue
            with open(shots_path, "r", encoding="utf-8") as f:
                shots = json.load(f)

            present_chars = scene_data.get("characters_present", [])
            profiles_for_scene = {n: char_profiles[n]
                                  for n in present_chars if n in char_profiles}

            print(f"    [{model_name}] {scene_id} (tension={sample['tension']:.2f})...",
                  flush=True)

            try:
                resp, cost = await call_api_async(
                    system=tmpl["system"],
                    user=tmpl["user"].format(
                        scene_json=fmt_json(scene_data),
                        shots_json=fmt_json(shots),
                        character_profiles=fmt_json(profiles_for_scene),
                        style_guide=style_guide,
                        target_duration=target_duration,
                        target_model=target_model,
                        scene_id=scene_id,
                    ),
                    temperature=tmpl["temperature"],
                    max_tokens=tmpl["max_tokens"],
                    model_name=model_name,
                )
                cost_tracker.add(7, cost)

                vff_result = extract_json(resp)

                # 保存
                out_path = os.path.join(model_dir, f"{scene_id}_vff.json")
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(vff_result, f, ensure_ascii=False, indent=2)

                # 评估指标
                if isinstance(vff_result, list):
                    n_segments = len(vff_result)
                    has_refs = sum(1 for v in vff_result
                                  if v.get("character_refs") or v.get("scene_refs"))
                    has_body = sum(1 for v in vff_result if v.get("vff_body"))
                else:
                    n_segments = 1
                    has_refs = 1 if vff_result.get("character_refs") else 0
                    has_body = 1 if vff_result.get("vff_body") else 0

                comparison_results[model_name].append({
                    "scene_id": scene_id,
                    "tension": sample["tension"],
                    "n_segments": n_segments,
                    "format_compliance": has_body / max(n_segments, 1),
                    "ref_compliance": has_refs / max(n_segments, 1),
                    "cost": cost,
                })

                print(f"      ✓ {n_segments} segments ({cost['elapsed_s']:.1f}s)")

            except Exception as e:
                print(f"      ⚠ 失败: {e}")
                comparison_results[model_name].append({
                    "scene_id": scene_id, "error": str(e),
                })

    # 保存对比报告
    save_json("vff_model_comparison.json", comparison_results)

    summary_lines = [f"多模型VFF对比: {len(test_models)} 模型 x {len(sample_scenes)} 场景"]
    for model_name, results in comparison_results.items():
        successes = [r for r in results if "error" not in r]
        summary_lines.append(f"  {model_name}: {len(successes)}/{len(results)} 成功")

    return {"summary_lines": summary_lines}


# ══════════════════════════════════════════════════════════════════
#  Stage 11: 总结报告
# ══════════════════════════════════════════════════════════════════

def stage11_summary(db: PipelineDB) -> dict:
    """Stage 11: 总结报告。"""
    novel = read_novel()

    lines = []
    lines.append("=" * 70)
    lines.append("  第7轮测试报告 — Phase A/B/C 三阶段Pipeline + VFF")
    lines.append("  多模型适配 + 中文VFF视觉融合流")
    lines.append("=" * 70)
    lines.append(f"  小说: 《我和沈词的长子》 ({len(novel)} 字)")
    lines.append(f"  模型: {', '.join(get_available_models())}")
    lines.append("")

    # 数据库统计
    tables = ["chapters", "characters", "scenes", "beats", "knowledge",
              "shots", "character_states", "dialogue", "shot_prompts",
              "segments", "vff_prompts"]
    stats = {}
    for table in tables:
        try:
            stats[table] = db.table_count(table)
        except Exception:
            stats[table] = 0

    lines.append(f"  数据库统计 ({len(tables)}张表):")
    for table, count in stats.items():
        lines.append(f"    {table}: {count} 条")
    lines.append("")

    # 文件统计
    dirs = ["chapters", "characters", "scenes", "beats", "knowledge",
            "visual", "shots", "character_states", "dialogue",
            "shot_prompts", "segments", "vff_prompts"]
    for d in dirs:
        dirpath = os.path.join(OUTPUT_DIR, d)
        if os.path.isdir(dirpath):
            all_files = os.listdir(dirpath)
            lines.append(f"  {d}/: {len(all_files)} 文件")
        else:
            lines.append(f"  {d}/: 不存在")
    lines.append("")

    # 成本统计
    cost_summary = cost_tracker.total_summary()
    lines.append("  成本统计:")
    lines.append(f"    总API调用: {cost_summary['total_api_calls']} 次")
    lines.append(f"    总Token: {cost_summary['total_tokens']} "
                 f"({cost_summary['total_input_tokens']}in + "
                 f"{cost_summary['total_output_tokens']}out)")
    lines.append(f"    总API耗时: {cost_summary['total_api_elapsed_s']}s")
    lines.append("")

    # 每阶段成本
    stage_names = {
        1: "章节分割", 2: "摘要+扫描", 3: "角色详情+知识库",
        4: "场景+节拍", 5: "绑定", 6: "Shot拆分",
        7: "VFF生成", 8: "角色状态", 9: "对白提取",
        10: "视觉评估", 11: "总结报告",
    }
    lines.append("  各阶段成本:")
    for stage_num in range(1, 11):
        name = stage_names.get(stage_num, f"Stage {stage_num}")
        summary = cost_tracker.stage_summary(stage_num)
        lines.append(f"    Stage {stage_num:2d} ({name}): {summary}")
    lines.append("")

    # R6 vs R7 对比
    lines.append("  R6 vs R7 对比:")
    lines.append(f"    旧 Stage 9 (英文image prompt): 134次调用, ~1.07M tokens")
    lines.append(f"    新 Stage 7 (中文VFF): "
                 f"{cost_tracker.stages.get(7, {}).get('api_calls', 0)}次调用, "
                 f"{cost_tracker.stages.get(7, {}).get('input_tokens', 0) + cost_tracker.stages.get(7, {}).get('output_tokens', 0)}tokens")
    lines.append(f"    VFF segments: {stats.get('segments', 0)} 段")
    lines.append(f"    VFF prompts: {stats.get('vff_prompts', 0)} 条")
    lines.append("")

    lines.append("=" * 70)
    lines.append("  流水线执行完毕")
    lines.append("=" * 70)

    report = "\n".join(lines)
    save_text("00_测试总结.txt", report)
    save_json("cost_summary.json", cost_summary)
    print(f"\n{report}")

    return {"summary_lines": [
        f"总API调用: {cost_summary['total_api_calls']} 次",
        f"总Token: {cost_summary['total_tokens']}",
        f"数据库: {sum(stats.values())} 条记录",
    ]}


# ══════════════════════════════════════════════════════════════════
#  流水线控制
# ══════════════════════════════════════════════════════════════════

async def run_pipeline_async(mode: str = "terminal", clean: bool = False):
    """运行 Phase A/B/C 三阶段流水线。"""
    print("=" * 70)
    print("  第7轮测试 — Phase A/B/C 三阶段Pipeline + VFF视觉融合流")
    print(f"  模式: {mode} | 默认模型: {DEFAULT_MODEL}")
    print(f"  可用模型: {', '.join(get_available_models())}")
    print("=" * 70)
    print()

    if clean:
        if os.path.exists(OUTPUT_DIR):
            shutil.rmtree(OUTPUT_DIR)
            print("  [CLEAN] 已清空结果目录")
        print()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    state = load_state()
    save_state(state)

    db_path = os.path.join(OUTPUT_DIR, "knowledge_base.db")
    db = PipelineDB(db_path)
    db.upsert_project(PROJECT_ID, "我和沈词的长子", NOVEL_PATH)

    project_json_path = os.path.join(OUTPUT_DIR, "project.json")
    if not os.path.exists(project_json_path):
        save_json("project.json", {
            "id": PROJECT_ID,
            "name": "我和沈词的长子",
            "novel_path": NOVEL_PATH,
            "created_at": now_iso(),
            "default_model": DEFAULT_MODEL,
            "available_models": get_available_models(),
            "pipeline_version": "round7",
        })

    # 找到起始阶段
    start_stage = 1
    for sid in sorted(state["stages"].keys(), key=int):
        if state["stages"][sid].get("status") == "completed":
            start_stage = int(sid) + 1
        else:
            break

    # 恢复cost_tracker（跨session持久化）
    if "cost_tracker" in state:
        cost_tracker.restore_from_dict(state["cost_tracker"])
    if start_stage > TOTAL_STAGES:
        print("  所有阶段已完成! 生成总结报告...")
        stage11_summary(db)
        db.close()
        return

    completed_stages = [s for s in state["stages"]
                        if state["stages"][s].get("status") == "completed"]
    if completed_stages:
        print(f"  已完成阶段: {', '.join(sorted(completed_stages, key=int))}")
    print(f"  从 Stage {start_stage} 开始执行")
    print()

    pipeline_start = time.time()

    # ── Phase A: 必须阶段 (Stage 1-7) ────────────────────────────

    PHASE_A_STAGES = [
        (1, "Stage 1: 章节分割", stage1_chapter_split, False),
        (2, "Stage 2: 摘要+角色扫描", stage2_summary_and_scan, True),
        (3, "Stage 3: 角色详情+知识库", stage3_character_detail_and_knowledge, True),
        (4, "Stage 4: 场景+节拍提取", stage4_scene_and_beat, True),
        (5, "Stage 5: 节拍↔场景绑定", stage5_beat_scene_bind, True),
        (6, "Stage 6: Scene→Shot拆分", stage6_scene_to_shot, True),
        (7, "Stage 7: VFF视觉融合流生成", None, True),  # 特殊处理
    ]

    for stage_num, stage_name, stage_func, is_async in PHASE_A_STAGES:
        if stage_num < start_stage:
            continue
        if stage_num > 7:
            break

        if stage_num > start_stage:
            await asyncio.sleep(STEP_COOLDOWN)

        print()
        print("─" * 60)
        print(f"  [Phase A {stage_num}/7] {stage_name}")
        print("─" * 60)

        mark_stage(state, stage_num, "running")

        try:
            if stage_num == 7:
                # Stage 7 VFF 使用默认配置
                result = await stage7_vff_generate(db)
            elif is_async:
                result = await stage_func(db)
            else:
                result = stage_func(db)
        except KeyboardInterrupt:
            print(f"\n\n  [中断] 用户中断流水线")
            db.close()
            sys.exit(130)
        except Exception as e:
            print(f"\n  [FAIL] {stage_name}: {e}")
            traceback.print_exc()
            db.close()
            sys.exit(1)

        mark_stage(state, stage_num, "completed")

        # Phase A 内部不需要逐步确认 — 自动连续运行
        for line in result.get("summary_lines", []):
            print(f"  {line}")

    # ── Phase B: 确认 + 选择可选阶段 ──────────────────────────────

    # 需要进入Phase B的条件:
    # 1. Phase A刚完成 (start_stage <= 7)
    # 2. 从Stage 8+恢复，但Phase B结果为stop或未配置，且有pending的可选阶段
    need_phase_b = start_stage <= 7
    if not need_phase_b and start_stage > 7:
        prev_action = state.get("phase_b_config", {}).get("action", "")
        has_pending = any(
            state["stages"][str(s)].get("status") == "pending"
            for s in [8, 9, 10]
        )
        if has_pending and prev_action in ("stop", ""):
            need_phase_b = True

    if need_phase_b:
        print()
        print("=" * 60)
        print("  Phase A 完成 — 进入 Phase B 确认")
        print("=" * 60)

        state["phase"] = "B"
        save_state(state)

        phase_a_summary = [
            f"章节: {db.table_count('chapters')} | 角色: {db.table_count('characters')}",
            f"场景: {db.table_count('scenes')} | 节拍: {db.table_count('beats')}",
            f"镜头: {db.table_count('shots')} | VFF段: {db.table_count('vff_prompts')}",
            f"总API调用: {cost_tracker.total_api_calls}",
            f"总Token: {cost_tracker.total_input_tokens + cost_tracker.total_output_tokens}",
            f"Phase A 耗时: {time.time() - pipeline_start:.0f}s "
            f"({(time.time() - pipeline_start)/60:.1f}min)",
        ]

        phase_b_data = {
            "stats": {
                "章节数": db.table_count("chapters"),
                "角色数": db.table_count("characters"),
                "场景数": db.table_count("scenes"),
                "节拍数": db.table_count("beats"),
                "镜头数": db.table_count("shots"),
                "VFF段": db.table_count("vff_prompts"),
            },
            "cost": {
                "api_calls": cost_tracker.total_api_calls,
                "tokens": cost_tracker.total_input_tokens + cost_tracker.total_output_tokens,
                "elapsed": f"{time.time() - pipeline_start:.0f}",
            },
        }

        phase_b_result = await confirm_phase_b_async(mode, phase_a_summary, phase_b_data)

        action = phase_b_result.get("action", "stop")
        state["phase_b_config"] = phase_b_result
        save_state(state)

        if action == "stop":
            print("  [STOP] 用户停止流水线")
            db.close()
            return
        elif action == "skip_to_report":
            print("  [SKIP] 跳过可选阶段，直接生成报告")
            mark_stage(state, 8, "completed")
            mark_stage(state, 9, "completed")
            mark_stage(state, 10, "completed")
        elif action == "run_selected":
            selected_stages = phase_b_result.get("selected_stages", [])
            config = phase_b_result.get("config", {})
            print(f"  选中阶段: {selected_stages}")
            print(f"  配置: {config}")

            # ── Phase C: 执行选中的可选阶段 ───────────────────────

            state["phase"] = "C"
            save_state(state)

            optional_stage_defs = {
                8: ("Stage 8: 角色状态追踪", stage8_character_state),
                9: ("Stage 9: 对白提取", stage9_dialogue_extract),
                10: ("Stage 10: 视觉评估", stage10_visual_assess),
            }

            for stage_num in sorted(selected_stages):
                if stage_num not in optional_stage_defs:
                    continue
                if state["stages"][str(stage_num)].get("status") == "completed":
                    continue

                stage_name, stage_func = optional_stage_defs[stage_num]

                print()
                print("─" * 60)
                print(f"  [Phase C] {stage_name}")
                print("─" * 60)

                mark_stage(state, stage_num, "running")

                try:
                    result = await stage_func(db)
                except Exception as e:
                    print(f"  [FAIL] {stage_name}: {e}")
                    traceback.print_exc()
                    continue

                mark_stage(state, stage_num, "completed")
                for line in result.get("summary_lines", []):
                    print(f"  {line}")

            # 多模型对比测试
            test_models = config.get("test_models", [])
            if len(test_models) > 1:
                print()
                print("─" * 60)
                print(f"  [Phase C] 多模型VFF对比测试")
                print("─" * 60)

                try:
                    result = await run_multi_model_vff_test(
                        db,
                        test_models=test_models,
                        target_duration=config.get("target_duration", "6s"),
                        target_model=config.get("target_model", "grok"),
                    )
                    for line in result.get("summary_lines", []):
                        print(f"  {line}")
                except Exception as e:
                    print(f"  [FAIL] 多模型测试: {e}")
                    traceback.print_exc()

            # 标记未选中的阶段为跳过
            for sn in (8, 9, 10):
                if sn not in selected_stages:
                    if state["stages"][str(sn)].get("status") != "completed":
                        state["stages"][str(sn)]["status"] = "skipped"
            save_state(state)

    # ── Stage 11: 总结报告 ─────────────────────────────────────────

    print()
    print("=" * 60)
    print("  Stage 11: 总结报告")
    print("=" * 60)

    mark_stage(state, 11, "running")
    stage11_summary(db)
    mark_stage(state, 11, "completed")

    pipeline_elapsed = time.time() - pipeline_start
    print()
    print("=" * 70)
    print(f"  流水线完成! 总耗时: {pipeline_elapsed:.1f}s ({pipeline_elapsed/60:.1f}min)")
    print("=" * 70)

    db.close()


# ── 主入口 ────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="第7轮测试 — Phase A/B/C 三阶段Pipeline + VFF"
    )
    parser.add_argument("--mode", choices=["terminal", "web"], default="terminal",
                        help="确认模式: terminal (默认) 或 web")
    parser.add_argument("--clean", action="store_true",
                        help="清空结果目录，从头重跑")
    args = parser.parse_args()

    asyncio.run(run_pipeline_async(mode=args.mode, clean=args.clean))


if __name__ == "__main__":
    main()
