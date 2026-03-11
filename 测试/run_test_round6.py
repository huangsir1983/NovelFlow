"""第6轮测试 — 11阶段异步并行流水线（知识层+生产层）.

用法:
  python run_test_round6.py            # 终端模式，自动从断点续跑
  python run_test_round6.py --mode web # Web 确认模式
  python run_test_round6.py --clean    # 清空重跑

特性:
  - 11 阶段（知识层5+生产层5+报告1），阶段间串行/阶段内并行
  - httpx.AsyncClient + asyncio.Semaphore(5) 并发控制
  - 成本追踪（token消耗+耗时）
  - 关键Bug修复：场景提取用原文、Beat↔Scene绑定、全场景视觉评估
  - 统一 dramatic_intensity（-1到1）评分体系
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
API_BASE = "https://www.openclaudecode.cn/v1/responses"
API_KEY = "sk-S2HdTVByFCfJcZ3oM3BUBQio0CGtty7xA2aTHdCP9occt50e"
MODEL = "gpt-5.4"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NOVEL_PATH = os.path.join(SCRIPT_DIR, "我和沈词的长子.txt")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "第6次测试结果")
TIMEOUT = 500
PROJECT_ID = "novel_shenCi_v6"

MAX_RETRIES = 3
RETRY_WAIT_BASE = 10
RATE_LIMIT_WAIT = 30
STEP_COOLDOWN = 2
MAX_CONCURRENT = 5  # Semaphore 并发上限

# 小章节阈值（低于此字数标记异常）
MIN_CHAPTER_WORDS = 50

sys.stdout.reconfigure(encoding="utf-8")

# prompt 模板
sys.path.insert(0, os.path.join(SCRIPT_DIR, "..", "backend"))
from services.prompt_templates import TEMPLATES

# 本地模块
from pipeline_db import PipelineDB
from confirm_server import ConfirmServer


# ── 基础工具 ──────────────────────────────────────────────────────

def read_novel() -> str:
    with open(NOVEL_PATH, "rb") as f:
        return f.read().decode("gb18030")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def fmt_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


# ── 异步 API 调用 ────────────────────────────────────────────────

_semaphore = asyncio.Semaphore(MAX_CONCURRENT)


def is_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.ReadTimeout):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (502, 524, 503, 504)
    return False


def is_rate_limited(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429
    return False


async def call_api_async(system: str, user: str, temperature: float = 0.7,
                         max_tokens: int = 4096) -> tuple[str, dict]:
    """异步调用API，返回 (text, cost_meta)。"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": MODEL,
        "input": [{"role": "user", "content": user}],
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }
    if system:
        body["instructions"] = system

    last_exc = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with _semaphore:
                t0 = time.time()
                async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
                    resp = await client.post(API_BASE, json=body, headers=headers)
                    resp.raise_for_status()
                elapsed = time.time() - t0

            data = resp.json()
            output = data.get("output", [])
            text = ""
            if output:
                content = output[0].get("content", [])
                if content:
                    text = content[0].get("text", "")

            # 提取 usage 信息
            usage = data.get("usage", {})
            cost_meta = {
                "model": MODEL,
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "elapsed_s": round(elapsed, 2),
            }
            return text, cost_meta

        except Exception as e:
            last_exc = e
            if is_rate_limited(e):
                print(f"\n    ⚠ 429限流，等待 {RATE_LIMIT_WAIT}s...", flush=True)
                await asyncio.sleep(RATE_LIMIT_WAIT)
                continue
            if is_retryable(e) and attempt < MAX_RETRIES:
                wait = RETRY_WAIT_BASE * (attempt + 1)
                code = getattr(getattr(e, 'response', None), 'status_code', type(e).__name__)
                print(f"\n    ⚠ {code}，重试 {attempt+1}/{MAX_RETRIES}，等待 {wait}s...", flush=True)
                await asyncio.sleep(wait)
                continue
            raise
    raise last_exc


def call_api_sync(system: str, user: str, temperature: float = 0.7,
                  max_tokens: int = 4096) -> tuple[str, dict]:
    """同步调用API（用于Stage 1等单次调用场景）。"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": MODEL,
        "input": [{"role": "user", "content": user}],
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }
    if system:
        body["instructions"] = system

    last_exc = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            t0 = time.time()
            with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
                resp = client.post(API_BASE, json=body, headers=headers)
                resp.raise_for_status()
            elapsed = time.time() - t0

            data = resp.json()
            output = data.get("output", [])
            text = ""
            if output:
                content = output[0].get("content", [])
                if content:
                    text = content[0].get("text", "")

            usage = data.get("usage", {})
            cost_meta = {
                "model": MODEL,
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "elapsed_s": round(elapsed, 2),
            }
            return text, cost_meta

        except Exception as e:
            last_exc = e
            if is_rate_limited(e):
                print(f"\n    ⚠ 429限流，等待 {RATE_LIMIT_WAIT}s...", flush=True)
                time.sleep(RATE_LIMIT_WAIT)
                continue
            if is_retryable(e) and attempt < MAX_RETRIES:
                wait = RETRY_WAIT_BASE * (attempt + 1)
                code = getattr(getattr(e, 'response', None), 'status_code', type(e).__name__)
                print(f"\n    ⚠ {code}，重试 {attempt+1}/{MAX_RETRIES}，等待 {wait}s...", flush=True)
                time.sleep(wait)
                continue
            raise
    raise last_exc


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


# ── 文件名安全化 ──────────────────────────────────────────────────

def safe_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\s]+', '_', name)
    return name.strip('_') or 'unnamed'


# ── 流水线状态 ────────────────────────────────────────────────────

STATE_FILE = os.path.join(OUTPUT_DIR, "pipeline_state.json")
TOTAL_STAGES = 11


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "project": "我和沈词的长子",
        "started_at": now_iso(),
        "current_stage": 1,
        "stages": {str(i): {"status": "pending"} for i in range(1, TOTAL_STAGES + 1)},
    }


def save_state(state: dict):
    filepath = os.path.join(OUTPUT_DIR, "pipeline_state.json")
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


_web_server = None


def confirm_web(stage_name: str, stage_number: int, stage_data: dict) -> str:
    global _web_server
    if _web_server is None:
        _web_server = ConfirmServer(port=5678)
    return _web_server.wait_for_confirm(stage_name, stage_number, stage_data)


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
    """异步版确认（桥接同步confirm到异步上下文）。"""
    return await asyncio.to_thread(
        confirm_stage, mode, stage_name, stage_number, summary_lines, stage_data
    )


# ══════════════════════════════════════════════════════════════════
#  知识层 Stage 1-5
# ══════════════════════════════════════════════════════════════════

def stage1_chapter_split(db: PipelineDB) -> dict:
    """Stage 1: 章节分割与存储。"""
    novel = read_novel()
    tmpl = TEMPLATES["P01_CHAPTER_SPLIT"]

    print(f"  小说长度: {len(novel)} 字")
    print(f"  调用 P01_CHAPTER_SPLIT...")

    resp, cost = call_api_sync(
        system=tmpl["system"],
        user=tmpl["user"].format(text=novel),
        temperature=tmpl["temperature"],
        max_tokens=tmpl["max_tokens"],
    )
    cost_tracker.add(1, cost)
    markers = extract_json(resp)

    print(f"  API 返回 {len(markers)} 个章节标记 ({cost['elapsed_s']:.1f}s)")
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

        # 小章节检测
        if word_count < MIN_CHAPTER_WORDS:
            skipped.append({"id": ch_id, "title": title, "word_count": word_count})
            print(f"    ⚠ 跳过小章节: {ch_id} {title} ({word_count}字)")
            continue

        filename = f"{ch_id}_{safe_filename(title)}.json"

        meta = {
            "id": ch_id,
            "type": "chapter",
            "pipeline_step": "chapter_split",
            "created_at": now_iso(),
        }
        hooks = {
            "ready_for": ["summary", "scene_extract", "beat_extract", "character_scan"],
            "canvas_node_type": "input_chapter",
            "downstream": {"scenes": [], "beats": [], "characters_mentioned": []},
        }
        data = {
            "title": title,
            "order": i,
            "content": content,
            "word_count": word_count,
            "start_marker": start,
            "end_marker": end,
            "summary": "",
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

    web_data = {
        "stats": {"章节数": len(index_entries), "跳过": len(skipped),
                  "总字数": sum(e["word_count"] for e in index_entries)},
        "items_title": "章节列表",
        "items": [
            {"idx": e["order"]+1, "name": e["title"], "desc": f"{e['word_count']}字"}
            for e in index_entries
        ],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


async def stage2_summary_and_scan(db: PipelineDB) -> dict:
    """Stage 2: 章节摘要 + 角色扫描（并行）。"""
    ch_files = list_entity_files("chapters")
    print(f"  共 {len(ch_files)} 个章节待摘要 + 1次角色扫描")

    tmpl_summary = TEMPLATES["P01B_CHAPTER_SUMMARY"]
    tmpl_scan = TEMPLATES["P03A_CHARACTER_SCAN"]

    # 定义摘要任务
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

        # 更新章节 JSON
        entity["data"]["summary"] = summary
        filepath = os.path.join(OUTPUT_DIR, "chapters", fname)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(entity, f, ensure_ascii=False, indent=2)

        db.update_chapter_summary(ch_id, summary)
        print(f"    ✓ {title} ({cost['elapsed_s']:.1f}s)")
        return {"ch_id": ch_id, "title": title, "summary": summary}

    # 定义角色扫描任务（需要先有 synopsis，但我们可以先跑摘要再跑扫描）
    # 改为：先并行跑所有摘要，得到 synopsis 后再跑扫描
    summary_tasks = [summarize_chapter(fname, i) for i, fname in enumerate(ch_files)]
    summaries = await asyncio.gather(*summary_tasks)

    # 拼接 synopsis
    synopsis = "\n\n".join(f"【{s['title']}】\n{s['summary']}" for s in summaries)
    ensure_dir("knowledge")
    save_text(os.path.join("knowledge", "synopsis.txt"), synopsis)

    # 角色扫描
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

    # 保存角色名单
    save_json(os.path.join("characters", "_scan.json"), char_list)

    summary_lines = [
        f"摘要: {len(summaries)} 章, synopsis {len(synopsis)} 字",
        f"角色扫描: {len(char_list)} 个角色",
        f"成本: {cost_tracker.stage_summary(2)}",
    ]

    web_data = {
        "stats": {"摘要数": len(summaries), "角色数": len(char_list),
                  "synopsis字数": len(synopsis)},
        "items_title": "章节摘要 + 角色名单",
        "items": [
            {"idx": i+1, "name": s["title"],
             "desc": s["summary"][:80] + ("..." if len(s["summary"]) > 80 else "")}
            for i, s in enumerate(summaries)
        ] + [
            {"idx": "角色", "name": c.get("name", "?"),
             "tag": c.get("role", ""),
             "desc": c.get("brief", "")}
            for c in char_list
        ],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


async def stage3_character_detail_and_knowledge(db: PipelineDB) -> dict:
    """Stage 3: 角色详情 + 知识库构建（并行）。"""
    # 读取角色名单和 synopsis
    char_list = json.load(open(os.path.join(OUTPUT_DIR, "characters", "_scan.json"), "r", encoding="utf-8"))
    synopsis_path = os.path.join(OUTPUT_DIR, "knowledge", "synopsis.txt")
    with open(synopsis_path, "r", encoding="utf-8") as f:
        synopsis = f.read()

    main_chars = [c for c in char_list if c.get("role") in ("protagonist", "antagonist", "supporting")]
    all_names = [c.get("name", "?") for c in char_list]

    tmpl_detail = TEMPLATES["P03B_CHARACTER_DETAIL"]

    print(f"  主要角色 {len(main_chars)} 个 + 知识库构建 1次")

    # 角色详情任务
    async def detail_character(ch, idx):
        name = ch.get("name", "?")
        brief = ch.get("brief", ch.get("description", ""))
        other_names = [n for n in all_names if n != name]

        print(f"  [{idx+1}/{len(main_chars)}] 角色详情: {name}...", flush=True)

        resp, cost = await call_api_async(
            system=tmpl_detail["system"],
            user=tmpl_detail["user"].format(
                character_name=name,
                character_brief=brief,
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
            "id": char_id,
            "type": "character",
            "pipeline_step": "character_detail",
            "created_at": now_iso(),
        }
        hooks = {
            "ready_for": ["visual_prompt", "arc_analysis", "casting"],
            "canvas_node_type": "character_profile",
            "appears_in_chapters": [],
            "appears_in_scenes": [],
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

    # 知识库构建任务
    async def build_knowledge():
        # 读取场景地点（如有）
        loc_names = "未知"
        scene_index_path = os.path.join(OUTPUT_DIR, "scenes", "_index.json")
        if os.path.exists(scene_index_path):
            with open(scene_index_path, "r", encoding="utf-8") as f:
                scene_index = json.load(f)
            locs = list(set(e.get("location", "") for e in scene_index["entries"] if e.get("location")))
            if locs:
                loc_names = ", ".join(locs[:10])

        char_names = ", ".join(all_names[:10])
        tmpl = TEMPLATES["P05_KNOWLEDGE_BASE_V2"]
        print(f"  知识库构建...", flush=True)

        resp, cost = await call_api_async(
            system=tmpl["system"],
            user=tmpl["user"].format(
                synopsis=synopsis,
                character_names=char_names,
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

    # 并行执行
    detail_tasks = [detail_character(ch, i) for i, ch in enumerate(main_chars)]
    all_tasks = detail_tasks + [build_knowledge()]
    results = await asyncio.gather(*all_tasks, return_exceptions=True)

    # 分离结果
    char_results = []
    kb_result = None
    for r in results:
        if isinstance(r, Exception):
            print(f"    ⚠ 任务失败: {r}")
            traceback.print_exc()
            continue
        if isinstance(r, dict) and "world_building" in r:
            kb_result = r
        elif isinstance(r, dict) and "name" in r:
            char_results.append(r)

    # minor 角色加入索引
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
        f"知识库: {'完成' if kb_result else '失败'}",
        f"成本: {cost_tracker.stage_summary(3)}",
    ]

    web_data = {
        "stats": {"主要角色": len(char_results), "总角色数": len(index_entries)},
        "items_title": "角色详情",
        "items": [
            {"idx": i+1, "name": e["name"], "tag": e["role"],
             "desc": e.get("description", "")}
            for i, e in enumerate(index_entries)
        ],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


async def stage4_scene_and_beat(db: PipelineDB) -> dict:
    """Stage 4: 场景提取(原文) + 节拍提取（并行）。
    关键修复：场景提取改用原文content，而非summary。
    """
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

    scene_order_counter = [0]  # 用列表实现可变闭包
    all_scenes_entries = []
    scene_lock = asyncio.Lock()

    # 场景提取任务（使用原文 content，不是 summary！）
    async def extract_scenes_for_chapter(ci, ch_entry):
        ch_id = ch_entry["id"]
        ch_title = ch_entry["title"]

        ch_entity = load_entity_json("chapters", ch_entry["filename"])
        # 关键修复：使用原文 content 而非 summary
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

                meta = {
                    "id": scene_id, "type": "scene",
                    "pipeline_step": "scene_extract", "created_at": now_iso(),
                }
                hooks = {
                    "ready_for": ["shot_design", "visual_readiness", "storyboard", "image_prompt"],
                    "canvas_node_type": "scene",
                    "source_chapter": ch_id,
                    "characters_present": s.get("characters_present", []),
                }
                # 统一评分：dramatic_intensity = tension_score * 2 - 1
                tension = s.get("tension_score", 0.5)
                dramatic_intensity = round(tension * 2 - 1, 3)

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

        # 回写章节 hooks
        update_entity_hooks("chapters", ch_entry["filename"], {
            "downstream": {
                "scenes": [r["id"] for r in results],
                "beats": ch_entity["_hooks"].get("downstream", {}).get("beats", []),
                "characters_mentioned": ch_entity["_hooks"].get("downstream", {}).get("characters_mentioned", []),
            }
        })

        print(f"    ✓ {ch_title}: {len(results)} 场景 ({cost['elapsed_s']:.1f}s)")
        return results

    # 节拍提取任务
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

            # 统一评分：dramatic_intensity = emotional_value
            emotional_value = b.get("emotional_value", 0)

            meta = {
                "id": beat_id, "type": "beat",
                "pipeline_step": "beat_extract", "created_at": now_iso(),
            }
            hooks = {
                "ready_for": ["rhythm_analysis", "arc_mapping", "pacing_check"],
                "canvas_node_type": "beat",
                "related_scenes": [],
            }
            data = {
                "title": b.get("title", b.get("beat_name", f"Beat {i+1}")),
                "description": b.get("description", ""),
                "beat_type": b.get("beat_type", b.get("type", "event")),
                "save_the_cat": b.get("save_the_cat", b.get("stc_type", "")),
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
                "emotional_value": emotional_value,
                "dramatic_intensity": emotional_value,
                "order": i,
            })

        save_index("beats", index_entries)
        print(f"    ✓ {len(beats)} 个节拍 ({cost['elapsed_s']:.1f}s)")
        return index_entries

    # 并行执行
    ensure_dir("scenes")
    scene_tasks = [extract_scenes_for_chapter(ci, ch) for ci, ch in enumerate(ch_entries)]
    all_tasks = scene_tasks + [extract_beats()]
    results = await asyncio.gather(*all_tasks, return_exceptions=True)

    # 分离结果
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
        f"场景提取: {len(all_scenes_entries)} 个（使用原文content）",
        f"节拍提取: {len(beat_entries)} 个",
        f"成本: {cost_tracker.stage_summary(4)}",
    ]

    web_data = {
        "stats": {"场景数": len(all_scenes_entries), "节拍数": len(beat_entries)},
        "items_title": "场景列表",
        "items": [
            {"idx": e["order"]+1, "name": e.get("heading", e["id"]),
             "tag": e.get("location", ""),
             "desc": f"张力: {e.get('tension_score', 0):.2f}"}
            for e in all_scenes_entries[:30]
        ],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


async def stage5_beat_scene_bind(db: PipelineDB) -> dict:
    """Stage 5: 节拍↔场景绑定。"""
    # 加载 beats 和 scenes
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

    # 更新 beat 和 scene 的 hooks
    for b in binding_list:
        beat_id = b.get("beat_id", "")
        scene_ids = b.get("scene_ids", [])

        # 更新 beat 的 related_scenes
        for fname in beat_files:
            entity = load_entity_json("beats", fname)
            if entity["_meta"]["id"] == beat_id:
                update_entity_hooks("beats", fname, {"related_scenes": scene_ids})
                db.update_beat_intensity(
                    beat_id,
                    entity["data"].get("dramatic_intensity", entity["data"].get("emotional_value", 0)),
                    related_scenes=scene_ids,
                )
                break

        # 更新 scene 的 related_beats
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

    # 保存绑定结果
    save_json("beat_scene_bindings.json", bindings)

    summary_lines = [
        f"绑定关系: {len(binding_list)} 条",
        f"孤立场景: {len(unbound_scenes)} 个",
        f"孤立节拍: {len(unbound_beats)} 个",
        f"成本: {cost_tracker.stage_summary(5)}",
    ]

    web_data = {
        "stats": {"绑定数": len(binding_list),
                  "孤立场景": len(unbound_scenes),
                  "孤立节拍": len(unbound_beats)},
        "items_title": "绑定关系",
        "items": [
            {"idx": i+1, "name": b.get("beat_title", b.get("beat_id", "")),
             "tag": f"{len(b.get('scene_ids', []))}场景",
             "desc": b.get("binding_reason", "")}
            for i, b in enumerate(binding_list[:20])
        ],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


# ══════════════════════════════════════════════════════════════════
#  生产层 Stage 6-10
# ══════════════════════════════════════════════════════════════════

async def stage6_scene_to_shot(db: PipelineDB) -> dict:
    """Stage 6: Scene→Shot拆分（每场景并行）。"""
    scene_files = list_entity_files("scenes")
    if not scene_files:
        return {"summary_lines": ["无场景数据"], "web_data": {"cards": [{"value": "无场景数据"}]}}

    # 读取 style_guide 和角色档案
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

        # 获取在场角色的档案
        present_chars = scene_data.get("characters_present", [])
        profiles_for_scene = {n: char_profiles[n] for n in present_chars if n in char_profiles}

        print(f"  [Shot {idx+1}/{len(scene_files)}] {scene_id}: {scene_data.get('heading', '')}...", flush=True)

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
                "id": shot_id,
                "scene_id": scene_id,
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

        # 保存该场景的所有shot到文件
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

    save_index("shots", [{"id": s["id"], "scene_id": s["scene_id"],
                           "framing": s["framing"], "goal": s["goal"][:50]}
                          for s in all_shots])

    summary_lines = [
        f"Shot拆分: {len(all_shots)} 个镜头 (覆盖 {len(scene_files)} 场景)",
        f"成本: {cost_tracker.stage_summary(6)}",
    ]

    web_data = {
        "stats": {"镜头数": len(all_shots), "覆盖场景": len(scene_files)},
        "items_title": "镜头概览",
        "items": [
            {"idx": i+1, "name": s["id"], "tag": s.get("framing", ""),
             "desc": s.get("goal", "")[:60]}
            for i, s in enumerate(all_shots[:30])
        ],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


async def stage7_character_state(db: PipelineDB) -> dict:
    """Stage 7: 角色状态追踪（每场景并行）。"""
    scene_files = list_entity_files("scenes")
    if not scene_files:
        return {"summary_lines": ["无场景数据"], "web_data": {"cards": [{"value": "无场景数据"}]}}

    # 加载角色档案
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

    # 按场景顺序串行处理（因为需要前一场景的状态），但使用异步API
    previous_states_map = {}  # scene_id -> states

    for idx, fname in enumerate(scene_files):
        entity = load_entity_json("scenes", fname)
        scene_id = entity["_meta"]["id"]
        scene_data = entity["data"]

        present_chars = scene_data.get("characters_present", [])
        profiles_for_scene = {n: char_profiles[n] for n in present_chars if n in char_profiles}

        # 获取前一场景的状态
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
                    previous_states=fmt_json(prev_states) if isinstance(prev_states, (dict, list)) else prev_states,
                ),
                temperature=tmpl["temperature"],
                max_tokens=tmpl["max_tokens"],
            )
            cost_tracker.add(7, cost)

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
                "id": cs_id,
                "character_id": char_id,
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
        f"成本: {cost_tracker.stage_summary(7)}",
    ]

    web_data = {
        "stats": {"状态记录数": len(all_states), "覆盖场景": len(scene_files)},
        "cards": [{"label": "角色状态追踪", "value": f"{len(all_states)} 条记录"}],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


async def stage8_dialogue_extract(db: PipelineDB) -> dict:
    """Stage 8: 对白提取（每章节并行）。"""
    ch_index_path = os.path.join(OUTPUT_DIR, "chapters", "_index.json")
    with open(ch_index_path, "r", encoding="utf-8") as f:
        ch_index = json.load(f)
    ch_entries = ch_index["entries"]

    # 读取场景索引
    scene_index_path = os.path.join(OUTPUT_DIR, "scenes", "_index.json")
    with open(scene_index_path, "r", encoding="utf-8") as f:
        scene_index = json.load(f)
    scene_entries = scene_index["entries"]

    # 读取角色名单
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

        # 找到该章节的场景
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
            cost_tracker.add(8, cost)

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
                "id": dl_id,
                "scene_id": d.get("scene_id", ""),
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
        f"成本: {cost_tracker.stage_summary(8)}",
    ]

    web_data = {
        "stats": {"对白数": len(all_dialogue), "覆盖章节": len(ch_entries)},
        "items_title": "对白样本",
        "items": [
            {"idx": i+1, "name": d.get("character_id", ""),
             "desc": d.get("line", "")[:80]}
            for i, d in enumerate(all_dialogue[:20])
        ],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


async def stage9_visual_prompt(db: PipelineDB) -> dict:
    """Stage 9: 视觉Prompt生成（分批并行）。"""
    # 加载所有 shot
    shot_files = list_entity_files("shots")
    if not shot_files:
        return {"summary_lines": ["无镜头数据"], "web_data": {"cards": [{"value": "无镜头数据"}]}}

    all_shots = []
    for fname in shot_files:
        shots = json.load(open(os.path.join(OUTPUT_DIR, "shots", fname), "r", encoding="utf-8"))
        if isinstance(shots, list):
            all_shots.extend(shots)
        else:
            all_shots.append(shots)

    # 加载角色档案
    char_files = list_entity_files("characters")
    char_profiles = {}
    for cfname in char_files:
        entity = load_entity_json("characters", cfname)
        name = entity["data"].get("name", "")
        char_profiles[name] = {
            "name": name,
            "appearance": entity["data"].get("appearance", {}),
            "visual_reference": entity["data"].get("visual_reference", ""),
        }

    # 加载 style_guide
    sg_path = os.path.join(OUTPUT_DIR, "knowledge", "style_guide.json")
    style_guide = "{}"
    if os.path.exists(sg_path):
        with open(sg_path, "r", encoding="utf-8") as f:
            style_guide = f.read()

    tmpl = TEMPLATES["P11_VISUAL_PROMPT"]
    ensure_dir("shot_prompts")

    # 分批：每批约6个shot
    batch_size = 6
    batches = [all_shots[i:i+batch_size] for i in range(0, len(all_shots), batch_size)]
    all_prompts = []
    prompt_counter = [0]

    async def process_batch(batch_idx, batch):
        print(f"  [Prompt批次 {batch_idx+1}/{len(batches)}] {len(batch)} 镜头...", flush=True)

        try:
            resp, cost = await call_api_async(
                system=tmpl["system"],
                user=tmpl["user"].format(
                    shot_cards=fmt_json(batch),
                    character_profiles=fmt_json(char_profiles),
                    style_guide=style_guide,
                ),
                temperature=tmpl["temperature"],
                max_tokens=tmpl["max_tokens"],
            )
            cost_tracker.add(9, cost)

            prompts = extract_json(resp)
            if not isinstance(prompts, list):
                prompts = [prompts]
        except Exception as e:
            print(f"    ⚠ Prompt生成批次 {batch_idx+1} 跳过: {e}")
            return []

        results = []
        for p in prompts:
            sp_id = f"sp_{prompt_counter[0]:04d}"
            prompt_counter[0] += 1

            sp_data = {
                "id": sp_id,
                "shot_id": p.get("shot_id", ""),
                "prompt_text": p.get("prompt_text", ""),
                "style_params": p.get("style_params", {}),
                "negative_prompt": p.get("negative_prompt", ""),
            }

            db.upsert_shot_prompt(PROJECT_ID, sp_data)
            results.append(sp_data)

        save_json(os.path.join("shot_prompts", f"batch_{batch_idx:03d}.json"), results)
        print(f"    ✓ 批次 {batch_idx+1}: {len(results)} prompts ({cost['elapsed_s']:.1f}s)")
        return results

    tasks = [process_batch(i, batch) for i, batch in enumerate(batches)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, Exception):
            print(f"    ⚠ 任务失败: {r}")
        elif isinstance(r, list):
            all_prompts.extend(r)

    save_index("shot_prompts", [{"id": p["id"], "shot_id": p["shot_id"],
                                  "prompt_text": p["prompt_text"][:80]}
                                 for p in all_prompts])

    summary_lines = [
        f"视觉Prompt: {len(all_prompts)} 个 ({len(batches)} 批次)",
        f"成本: {cost_tracker.stage_summary(9)}",
    ]

    web_data = {
        "stats": {"Prompt数": len(all_prompts), "批次": len(batches)},
        "items_title": "Prompt样本",
        "items": [
            {"idx": i+1, "name": p["shot_id"],
             "desc": p["prompt_text"][:100]}
            for i, p in enumerate(all_prompts[:10])
        ],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


async def stage10_visual_assess(db: PipelineDB) -> dict:
    """Stage 10: 全场景视觉评估（分批处理全部场景）。"""
    scene_files = list_entity_files("scenes")
    if not scene_files:
        return {"summary_lines": ["无场景数据"], "web_data": {"cards": [{"value": "无场景数据"}]}}

    # 加载所有场景
    all_scenes_data = []
    for fname in scene_files:
        entity = load_entity_json("scenes", fname)
        all_scenes_data.append(entity["data"])

    tmpl_ready = TEMPLATES["PS04_VISUAL_READINESS"]
    ensure_dir("visual")

    # 分批评估（每批约6个场景）
    batch_size = 6
    batches = [all_scenes_data[i:i+batch_size] for i in range(0, len(all_scenes_data), batch_size)]
    all_readiness = []

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

    # 合并结果
    combined_readiness = {
        "overall_score": 0,
        "overall_assessment": "",
        "scenes": [],
        "recommendations": [],
        "batch_count": len(batches),
        "total_scenes": len(all_scenes_data),
    }

    scores = []
    for r in results:
        if isinstance(r, Exception):
            print(f"    ⚠ 任务失败: {r}")
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
        combined_readiness["overall_assessment"] = f"基于 {len(batches)} 批次 {len(all_scenes_data)} 场景的平均评分"

    save_json(os.path.join("visual", "readiness.json"), combined_readiness)

    summary_lines = [
        f"视觉评估: 覆盖全部 {len(all_scenes_data)} 场景 ({len(batches)} 批次)",
        f"综合评分: {combined_readiness['overall_score']}",
        f"成本: {cost_tracker.stage_summary(10)}",
    ]

    web_data = {
        "stats": {"综合评分": combined_readiness["overall_score"],
                  "覆盖场景": len(all_scenes_data), "批次": len(batches)},
        "cards": [
            {"label": "视觉就绪度综合评分", "value": str(combined_readiness["overall_score"]), "highlight": True},
            {"label": "覆盖范围", "value": f"全部 {len(all_scenes_data)} 场景"},
        ],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


# ══════════════════════════════════════════════════════════════════
#  Stage 11: 总结报告
# ══════════════════════════════════════════════════════════════════

def stage11_summary(db: PipelineDB) -> dict:
    """Stage 11: 总结报告（无API调用）。"""
    novel = read_novel()

    lines = []
    lines.append("=" * 70)
    lines.append("  第6轮测试报告 — 11阶段异步并行流水线")
    lines.append("  OpenClaudeCode API + gpt-5.4")
    lines.append("=" * 70)
    lines.append(f"  小说: 《我和沈词的长子》 ({len(novel)} 字)")
    lines.append(f"  API: OpenClaudeCode (www.openclaudecode.cn)")
    lines.append(f"  模型: {MODEL}")
    lines.append("")

    # 数据库统计
    tables = ["chapters", "characters", "scenes", "beats", "knowledge",
              "shots", "character_states", "dialogue", "shot_prompts"]
    stats = {}
    for table in tables:
        try:
            stats[table] = db.table_count(table)
        except Exception:
            stats[table] = 0

    lines.append("  数据库统计 (10张表):")
    for table, count in stats.items():
        lines.append(f"    {table}: {count} 条")
    lines.append("")

    # 文件统计
    dirs = ["chapters", "characters", "scenes", "beats", "knowledge",
            "visual", "shots", "character_states", "dialogue", "shot_prompts"]
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
    lines.append(f"    总Token: {cost_summary['total_tokens']} ({cost_summary['total_input_tokens']}in + {cost_summary['total_output_tokens']}out)")
    lines.append(f"    总API耗时: {cost_summary['total_api_elapsed_s']}s")
    lines.append("")

    # 每阶段成本
    stage_names = {
        1: "章节分割", 2: "摘要+扫描", 3: "角色详情+知识库",
        4: "场景+节拍", 5: "绑定", 6: "Shot拆分",
        7: "角色状态", 8: "对白提取", 9: "视觉Prompt",
        10: "视觉评估", 11: "总结报告",
    }
    lines.append("  各阶段成本:")
    for stage_num in range(1, 11):
        name = stage_names.get(stage_num, f"Stage {stage_num}")
        summary = cost_tracker.stage_summary(stage_num)
        lines.append(f"    Stage {stage_num:2d} ({name}): {summary}")
    lines.append("")

    # 阶段状态
    state = load_state()
    lines.append("  阶段状态:")
    for sid in sorted(state["stages"].keys(), key=int):
        s = state["stages"][sid]
        name = stage_names.get(int(sid), f"Stage {sid}")
        status = s.get("status", "pending")
        lines.append(f"    Stage {sid}: {name} — {status}")
    lines.append("")

    lines.append("=" * 70)
    lines.append("  流水线执行完毕")
    lines.append("=" * 70)

    report = "\n".join(lines)
    save_text("00_测试总结.txt", report)
    save_json("cost_summary.json", cost_summary)
    print(f"\n{report}")

    return {
        "summary_lines": [
            f"总API调用: {cost_summary['total_api_calls']} 次",
            f"总Token: {cost_summary['total_tokens']}",
            f"数据库: {sum(stats.values())} 条记录 (10张表)",
        ],
        "web_data": {
            "stats": {"API调用": cost_summary["total_api_calls"],
                      "总Token": cost_summary["total_tokens"],
                      "数据库记录": sum(stats.values())},
            "cards": [
                {"label": "总报告", "value": report[:500], "highlight": True},
            ],
        },
    }


# ══════════════════════════════════════════════════════════════════
#  流水线控制
# ══════════════════════════════════════════════════════════════════

STAGE_DEFS = [
    # (stage_num, name, func, is_async)
    (1, "Stage 1: 章节分割与存储", stage1_chapter_split, False),
    (2, "Stage 2: 章节摘要 + 角色扫描", stage2_summary_and_scan, True),
    (3, "Stage 3: 角色详情 + 知识库构建", stage3_character_detail_and_knowledge, True),
    (4, "Stage 4: 场景提取(原文) + 节拍提取", stage4_scene_and_beat, True),
    (5, "Stage 5: 节拍↔场景绑定", stage5_beat_scene_bind, True),
    (6, "Stage 6: Scene→Shot拆分", stage6_scene_to_shot, True),
    (7, "Stage 7: 角色状态追踪", stage7_character_state, True),
    (8, "Stage 8: 对白提取", stage8_dialogue_extract, True),
    (9, "Stage 9: 视觉Prompt生成", stage9_visual_prompt, True),
    (10, "Stage 10: 全场景视觉评估", stage10_visual_assess, True),
    (11, "Stage 11: 总结报告", stage11_summary, False),
]


async def run_pipeline_async(mode: str = "terminal", clean: bool = False):
    """运行完整流水线（异步主循环）。"""
    print("=" * 70)
    print("  第6轮测试 — 11阶段异步并行流水线（知识层+生产层）")
    print(f"  模式: {mode} | 模型: {MODEL} | 并发: {MAX_CONCURRENT}")
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
            "model": MODEL,
            "api": API_BASE,
            "pipeline_version": "round6",
        })

    # 找到起始阶段
    start_stage = 1
    for sid in sorted(state["stages"].keys(), key=int):
        if state["stages"][sid].get("status") == "completed":
            start_stage = int(sid) + 1
        else:
            break

    if start_stage > TOTAL_STAGES:
        print("  所有阶段已完成! 生成总结报告...")
        stage11_summary(db)
        db.close()
        return

    completed_stages = [s for s in state["stages"] if state["stages"][s].get("status") == "completed"]
    if completed_stages:
        print(f"  已完成阶段: {', '.join(sorted(completed_stages, key=int))}")
    print(f"  从 Stage {start_stage} 开始执行")
    print()

    pipeline_start = time.time()

    for stage_num, stage_name, stage_func, is_async in STAGE_DEFS:
        if stage_num < start_stage:
            continue

        if stage_num > start_stage:
            print(f"\n  -- 冷却 {STEP_COOLDOWN}s --")
            await asyncio.sleep(STEP_COOLDOWN)

        print()
        print("=" * 60)
        print(f"  [{stage_num}/{TOTAL_STAGES}] {stage_name}")
        print("=" * 60)

        mark_stage(state, stage_num, "running")

        try:
            if is_async:
                result = await stage_func(db)
            else:
                result = stage_func(db)
        except KeyboardInterrupt:
            print(f"\n\n  [中断] 用户中断流水线")
            print(f"  下次运行将从 Stage {stage_num} 续跑")
            db.close()
            sys.exit(130)
        except Exception as e:
            print(f"\n  [FAIL] {stage_name}")
            print(f"  错误: {e}")
            traceback.print_exc()
            print(f"\n  流水线停止于 Stage {stage_num}")
            print(f"  重新运行脚本将从 Stage {stage_num} 自动续跑")
            db.close()
            sys.exit(1)

        mark_stage(state, stage_num, "completed")

        if stage_num < TOTAL_STAGES:
            action = await confirm_stage_async(
                mode, stage_name, stage_num,
                result.get("summary_lines", []),
                result.get("web_data"),
            )

            if action == "retry":
                mark_stage(state, stage_num, "pending")
                print(f"\n  [RETRY] 重跑 {stage_name}...")
                db.close()
                await run_pipeline_async(mode=mode, clean=False)
                return
            elif action == "stop":
                print(f"\n  [STOP] 用户停止流水线")
                print(f"  下次运行将从 Stage {stage_num + 1} 续跑")
                db.close()
                return

    pipeline_elapsed = time.time() - pipeline_start
    print()
    print("=" * 70)
    print(f"  流水线完成! 总耗时: {pipeline_elapsed:.1f}s ({pipeline_elapsed/60:.1f}min)")
    print("=" * 70)
    print()

    db.close()


# ── 主入口 ────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="第6轮测试 — 11阶段异步并行流水线")
    parser.add_argument("--mode", choices=["terminal", "web"], default="terminal",
                        help="确认模式: terminal (默认) 或 web")
    parser.add_argument("--clean", action="store_true",
                        help="清空结果目录，从头重跑")
    args = parser.parse_args()

    asyncio.run(run_pipeline_async(mode=args.mode, clean=args.clean))


if __name__ == "__main__":
    main()
