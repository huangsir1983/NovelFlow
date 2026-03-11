"""第5轮测试 — 知识库构建流水线（框架重构）.

用法:
  python run_test_round5.py            # 终端模式，自动从断点续跑
  python run_test_round5.py --mode web # Web 确认模式
  python run_test_round5.py --clean    # 清空重跑
  python run_test_round5.py --mode web --clean

特性:
  - 实体级 JSON 文件存储（每个章节/角色/场景/节拍独立文件）
  - 7 阶段确认流程（每阶段完成后暂停确认）
  - 双存储：JSON 文件 + SQLite 数据库
  - 断点续跑机制（pipeline_state.json）
  - 两种确认模式：终端 input() / Web 浏览器
"""

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
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "第5次测试结果")
TIMEOUT = 500
PROJECT_ID = "novel_shenCi"

MAX_RETRIES = 3
RETRY_WAIT_BASE = 10
RATE_LIMIT_WAIT = 30
STEP_COOLDOWN = 2

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


def call_api(system: str, user: str, temperature: float = 0.7,
             max_tokens: int = 4096) -> str:
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
            with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
                resp = client.post(API_BASE, json=body, headers=headers)
                resp.raise_for_status()
            data = resp.json()
            output = data.get("output", [])
            if output:
                content = output[0].get("content", [])
                if content:
                    return content[0].get("text", "")
            return ""
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


# ── 文件工具 ──────────────────────────────────────────────────────

def ensure_dir(*parts):
    """确保目录存在，返回完整路径。"""
    path = os.path.join(OUTPUT_DIR, *parts)
    os.makedirs(path, exist_ok=True)
    return path


def save_entity_json(folder: str, filename: str, meta: dict, hooks: dict, data: dict):
    """保存单个实体 JSON 文件。"""
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
    """保存 _index.json（清单 + 统计）。"""
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
    """更新实体 JSON 的 _hooks 字段。"""
    filepath = os.path.join(OUTPUT_DIR, folder, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        entity = json.load(f)
    entity.setdefault("_hooks", {})
    for k, v in updates.items():
        if isinstance(v, list) and isinstance(entity["_hooks"].get(k), list):
            # 合并列表（去重）
            existing = set(str(x) for x in entity["_hooks"][k])
            entity["_hooks"][k].extend(x for x in v if str(x) not in existing)
        else:
            entity["_hooks"][k] = v
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(entity, f, ensure_ascii=False, indent=2)


def save_text(filename: str, content: str):
    """保存普通文本文件到输出目录根。"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"    → {filename}")


def save_json(filename: str, data):
    """保存 JSON 到输出目录根。"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"    → {filename}")


def list_entity_files(folder: str) -> list[str]:
    """列出 folder 下除 _index.json 外的 JSON 文件。"""
    dirpath = os.path.join(OUTPUT_DIR, folder)
    if not os.path.isdir(dirpath):
        return []
    return sorted(f for f in os.listdir(dirpath)
                  if f.endswith(".json") and f != "_index.json")


# ── 流水线状态 ────────────────────────────────────────────────────

STATE_FILE = os.path.join(OUTPUT_DIR, "pipeline_state.json")
TOTAL_STAGES = 7


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
    """终端确认，返回 'continue'|'retry'|'stop'。"""
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
    """Web 确认，返回 'continue'|'retry'|'stop'。"""
    global _web_server
    if _web_server is None:
        _web_server = ConfirmServer(port=5678)
    return _web_server.wait_for_confirm(stage_name, stage_number, stage_data)


def confirm_stage(mode: str, stage_name: str, stage_number: int,
                  summary_lines: list[str], stage_data: dict = None) -> str:
    """根据模式分发确认。"""
    if mode == "web":
        if stage_data is None:
            stage_data = {"cards": [{"value": line} for line in summary_lines]}
        return confirm_web(stage_name, stage_number, stage_data)
    else:
        return confirm_terminal(stage_name, summary_lines)


# ── 文件名安全化 ──────────────────────────────────────────────────

def safe_filename(name: str) -> str:
    """将中文名转为安全文件名。"""
    # 保留中文字符、字母、数字、下划线、连字符
    name = re.sub(r'[\\/:*?"<>|\s]+', '_', name)
    return name.strip('_') or 'unnamed'


# ══════════════════════════════════════════════════════════════════
#  7 个阶段函数
# ══════════════════════════════════════════════════════════════════

def stage1_chapter_split(db: PipelineDB) -> dict:
    """Stage 1: 章节分割与存储。"""
    novel = read_novel()
    tmpl = TEMPLATES["P01_CHAPTER_SPLIT"]

    print(f"  小说长度: {len(novel)} 字")
    print(f"  调用 P01_CHAPTER_SPLIT...")

    t0 = time.time()
    resp = call_api(
        system=tmpl["system"],
        user=tmpl["user"].format(text=novel),
        temperature=tmpl["temperature"],
        max_tokens=tmpl["max_tokens"],
    )
    elapsed = time.time() - t0
    markers = extract_json(resp)

    print(f"  API 返回 {len(markers)} 个章节标记 ({elapsed:.1f}s)")
    print(f"  提取完整章节内容...")

    ensure_dir("chapters")
    index_entries = []

    for i, ch in enumerate(markers):
        ch_id = f"ch_{i:03d}"
        title = ch.get("title", f"第{i+1}章")
        start = ch.get("start_marker", "")
        end = ch.get("end_marker", "")

        # 从原文提取完整内容
        si = novel.find(start) if start else -1
        ei = novel.find(end) if end else -1
        if si >= 0 and ei >= 0:
            content = novel[si:ei + len(end)]
        else:
            content = f"（未能定位章节内容: {title}）"

        word_count = len(content)
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

        # 写入 SQLite
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

    # 返回确认数据
    summary_lines = [f"共分割 {len(markers)} 个章节:"]
    for e in index_entries:
        summary_lines.append(f"  {e['order']+1}. {e['title']} ({e['word_count']}字)")
    summary_lines.append(f"  总耗时: {elapsed:.1f}s")

    web_data = {
        "stats": {"章节数": len(markers), "总字数": sum(e["word_count"] for e in index_entries)},
        "items_title": "章节列表",
        "items": [
            {"idx": e["order"]+1, "name": e["title"], "desc": f"{e['word_count']}字"}
            for e in index_entries
        ],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


def stage2_chapter_summary(db: PipelineDB) -> dict:
    """Stage 2: 章节摘要。"""
    tmpl = TEMPLATES["P01B_CHAPTER_SUMMARY"]
    ch_files = list_entity_files("chapters")
    print(f"  共 {len(ch_files)} 个章节待摘要")

    summaries = []
    total_time = 0

    for i, fname in enumerate(ch_files):
        entity = load_entity_json("chapters", fname)
        ch_data = entity["data"]
        ch_id = entity["_meta"]["id"]
        title = ch_data["title"]
        content = ch_data["content"]

        print(f"  [{i+1}/{len(ch_files)}] {title} ({len(content)}字)...", end="", flush=True)

        t0 = time.time()
        resp = call_api(
            system=tmpl["system"],
            user=tmpl["user"].format(chapter_title=title, text=content),
            temperature=tmpl["temperature"],
            max_tokens=tmpl["max_tokens"],
        )
        elapsed = time.time() - t0
        total_time += elapsed

        summary = resp.strip()
        summaries.append({"ch_id": ch_id, "title": title, "summary": summary})

        # 更新章节 JSON 的 summary 字段
        entity["data"]["summary"] = summary
        filepath = os.path.join(OUTPUT_DIR, "chapters", fname)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(entity, f, ensure_ascii=False, indent=2)

        # 更新 SQLite
        db.update_chapter_summary(ch_id, summary)

        print(f" {elapsed:.1f}s")

    # 拼接 synopsis
    synopsis = "\n\n".join(f"【{s['title']}】\n{s['summary']}" for s in summaries)
    ensure_dir("knowledge")
    save_text(os.path.join("knowledge", "synopsis.txt"), synopsis)

    summary_lines = [f"共生成 {len(summaries)} 章摘要, synopsis {len(synopsis)} 字:"]
    for s in summaries:
        preview = s["summary"][:60] + "..." if len(s["summary"]) > 60 else s["summary"]
        summary_lines.append(f"  {s['title']}: {preview}")
    summary_lines.append(f"  总耗时: {total_time:.1f}s")

    web_data = {
        "stats": {"摘要数": len(summaries), "synopsis字数": len(synopsis)},
        "items_title": "各章摘要",
        "items": [
            {"idx": i+1, "name": s["title"],
             "desc": s["summary"][:80] + ("..." if len(s["summary"]) > 80 else "")}
            for i, s in enumerate(summaries)
        ],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


def stage3_character_extract(db: PipelineDB) -> dict:
    """Stage 3: 角色提取。"""
    # 读取 synopsis
    synopsis_path = os.path.join(OUTPUT_DIR, "knowledge", "synopsis.txt")
    with open(synopsis_path, "r", encoding="utf-8") as f:
        synopsis = f.read()

    # 3a: 角色名单扫描
    tmpl_scan = TEMPLATES["P03A_CHARACTER_SCAN"]
    print(f"  [3a] 角色名单扫描...")

    t0 = time.time()
    resp = call_api(
        system=tmpl_scan["system"],
        user=tmpl_scan["user"].format(synopsis=synopsis),
        temperature=tmpl_scan["temperature"],
        max_tokens=tmpl_scan["max_tokens"],
    )
    elapsed_scan = time.time() - t0
    char_list = extract_json(resp)
    print(f"  [3a] 发现 {len(char_list)} 个角色 ({elapsed_scan:.1f}s)")

    # 3b: 逐角色详情（跳过 minor）
    tmpl_detail = TEMPLATES["P03B_CHARACTER_DETAIL"]
    main_chars = [c for c in char_list if c.get("role") in ("protagonist", "antagonist", "supporting")]
    all_names = [c.get("name", "?") for c in char_list]

    print(f"  [3b] 主要角色 {len(main_chars)} 个，开始详情提取...")

    ensure_dir("characters")
    index_entries = []
    total_time = elapsed_scan

    for i, ch in enumerate(main_chars):
        name = ch.get("name", "?")
        brief = ch.get("brief", ch.get("description", ""))
        other_names = [n for n in all_names if n != name]

        print(f"  [{i+1}/{len(main_chars)}] {name}...", end="", flush=True)

        t0 = time.time()
        resp = call_api(
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
        elapsed = time.time() - t0
        total_time += elapsed

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

        # 写入 SQLite
        db.upsert_character(PROJECT_ID, {"id": char_id, **data})

        index_entries.append({
            "id": char_id, "name": name, "role": data["role"],
            "filename": filename,
            "description": data["description"][:50] if data["description"] else "",
        })

        print(f" {elapsed:.1f}s")

    # minor 角色也加入索引（仅名单信息）
    for ch in char_list:
        if ch.get("role") == "minor":
            name = ch.get("name", "?")
            index_entries.append({
                "id": f"char_{safe_filename(name)}",
                "name": name,
                "role": "minor",
                "filename": None,
                "description": ch.get("brief", ch.get("description", ""))[:50],
            })

    save_index("characters", index_entries)

    summary_lines = [f"共提取 {len(index_entries)} 个角色 (主要角色 {len(main_chars)}):"]
    for e in index_entries:
        tag = f"[{e['role']}]"
        desc = e.get("description", "")
        summary_lines.append(f"  {e['name']:8s} {tag:14s} — {desc}")
    summary_lines.append(f"  总耗时: {total_time:.1f}s")

    web_data = {
        "stats": {"总角色数": len(index_entries), "主要角色": len(main_chars)},
        "items_title": "角色列表",
        "items": [
            {"idx": i+1, "name": e["name"], "tag": e["role"],
             "desc": e.get("description", "")}
            for i, e in enumerate(index_entries)
        ],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


def stage4_scene_extract(db: PipelineDB) -> dict:
    """Stage 4: 场景提取。"""
    # 读取 synopsis
    synopsis_path = os.path.join(OUTPUT_DIR, "knowledge", "synopsis.txt")
    with open(synopsis_path, "r", encoding="utf-8") as f:
        synopsis = f.read()

    # 读取角色名单
    char_index_path = os.path.join(OUTPUT_DIR, "characters", "_index.json")
    with open(char_index_path, "r", encoding="utf-8") as f:
        char_index = json.load(f)
    char_names = ", ".join(e["name"] for e in char_index["entries"][:10])

    # 读取章节索引
    ch_index_path = os.path.join(OUTPUT_DIR, "chapters", "_index.json")
    with open(ch_index_path, "r", encoding="utf-8") as f:
        ch_index = json.load(f)
    ch_entries = ch_index["entries"]

    tmpl = TEMPLATES["P04_SCENE_EXTRACT"]

    # 按章节逐章提取场景
    ensure_dir("scenes")
    all_scenes_entries = []
    scene_order = 0
    total_time = 0

    for ci, ch_entry in enumerate(ch_entries):
        ch_id = ch_entry["id"]
        ch_title = ch_entry["title"]

        # 加载章节 JSON 获取摘要（用摘要而非全文，避免 token 过长）
        ch_entity = load_entity_json("chapters", ch_entry["filename"])
        ch_summary = ch_entity["data"].get("summary", "")
        if not ch_summary:
            ch_summary = ch_entity["data"]["content"][:2000]

        batch_text = f"【{ch_title}】\n{ch_summary}"
        print(f"  [章节 {ci+1}/{len(ch_entries)}] {ch_title}...", end="", flush=True)

        t0 = time.time()
        try:
            resp = call_api(
                system=tmpl["system"],
                user=tmpl["user"].format(text=batch_text, character_names=char_names),
                temperature=tmpl["temperature"],
                max_tokens=4096,
            )
            elapsed = time.time() - t0
            total_time += elapsed

            scenes = extract_json(resp)
            if not isinstance(scenes, list):
                scenes = [scenes]
        except Exception as e:
            elapsed = time.time() - t0
            total_time += elapsed
            print(f" [WARN] 跳过 ({type(e).__name__}: {e})")
            # 回写空场景列表
            update_entity_hooks("chapters", ch_entry["filename"], {
                "downstream": {
                    "scenes": [],
                    "beats": ch_entity["_hooks"].get("downstream", {}).get("beats", []),
                    "characters_mentioned": ch_entity["_hooks"].get("downstream", {}).get("characters_mentioned", []),
                }
            })
            continue

        scene_ids_for_chapter = []

        for s in scenes:
            scene_id = f"scene_{scene_order:03d}"
            filename = f"{scene_id}.json"

            meta = {
                "id": scene_id,
                "type": "scene",
                "pipeline_step": "scene_extract",
                "created_at": now_iso(),
            }
            hooks = {
                "ready_for": ["visual_readiness", "storyboard", "shot_design", "image_prompt"],
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
                "tension_score": s.get("tension_score", 0),
                "order": scene_order,
            }

            save_entity_json("scenes", filename, meta, hooks, data)

            # 写入 SQLite
            db.upsert_scene(PROJECT_ID, {
                "id": scene_id, "chapter_id": ch_id, **data,
            })

            all_scenes_entries.append({
                "id": scene_id, "filename": filename,
                "heading": data["heading"], "location": data["location"],
                "tension_score": data["tension_score"], "order": scene_order,
                "source_chapter": ch_id,
            })
            scene_ids_for_chapter.append(scene_id)
            scene_order += 1

        # 回写章节 JSON 的 _hooks.downstream.scenes
        update_entity_hooks("chapters", ch_entry["filename"], {
            "downstream": {
                "scenes": scene_ids_for_chapter,
                "beats": ch_entity["_hooks"].get("downstream", {}).get("beats", []),
                "characters_mentioned": ch_entity["_hooks"].get("downstream", {}).get("characters_mentioned", []),
            }
        })

        print(f" {len(scenes)} 场景 ({elapsed:.1f}s)")

    save_index("scenes", all_scenes_entries)

    summary_lines = [f"共提取 {len(all_scenes_entries)} 个场景:"]
    for e in all_scenes_entries[:15]:
        ts = e.get("tension_score", 0)
        summary_lines.append(f"  {e['id']}: {e.get('heading', '')} [{e.get('location', '')}] 张力={ts}")
    if len(all_scenes_entries) > 15:
        summary_lines.append(f"  ... 共 {len(all_scenes_entries)} 个")
    summary_lines.append(f"  总耗时: {total_time:.1f}s")

    web_data = {
        "stats": {"场景数": len(all_scenes_entries),
                  "覆盖章节": len(ch_entries)},
        "items_title": "场景列表",
        "items": [
            {"idx": e["order"]+1, "name": e.get("heading", e["id"]),
             "tag": e.get("location", ""),
             "desc": f"张力: {e.get('tension_score', 0)}"}
            for e in all_scenes_entries[:30]
        ],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


def stage5_beat_extract(db: PipelineDB) -> dict:
    """Stage 5: 节拍提取。"""
    synopsis_path = os.path.join(OUTPUT_DIR, "knowledge", "synopsis.txt")
    with open(synopsis_path, "r", encoding="utf-8") as f:
        synopsis = f.read()

    tmpl = TEMPLATES["P10_NOVEL_TO_BEAT"]
    print(f"  Synopsis 长度: {len(synopsis)} 字")
    print(f"  调用 P10_NOVEL_TO_BEAT...")

    t0 = time.time()
    resp = call_api(
        system=tmpl["system"],
        user=tmpl["user"].format(text=synopsis),
        temperature=tmpl["temperature"],
        max_tokens=tmpl["max_tokens"],
    )
    elapsed = time.time() - t0

    beats = extract_json(resp)
    if not isinstance(beats, list):
        beats = [beats]

    ensure_dir("beats")
    index_entries = []

    for i, b in enumerate(beats):
        beat_id = f"beat_{i:03d}"
        filename = f"{beat_id}.json"

        meta = {
            "id": beat_id,
            "type": "beat",
            "pipeline_step": "beat_extract",
            "created_at": now_iso(),
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
            "emotional_value": b.get("emotional_value", 0),
            "hook_potential": b.get("hook_potential", "medium"),
            "rhythm_warning": str(b.get("rhythm_warning", "false")),
            "order": i,
        }

        save_entity_json("beats", filename, meta, hooks, data)

        # 写入 SQLite
        db.upsert_beat(PROJECT_ID, {"id": beat_id, **data})

        index_entries.append({
            "id": beat_id, "filename": filename,
            "title": data["title"], "beat_type": data["beat_type"],
            "save_the_cat": data["save_the_cat"],
            "emotional_value": data["emotional_value"],
            "order": i,
        })

    save_index("beats", index_entries)

    summary_lines = [f"共提取 {len(beats)} 个节拍:"]
    for e in index_entries:
        stc = f"({e['save_the_cat']})" if e.get("save_the_cat") else ""
        summary_lines.append(
            f"  {e['id']}: {e['title']} [{e['beat_type']}] {stc} 情感={e['emotional_value']}")
    summary_lines.append(f"  耗时: {elapsed:.1f}s")

    web_data = {
        "stats": {"节拍数": len(beats)},
        "items_title": "节拍列表",
        "items": [
            {"idx": e["order"]+1, "name": e["title"],
             "tag": e.get("save_the_cat", e["beat_type"]),
             "desc": f"情感值: {e['emotional_value']}"}
            for e in index_entries
        ],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


def stage6_knowledge_build(db: PipelineDB) -> dict:
    """Stage 6: 知识库构建。"""
    synopsis_path = os.path.join(OUTPUT_DIR, "knowledge", "synopsis.txt")
    with open(synopsis_path, "r", encoding="utf-8") as f:
        synopsis = f.read()

    # 读取角色名
    char_index_path = os.path.join(OUTPUT_DIR, "characters", "_index.json")
    with open(char_index_path, "r", encoding="utf-8") as f:
        char_index = json.load(f)
    char_names = ", ".join(e["name"] for e in char_index["entries"][:10])

    # 读取场景地点
    loc_names = "未知"
    scene_index_path = os.path.join(OUTPUT_DIR, "scenes", "_index.json")
    if os.path.exists(scene_index_path):
        with open(scene_index_path, "r", encoding="utf-8") as f:
            scene_index = json.load(f)
        locs = list(set(e.get("location", "") for e in scene_index["entries"] if e.get("location")))
        if locs:
            loc_names = ", ".join(locs[:10])

    tmpl = TEMPLATES["P05_KNOWLEDGE_BASE_V2"]
    print(f"  调用 P05_KNOWLEDGE_BASE_V2...")

    t0 = time.time()
    resp = call_api(
        system=tmpl["system"],
        user=tmpl["user"].format(
            synopsis=synopsis,
            character_names=char_names,
            location_names=loc_names,
        ),
        temperature=tmpl["temperature"],
        max_tokens=tmpl["max_tokens"],
    )
    elapsed = time.time() - t0

    data = extract_json(resp)
    wb = data.get("world_building", {})
    sg = data.get("style_guide", {})

    ensure_dir("knowledge")
    save_json(os.path.join("knowledge", "world_building.json"), wb)
    save_json(os.path.join("knowledge", "style_guide.json"), sg)

    # 写入 SQLite
    db.upsert_knowledge(PROJECT_ID, {
        "world_building": wb,
        "style_guide": sg,
        "synopsis": synopsis,
    })

    summary_lines = [
        f"知识库构建完成:",
        f"  world_building: {len(wb)} 项",
        f"  style_guide: {len(sg)} 项",
        f"  耗时: {elapsed:.1f}s",
    ]

    wb_preview = ", ".join(list(wb.keys())[:5]) if isinstance(wb, dict) else str(wb)[:100]
    sg_preview = ", ".join(list(sg.keys())[:5]) if isinstance(sg, dict) else str(sg)[:100]

    web_data = {
        "stats": {"世界观条目": len(wb) if isinstance(wb, dict) else 1,
                  "风格指南条目": len(sg) if isinstance(sg, dict) else 1},
        "cards": [
            {"label": "世界观概要", "value": wb_preview},
            {"label": "风格指南概要", "value": sg_preview},
        ],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


def stage7_visual_assess(db: PipelineDB) -> dict:
    """Stage 7: 视觉评估与分镜。"""
    scene_files = list_entity_files("scenes")[:6]
    if not scene_files:
        return {
            "summary_lines": ["无场景数据，跳过视觉评估"],
            "web_data": {"cards": [{"value": "无场景数据"}]},
        }

    # 收集场景数据用于评估
    scenes_for_eval = []
    for fname in scene_files:
        entity = load_entity_json("scenes", fname)
        scenes_for_eval.append(entity["data"])

    # PS04: 视觉就绪度评估
    tmpl_ready = TEMPLATES["PS04_VISUAL_READINESS"]
    scenes_text = fmt_json(scenes_for_eval)
    print(f"  [PS04] 评估 {len(scenes_for_eval)} 个场景的视觉就绪度...")

    t0 = time.time()
    resp = call_api(
        system=tmpl_ready["system"],
        user=tmpl_ready["user"].format(text=scenes_text),
        temperature=tmpl_ready["temperature"],
        max_tokens=tmpl_ready["max_tokens"],
    )
    elapsed_ready = time.time() - t0

    readiness = extract_json(resp)
    overall_score = readiness.get("overall_score", "N/A")

    ensure_dir("visual")
    save_json(os.path.join("visual", "readiness.json"), readiness)
    print(f"  [PS04] 视觉评分: {overall_score} ({elapsed_ready:.1f}s)")

    # PS05: 分镜优化（前3个场景）
    tmpl_sb = TEMPLATES["PS05_STORYBOARD_OPTIMIZE"]
    sb_scenes = scenes_for_eval[:3]
    sb_text = fmt_json(sb_scenes)
    print(f"  [PS05] 优化 {len(sb_scenes)} 个场景的分镜...")

    t0 = time.time()
    resp = call_api(
        system=tmpl_sb["system"],
        user=tmpl_sb["user"].format(text=sb_text),
        temperature=tmpl_sb["temperature"],
        max_tokens=tmpl_sb["max_tokens"],
    )
    elapsed_sb = time.time() - t0

    storyboard_data = extract_json(resp)
    if not isinstance(storyboard_data, list):
        storyboard_data = [storyboard_data]

    # 保存分镜结果
    ensure_dir("visual", "storyboard")
    for i, sb in enumerate(storyboard_data):
        sb_filename = f"scene_{i:03d}.json"
        save_json(os.path.join("visual", "storyboard", sb_filename), sb)

    print(f"  [PS05] 分镜优化完成 ({elapsed_sb:.1f}s)")

    total_time = elapsed_ready + elapsed_sb
    has_vn = any("visual_notes" in s for s in storyboard_data) if isinstance(storyboard_data, list) else False

    summary_lines = [
        f"视觉评估与分镜完成:",
        f"  视觉就绪度: {overall_score}",
        f"  分镜优化: {len(storyboard_data)} 场景, visual_notes={'有' if has_vn else '无'}",
        f"  总耗时: {total_time:.1f}s",
    ]

    web_data = {
        "stats": {"视觉评分": overall_score, "分镜场景": len(storyboard_data)},
        "cards": [
            {"label": "视觉就绪度评分", "value": str(overall_score), "highlight": True},
            {"label": "分镜优化", "value": f"{len(storyboard_data)} 个场景已优化"},
        ],
    }

    return {"summary_lines": summary_lines, "web_data": web_data}


# ══════════════════════════════════════════════════════════════════
#  总结报告
# ══════════════════════════════════════════════════════════════════

def generate_summary(db: PipelineDB):
    """汇总所有阶段结果，生成总结报告。"""
    novel = read_novel()

    lines = []
    lines.append("=" * 70)
    lines.append("  第5轮测试报告 — 知识库构建流水线（框架重构）")
    lines.append("  OpenClaudeCode API + gpt-5.4")
    lines.append("=" * 70)
    lines.append(f"  小说: 《我和沈词的长子》 ({len(novel)} 字)")
    lines.append(f"  API: OpenClaudeCode (www.openclaudecode.cn)")
    lines.append(f"  模型: {MODEL}")
    lines.append("")

    # 统计各表数据量
    stats = {
        "chapters": db.table_count("chapters"),
        "characters": db.table_count("characters"),
        "scenes": db.table_count("scenes"),
        "beats": db.table_count("beats"),
        "knowledge": db.table_count("knowledge"),
    }
    lines.append("  数据库统计:")
    for table, count in stats.items():
        lines.append(f"    {table}: {count} 条")
    lines.append("")

    # 检查各目录文件
    dirs = ["chapters", "characters", "scenes", "beats", "knowledge", "visual"]
    for d in dirs:
        files = list_entity_files(d)
        dirpath = os.path.join(OUTPUT_DIR, d)
        if os.path.isdir(dirpath):
            all_files = os.listdir(dirpath)
            lines.append(f"  {d}/: {len(all_files)} 文件")
        else:
            lines.append(f"  {d}/: 不存在")
    lines.append("")

    # 阶段状态
    state = load_state()
    lines.append("  阶段状态:")
    stage_names = {
        "1": "章节分割", "2": "章节摘要", "3": "角色提取",
        "4": "场景提取", "5": "节拍提取", "6": "知识库构建",
        "7": "视觉评估",
    }
    for sid in sorted(state["stages"].keys(), key=int):
        s = state["stages"][sid]
        name = stage_names.get(sid, f"Stage {sid}")
        status = s.get("status", "pending")
        lines.append(f"    Stage {sid}: {name} — {status}")
    lines.append("")

    lines.append("=" * 70)
    lines.append("  流水线执行完毕")
    lines.append("=" * 70)

    report = "\n".join(lines)
    save_text("00_测试总结.txt", report)
    print(f"\n{report}")


# ══════════════════════════════════════════════════════════════════
#  流水线控制
# ══════════════════════════════════════════════════════════════════

STAGE_DEFS = [
    (1, "Stage 1: 章节分割与存储", stage1_chapter_split),
    (2, "Stage 2: 章节摘要", stage2_chapter_summary),
    (3, "Stage 3: 角色提取", stage3_character_extract),
    (4, "Stage 4: 场景提取", stage4_scene_extract),
    (5, "Stage 5: 节拍提取", stage5_beat_extract),
    (6, "Stage 6: 知识库构建", stage6_knowledge_build),
    (7, "Stage 7: 视觉评估与分镜", stage7_visual_assess),
]


def run_pipeline(mode: str = "terminal", clean: bool = False):
    """运行完整流水线。"""
    print("=" * 70)
    print("  第5轮测试 — 知识库构建流水线（框架重构）")
    print(f"  模式: {mode} | 模型: {MODEL}")
    print("=" * 70)
    print()

    # --clean: 清空结果目录
    if clean:
        if os.path.exists(OUTPUT_DIR):
            shutil.rmtree(OUTPUT_DIR)
            print("  [CLEAN] 已清空结果目录")
        print()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 加载/初始化状态
    state = load_state()
    save_state(state)

    # 初始化数据库
    db_path = os.path.join(OUTPUT_DIR, "knowledge_base.db")
    db = PipelineDB(db_path)
    db.upsert_project(PROJECT_ID, "我和沈词的长子", NOVEL_PATH)

    # 保存项目元信息
    project_json_path = os.path.join(OUTPUT_DIR, "project.json")
    if not os.path.exists(project_json_path):
        save_json("project.json", {
            "id": PROJECT_ID,
            "name": "我和沈词的长子",
            "novel_path": NOVEL_PATH,
            "created_at": now_iso(),
            "model": MODEL,
            "api": API_BASE,
        })

    # 找到第一个需要执行的阶段
    start_stage = 1
    for sid in sorted(state["stages"].keys(), key=int):
        if state["stages"][sid].get("status") == "completed":
            start_stage = int(sid) + 1
        else:
            break

    if start_stage > TOTAL_STAGES:
        print("  所有阶段已完成! 生成总结报告...")
        generate_summary(db)
        db.close()
        return

    # 显示状态
    completed_stages = [s for s in state["stages"] if state["stages"][s].get("status") == "completed"]
    if completed_stages:
        print(f"  已完成阶段: {', '.join(sorted(completed_stages, key=int))}")
    print(f"  从 Stage {start_stage} 开始执行")
    print()

    # 执行流水线
    pipeline_start = time.time()

    for stage_num, stage_name, stage_func in STAGE_DEFS:
        if stage_num < start_stage:
            continue

        # 步骤间冷却
        if stage_num > start_stage:
            print(f"\n  -- 冷却 {STEP_COOLDOWN}s --")
            time.sleep(STEP_COOLDOWN)

        print()
        print("=" * 60)
        print(f"  [{stage_num}/{TOTAL_STAGES}] {stage_name}")
        print("=" * 60)

        mark_stage(state, stage_num, "running")

        try:
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

        # 确认
        if stage_num < TOTAL_STAGES:
            action = confirm_stage(
                mode, stage_name, stage_num,
                result.get("summary_lines", []),
                result.get("web_data"),
            )

            if action == "retry":
                # 重置本阶段状态，重新执行
                mark_stage(state, stage_num, "pending")
                print(f"\n  [RETRY] 重跑 {stage_name}...")
                # 递归调用 — 重新从本阶段开始
                db.close()
                run_pipeline(mode=mode, clean=False)
                return
            elif action == "stop":
                print(f"\n  [STOP] 用户停止流水线")
                print(f"  下次运行将从 Stage {stage_num + 1} 续跑")
                db.close()
                return

    # 全部完成
    pipeline_elapsed = time.time() - pipeline_start
    print()
    print("=" * 70)
    print(f"  流水线完成! 总耗时: {pipeline_elapsed:.1f}s")
    print("=" * 70)
    print()

    generate_summary(db)
    db.close()


# ── 主入口 ────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="第5轮测试 — 知识库构建流水线")
    parser.add_argument("--mode", choices=["terminal", "web"], default="terminal",
                        help="确认模式: terminal (默认) 或 web")
    parser.add_argument("--clean", action="store_true",
                        help="清空结果目录，从头重跑")
    args = parser.parse_args()

    run_pipeline(mode=args.mode, clean=args.clean)


if __name__ == "__main__":
    main()
