"""Full novel pipeline test — 我和沈词的长子.txt
Runs through all pipeline stages and saves each result to 测试/ folder.

v2: Marker-based chapter split, standard model tier, full chapter processing,
    distributed scene/beat extraction, enhanced character visual fields.
"""

import json
import sys
import os
import re
import time
import traceback

sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, init_db
from models.ai_provider import AIProvider
from uuid import uuid4

init_db()
db = SessionLocal()

# ── Setup Comfly Gemini provider ──────────────────────────────────
db.query(AIProvider).filter(AIProvider.name == "_novel_pipeline").delete()
db.commit()

provider = AIProvider(
    id=str(uuid4()),
    name="_novel_pipeline",
    provider_type="gemini",
    base_url="https://ai.comfly.chat",
    api_key="sk-4f5dNlvbRjwcwjsxGeWU2NqY8Yp4u9SaYZUeuAhQVrofzD6R",
    models=[
        {
            "model_id": "gemini-3.1-flash-lite-preview",
            "display_name": "Gemini Flash Lite",
            "model_type": "text",
            "capability_tier": "fast",
            "max_tokens": 8192,
            "supports_streaming": True,
        },
        {
            "model_id": "gemini-3.1-pro-preview",
            "display_name": "Gemini 3.1 Pro",
            "model_type": "text",
            "capability_tier": "standard",
            "max_tokens": 16384,
            "supports_streaming": True,
        },
        {
            "model_id": "gemini-3.1-flash-image-preview",
            "display_name": "Gemini Flash Image (2K)",
            "model_type": "image",
            "capability_tier": "standard",
            "max_tokens": 8192,
            "supports_streaming": False,
        },
    ],
    is_default=True,
    enabled=True,
    priority=0,
)
db.add(provider)
db.commit()

from services.ai_engine import ai_engine
from services.prompt_templates import render_prompt

ai_engine.invalidate_cache()

# ── Read novel ────────────────────────────────────────────────────
NOVEL_PATH = os.path.join(os.path.dirname(__file__), "..", "测试", "我和沈词的长子.txt")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "测试")

with open(NOVEL_PATH, "rb") as f:
    raw = f.read()
NOVEL_TEXT = raw.decode("gb18030")

# Strip the copyright header (everything before the actual story)
header_end = NOVEL_TEXT.find("我和沈词的长子")
if header_end > 0:
    NOVEL_TEXT = NOVEL_TEXT[header_end:]

print(f"Novel loaded: {len(NOVEL_TEXT)} chars")
print(f"Output dir: {os.path.abspath(OUTPUT_DIR)}")
print()


# ── Helpers ───────────────────────────────────────────────────────

def fix_json(raw_text):
    """Extract and fix JSON from AI response."""
    text = raw_text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    # Fix trailing commas
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)
    return json.loads(text)


def save_result(filename, content):
    """Save result to 测试/ folder."""
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  -> Saved: {filename}")


def call_ai(template_id, delay=2, retries=2, **kwargs):
    """Call AI with template and return parsed result. Retries on server errors."""
    prompt = render_prompt(template_id, **kwargs)
    last_err = None
    for attempt in range(retries + 1):
        try:
            start = time.time()
            result = ai_engine.call(
                system=prompt["system"],
                messages=[{"role": "user", "content": prompt["user"]}],
                capability_tier=prompt["capability_tier"],
                temperature=prompt["temperature"],
                max_tokens=prompt["max_tokens"],
                db=db,
            )
            elapsed = time.time() - start
            content = result["content"]
            parsed = fix_json(content)
            info = {
                "model": result["model"],
                "provider": result["provider"],
                "elapsed": round(elapsed, 1),
                "output_chars": len(content),
            }
            if delay > 0:
                time.sleep(delay)
            return parsed, info
        except Exception as e:
            last_err = e
            if attempt < retries:
                wait = 5 * (attempt + 1)
                print(f"  Retry {attempt+1}/{retries} after error: {e} (waiting {wait}s)")
                time.sleep(wait)
    raise last_err


def resolve_markers(text, markers):
    """Resolve start_marker/end_marker pairs to full chapter content from original text."""
    chapters = []
    for i, m in enumerate(markers):
        start_marker = m.get("start_marker", "")
        end_marker = m.get("end_marker", "")
        title = m.get("title", f"章节{i+1}")

        if not start_marker:
            continue

        # Find start position
        start_pos = text.find(start_marker)
        if start_pos == -1:
            start_pos = text.find(start_marker[:10])
        if start_pos == -1:
            print(f"  WARNING: Chapter '{title}' start_marker not found, skipping")
            continue

        # Find end position
        if end_marker:
            end_pos = text.find(end_marker, start_pos)
            if end_pos == -1:
                end_pos = text.find(end_marker[-10:], start_pos)
            if end_pos != -1:
                end_pos += len(end_marker)
            else:
                # Fallback: next chapter start or EOF
                if i + 1 < len(markers):
                    next_marker = markers[i + 1].get("start_marker", "")
                    next_pos = text.find(next_marker, start_pos + 1) if next_marker else -1
                    end_pos = next_pos if next_pos != -1 else len(text)
                else:
                    end_pos = len(text)
        else:
            if i + 1 < len(markers):
                next_marker = markers[i + 1].get("start_marker", "")
                next_pos = text.find(next_marker, start_pos + 1) if next_marker else -1
                end_pos = next_pos if next_pos != -1 else len(text)
            else:
                end_pos = len(text)

        content = text[start_pos:end_pos].strip()
        if content:
            chapters.append({
                "title": title,
                "content": content,
                "order": i,
            })

    return chapters


def dedupe_scenes(scenes):
    """Deduplicate scenes based on location + time_of_day + characters key."""
    seen = set()
    deduped = []
    for sc in scenes:
        loc = sc.get("location", "")
        tod = sc.get("time_of_day", "")
        chars = tuple(sorted(sc.get("characters_present", [])))
        key = (loc, tod, chars)
        if key not in seen:
            seen.add(key)
            deduped.append(sc)
        else:
            # Keep the one with more content
            deduped.append(sc)
    return deduped


# ── Pipeline stages ───────────────────────────────────────────────

summary_lines = []
summary_lines.append("=" * 70)
summary_lines.append("  《我和沈词的长子》 全流程 Pipeline 测试报告 (v2)")
summary_lines.append("=" * 70)
summary_lines.append(f"  小说长度: {len(NOVEL_TEXT)} 字")
summary_lines.append(f"  模型配置: fast=flash-lite, standard=pro-preview, image=flash-image")
summary_lines.append("")

all_ok = True

# ────────────────────────────────────────────────────────────────
# Stage 1: P01 — 章节分割 (marker-based)
# ────────────────────────────────────────────────────────────────
print("[1/10] P01_CHAPTER_SPLIT — 章节分割（标记模式）...")
try:
    markers, info = call_ai("P01_CHAPTER_SPLIT", text=NOVEL_TEXT)

    # Resolve markers to full chapter content
    chapters = resolve_markers(NOVEL_TEXT, markers)

    if not chapters:
        raise RuntimeError(f"Marker resolution failed. Got {len(markers)} markers but 0 resolved chapters.")

    total_chars = sum(len(ch["content"]) for ch in chapters)

    lines = []
    lines.append(f"模型: {info['model']}  |  耗时: {info['elapsed']}s")
    lines.append(f"AI返回标记数: {len(markers)}  |  成功解析章节: {len(chapters)}")
    lines.append(f"章节总字数: {total_chars}  |  原文总字数: {len(NOVEL_TEXT)}")
    lines.append(f"覆盖率: {total_chars/len(NOVEL_TEXT)*100:.1f}%")
    lines.append("")
    for i, ch in enumerate(chapters):
        title = ch.get("title", f"章节{i+1}")
        content = ch.get("content", "")
        lines.append(f"{'='*60}")
        lines.append(f"章节 {i+1}: {title}")
        lines.append(f"字数: {len(content)}")
        lines.append(f"{'='*60}")
        # Show first 300 and last 200 chars
        if len(content) > 600:
            lines.append(content[:300])
            lines.append(f"\n... [省略 {len(content)-500} 字] ...\n")
            lines.append(content[-200:])
        else:
            lines.append(content)
        lines.append("")

    save_result("01_章节分割.txt", "\n".join(lines))
    summary_lines.append(f"  [PASS] P01 章节分割 — {len(chapters)} 章, {total_chars}字, 覆盖{total_chars/len(NOVEL_TEXT)*100:.1f}%  |  {info['elapsed']}s  |  {info['model']}")
    print(f"  PASS: {len(chapters)} chapters, {total_chars} chars ({total_chars/len(NOVEL_TEXT)*100:.1f}% coverage)")
except Exception as e:
    all_ok = False
    save_result("01_章节分割.txt", f"FAIL: {e}\n{traceback.format_exc()}")
    summary_lines.append(f"  [FAIL] P01 章节分割 — {e}")
    print(f"  FAIL: {e}")
    chapters = None

# ────────────────────────────────────────────────────────────────
# Stage 2: P03 — 角色提取 (chunked to avoid pro model timeout)
# ────────────────────────────────────────────────────────────────
print("[2/10] P03_CHARACTER_EXTRACT — 角色提取（分段+合并）...")
try:
    # Split novel into ~6000 char chunks to stay within pro model limits
    CHUNK_SIZE = 6000
    OVERLAP = 500
    text_chunks = []
    pos = 0
    while pos < len(NOVEL_TEXT):
        end = min(pos + CHUNK_SIZE, len(NOVEL_TEXT))
        text_chunks.append(NOVEL_TEXT[pos:end])
        pos = end - OVERLAP if end < len(NOVEL_TEXT) else end

    all_characters = []
    for ci, chunk in enumerate(text_chunks):
        try:
            chars_chunk, info = call_ai("P03_CHARACTER_EXTRACT", text=chunk, delay=3)
            all_characters.extend(chars_chunk)
            print(f"  Chunk {ci+1}/{len(text_chunks)}: {len(chars_chunk)} characters  ({info['model']})")
        except Exception as chunk_err:
            print(f"  Chunk {ci+1}/{len(text_chunks)}: FAIL — {chunk_err}")

    # Deduplicate characters by name
    seen_names = {}
    characters = []
    for ch in all_characters:
        name = ch.get("name", "")
        if name and name not in seen_names:
            seen_names[name] = ch
            characters.append(ch)
        elif name and name in seen_names:
            # Merge: keep the one with more fields populated
            existing = seen_names[name]
            if not existing.get("appearance") and ch.get("appearance"):
                existing["appearance"] = ch["appearance"]
            if not existing.get("costume") and ch.get("costume"):
                existing["costume"] = ch["costume"]
            if not existing.get("visual_reference") and ch.get("visual_reference"):
                existing["visual_reference"] = ch["visual_reference"]

    lines = []
    lines.append(f"模型: {info['model']}  |  耗时: {info['elapsed']}s")
    lines.append(f"提取出 {len(characters)} 个角色")
    lines.append("")
    for ch in characters:
        lines.append(f"{'='*60}")
        lines.append(f"角色: {ch.get('name', '?')}  ({ch.get('role', '?')})")
        lines.append(f"{'='*60}")
        if ch.get("aliases"):
            lines.append(f"  别名: {', '.join(ch['aliases'])}")
        lines.append(f"  年龄: {ch.get('age_range', 'N/A')}")
        lines.append(f"  定位: {ch.get('description', 'N/A')}")
        lines.append(f"  性格: {ch.get('personality', 'N/A')}")
        lines.append(f"  欲望: {ch.get('desire', 'N/A')}")
        lines.append(f"  缺陷: {ch.get('flaw', 'N/A')}")
        lines.append(f"  弧线: {ch.get('arc', 'N/A')}")

        # Appearance
        appearance = ch.get("appearance", {})
        if appearance:
            lines.append(f"  ── 外观 ──")
            lines.append(f"    面部: {appearance.get('face', 'N/A')}")
            lines.append(f"    体型: {appearance.get('body', 'N/A')}")
            lines.append(f"    发型: {appearance.get('hair', 'N/A')}")
            lines.append(f"    辨识特征: {appearance.get('distinguishing_features', 'N/A')}")

        # Costume
        costume = ch.get("costume", {})
        if costume:
            lines.append(f"  ── 服装 ──")
            lines.append(f"    典型着装: {costume.get('typical_outfit', 'N/A')}")
            palette = costume.get("color_palette", [])
            if palette:
                lines.append(f"    色彩: {', '.join(palette)}")
            textures = costume.get("texture_keywords", [])
            if textures:
                lines.append(f"    材质: {', '.join(textures)}")

        # Casting & Visual
        tags = ch.get("casting_tags", [])
        if tags:
            lines.append(f"  选角标签: {', '.join(tags)}")
        vref = ch.get("visual_reference")
        if vref:
            lines.append(f"  AI绘图提示: {vref}")

        rels = ch.get("relationships", [])
        if rels:
            lines.append(f"  关系:")
            for r in rels:
                func = f" | 功能: {r['function']}" if r.get("function") else ""
                lines.append(f"    -> {r.get('target', '?')} [{r.get('type', '?')}]: {r.get('dynamic', '')}{func}")
        lines.append("")

    save_result("02_角色提取.txt", "\n".join(lines))
    char_names = [c.get("name", "?") for c in characters]
    has_appearance = sum(1 for c in characters if c.get("appearance"))
    summary_lines.append(f"  [PASS] P03 角色提取 — {len(characters)} 角色 ({has_appearance}有外观): {', '.join(char_names)}  |  {info['elapsed']}s  |  {info['model']}")
    print(f"  PASS: {len(characters)} characters ({has_appearance} with appearance): {', '.join(char_names)}")
except Exception as e:
    all_ok = False
    save_result("02_角色提取.txt", f"FAIL: {e}\n{traceback.format_exc()}")
    summary_lines.append(f"  [FAIL] P03 角色提取 — {e}")
    print(f"  FAIL: {e}")
    characters = None

# ────────────────────────────────────────────────────────────────
# Stage 3: P04 — 场景拆解 (ALL chapters)
# ────────────────────────────────────────────────────────────────
print("[3/10] P04_SCENE_EXTRACT — 场景拆解（全部章节）...")
all_scenes = []
try:
    if chapters and len(chapters) > 1:
        # Process ALL chapters
        for i, ch in enumerate(chapters):
            ch_text = ch.get("content", "")
            if len(ch_text) < 50:
                print(f"  Chapter {i+1}: skipped (too short)")
                continue
            try:
                scenes_chunk, info = call_ai("P04_SCENE_EXTRACT", text=ch_text, delay=3)
                for sc in scenes_chunk:
                    sc["source_chapter"] = ch.get("title", f"章节{i+1}")
                all_scenes.extend(scenes_chunk)
                print(f"  Chapter {i+1}/{len(chapters)}: {len(scenes_chunk)} scenes  ({info['model']})")
            except Exception as ch_err:
                print(f"  Chapter {i+1}/{len(chapters)}: FAIL — {ch_err}")
    else:
        # No chapter split — process full text in halves
        mid = len(NOVEL_TEXT) // 2
        scenes1, info = call_ai("P04_SCENE_EXTRACT", text=NOVEL_TEXT[:mid], delay=3)
        scenes2, info = call_ai("P04_SCENE_EXTRACT", text=NOVEL_TEXT[mid:])
        all_scenes = scenes1 + scenes2

    lines = []
    lines.append(f"场景总数: {len(all_scenes)}")
    lines.append("")
    for i, sc in enumerate(all_scenes):
        lines.append(f"{'='*60}")
        lines.append(f"场景 {i+1}: {sc.get('heading', '?')}")
        if sc.get("source_chapter"):
            lines.append(f"  来源章节: {sc['source_chapter']}")
        lines.append(f"{'='*60}")
        lines.append(f"  地点: {sc.get('location', 'N/A')}")
        lines.append(f"  时间: {sc.get('time_of_day', 'N/A')}")
        lines.append(f"  描述: {sc.get('description', 'N/A')}")
        lines.append(f"  动作: {sc.get('action', 'N/A')}")
        lines.append(f"  张力: {sc.get('tension_score', 'N/A')}")
        lines.append(f"  戏剧目的: {sc.get('dramatic_purpose', 'N/A')}")

        chars_present = sc.get("characters_present", [])
        if chars_present:
            lines.append(f"  在场角色: {', '.join(chars_present)}")

        key_props = sc.get("key_props", [])
        if key_props:
            lines.append(f"  关键道具: {', '.join(key_props)}")

        dialogues = sc.get("dialogue", [])
        if dialogues:
            lines.append(f"  对话:")
            for d in dialogues:
                lines.append(f"    {d.get('character', '?')}: {d.get('line', '')}")
                if d.get("subtext"):
                    lines.append(f"      (潜台词: {d['subtext']})")
        lines.append("")

    save_result("03_场景拆解.txt", "\n".join(lines))

    # Count chapters covered
    covered_chapters = set(sc.get("source_chapter", "") for sc in all_scenes if sc.get("source_chapter"))
    summary_lines.append(f"  [PASS] P04 场景拆解 — {len(all_scenes)} 场景, 覆盖 {len(covered_chapters)} 章")
    print(f"  PASS: {len(all_scenes)} scenes total, covering {len(covered_chapters)} chapters")
except Exception as e:
    all_ok = False
    save_result("03_场景拆解.txt", f"FAIL: {e}\n{traceback.format_exc()}")
    summary_lines.append(f"  [FAIL] P04 场景拆解 — {e}")
    print(f"  FAIL: {e}")

# ────────────────────────────────────────────────────────────────
# Stage 4: P10 — 节拍表 (full text, enhanced granularity)
# ────────────────────────────────────────────────────────────────
print("[4/10] P10_NOVEL_TO_BEAT — 节拍表（分段+合并）...")
try:
    # Process in chunks using chapters if available
    all_beats = []
    if chapters and len(chapters) > 1:
        # Group chapters into ~6000 char segments
        segments = []
        current_seg = ""
        for ch in chapters:
            content = ch.get("content", "")
            if len(current_seg) + len(content) > 6000 and current_seg:
                segments.append(current_seg)
                current_seg = content
            else:
                current_seg += "\n\n" + content if current_seg else content
        if current_seg:
            segments.append(current_seg)

        for si, seg in enumerate(segments):
            try:
                beats_chunk, info = call_ai("P10_NOVEL_TO_BEAT", text=seg, delay=3)
                # Offset order values
                offset = len(all_beats)
                for b in beats_chunk:
                    b["order"] = b.get("order", 0) + offset
                all_beats.extend(beats_chunk)
                print(f"  Segment {si+1}/{len(segments)}: {len(beats_chunk)} beats  ({info['model']})")
            except Exception as seg_err:
                print(f"  Segment {si+1}/{len(segments)}: FAIL — {seg_err}")
    else:
        # Fallback: split by character count
        mid = len(NOVEL_TEXT) // 2
        beats1, info = call_ai("P10_NOVEL_TO_BEAT", text=NOVEL_TEXT[:mid], delay=3)
        beats2, info = call_ai("P10_NOVEL_TO_BEAT", text=NOVEL_TEXT[mid:])
        offset = len(beats1)
        for b in beats2:
            b["order"] = b.get("order", 0) + offset
        all_beats = beats1 + beats2

    beats = all_beats

    lines = []
    lines.append(f"模型: {info['model']}  |  耗时: {info['elapsed']}s")
    lines.append(f"节拍总数: {len(beats)}")
    lines.append("")

    # Check Save the Cat coverage
    stc_types = set(b.get("save_the_cat", "N/A") for b in beats if b.get("save_the_cat") != "N/A")
    lines.append(f"Save the Cat 覆盖: {len(stc_types)} 类型")
    lines.append(f"  已覆盖: {', '.join(sorted(stc_types))}")
    lines.append("")

    # Check rhythm warnings
    warnings = [b for b in beats if b.get("rhythm_warning") and b["rhythm_warning"] != "false"]
    if warnings:
        lines.append(f"节奏预警: {len(warnings)} 处")
        lines.append("")

    for i, b in enumerate(beats):
        lines.append(f"{'─'*50}")
        lines.append(f"节拍 {i+1}: {b.get('title', '?')}")
        lines.append(f"  类型: {b.get('beat_type', 'N/A')}")
        lines.append(f"  Save the Cat: {b.get('save_the_cat', 'N/A')}")
        lines.append(f"  情感值: {b.get('emotional_value', 'N/A')}")
        lines.append(f"  钩子潜力: {b.get('hook_potential', 'N/A')}")
        rw = b.get("rhythm_warning", "false")
        if rw and rw != "false":
            lines.append(f"  ⚠ 节奏预警: {rw}")
        lines.append(f"  描述: {b.get('description', 'N/A')}")
        lines.append("")

    save_result("04_节拍表.txt", "\n".join(lines))
    summary_lines.append(f"  [PASS] P10 节拍表 — {len(beats)} 节拍, {len(stc_types)} STC类型  |  {info['elapsed']}s  |  {info['model']}")
    print(f"  PASS: {len(beats)} beats, {len(stc_types)} Save the Cat types")
except Exception as e:
    all_ok = False
    save_result("04_节拍表.txt", f"FAIL: {e}\n{traceback.format_exc()}")
    summary_lines.append(f"  [FAIL] P10 节拍表 — {e}")
    print(f"  FAIL: {e}")

# ────────────────────────────────────────────────────────────────
# Stage 5: P05 — 知识库 (with segment merge for long texts)
# ────────────────────────────────────────────────────────────────
print("[5/10] P05_KNOWLEDGE_BASE — 知识库构建...")
try:
    text_len = len(NOVEL_TEXT)

    if text_len < 6000:
        # Short text: single call
        knowledge, info = call_ai("P05_KNOWLEDGE_BASE", text=NOVEL_TEXT)
    else:
        # Split into ~6000 char segments to avoid pro model timeout
        segment_size = min(6000, text_len // 2 + 500)
        seg1 = NOVEL_TEXT[:segment_size]
        seg2 = NOVEL_TEXT[segment_size - 500:]

        print(f"  Long text ({text_len} chars), processing in 2 segments...")
        knowledge1, info1 = call_ai("P05_KNOWLEDGE_BASE", text=seg1, delay=3)
        knowledge2, info2 = call_ai("P05_KNOWLEDGE_BASE", text=seg2, delay=2)
        info = info2  # Use last call's info

        # Merge: keep first segment's world_building and style_guide, merge locations
        knowledge = knowledge1
        locs1 = knowledge1.get("locations", [])
        locs2 = knowledge2.get("locations", [])

        # Deduplicate locations by name
        seen_names = set(loc.get("name", "") for loc in locs1)
        for loc in locs2:
            name = loc.get("name", "")
            if name and name not in seen_names:
                locs1.append(loc)
                seen_names.add(name)
        knowledge["locations"] = locs1

    lines = []
    lines.append(f"模型: {info['model']}  |  耗时: {info['elapsed']}s")
    lines.append(f"文本长度: {text_len} 字  |  处理策略: {'分段合并' if text_len >= 15000 else '单次调用'}")
    lines.append("")

    wb = knowledge.get("world_building", {})
    lines.append("=" * 60)
    lines.append("【世界观】")
    lines.append("=" * 60)
    lines.append(f"  设定: {wb.get('setting', 'N/A')}")
    lines.append(f"  时代: {wb.get('era', 'N/A')}")
    lines.append(f"  规则: {wb.get('rules', 'N/A')}")
    lines.append(f"  冲突触发: {wb.get('conflict_triggers', 'N/A')}")
    lines.append(f"  基调: {wb.get('tone', 'N/A')}")
    lines.append(f"  主题: {wb.get('themes', 'N/A')}")
    lines.append("")

    sg = knowledge.get("style_guide", {})
    lines.append("=" * 60)
    lines.append("【风格指南】")
    lines.append("=" * 60)
    lines.append(f"  视角: {sg.get('pov', 'N/A')}")
    lines.append(f"  时态: {sg.get('tense', 'N/A')}")
    lines.append(f"  文风: {sg.get('voice', 'N/A')}")
    lines.append(f"  体裁: {sg.get('genre', 'N/A')}")
    lines.append(f"  视觉基调: {sg.get('visual_tone', 'N/A')}")
    lines.append(f"  节奏DNA: {sg.get('pacing_dna', 'N/A')}")
    lines.append("")

    locs = knowledge.get("locations", [])
    lines.append("=" * 60)
    lines.append(f"【场景地理】({len(locs)} 个地点)")
    lines.append("=" * 60)
    for loc in locs:
        lines.append(f"  ● {loc.get('name', '?')}")
        lines.append(f"    描述: {loc.get('description', 'N/A')}")
        lines.append(f"    视觉: {loc.get('visual_description', 'N/A')}")
        lines.append(f"    感官: {loc.get('sensory', 'N/A')}")
        lines.append(f"    氛围: {loc.get('mood', 'N/A')}")
        lines.append(f"    功能: {loc.get('narrative_function', 'N/A')}")
        lines.append("")

    save_result("05_知识库.txt", "\n".join(lines))
    summary_lines.append(f"  [PASS] P05 知识库 — {len(locs)} 地点  |  {info['elapsed']}s  |  {info['model']}")
    print(f"  PASS: {len(locs)} locations")
except Exception as e:
    all_ok = False
    save_result("05_知识库.txt", f"FAIL: {e}\n{traceback.format_exc()}")
    summary_lines.append(f"  [FAIL] P05 知识库 — {e}")
    print(f"  FAIL: {e}")

# ────────────────────────────────────────────────────────────────
# Stage 6: PS04 — 视觉可执行性评估 (ALL scenes)
# ────────────────────────────────────────────────────────────────
print("[6/10] PS04_VISUAL_READINESS — 视觉评估（全部场景）...")
try:
    if all_scenes:
        # Limit scenes to avoid pro model timeout (max ~10 scenes per call)
        scenes_for_eval = all_scenes[:10]
        scenes_json = json.dumps(scenes_for_eval, ensure_ascii=False)
        visual, info = call_ai("PS04_VISUAL_READINESS", text=scenes_json)

        lines = []
        lines.append(f"模型: {info['model']}  |  耗时: {info['elapsed']}s")
        lines.append(f"评估场景数: {len(scenes_for_eval)} / {len(all_scenes)}")
        lines.append("")
        lines.append(f"整体评分: {visual.get('overall_score', 'N/A')}")
        lines.append(f"整体评估: {visual.get('overall_assessment', 'N/A')}")
        lines.append("")

        for sc in visual.get("scenes", []):
            lines.append(f"{'─'*50}")
            lines.append(f"场景: {sc.get('scene_id', '?')}  —  评分: {sc.get('score', '?')}")
            strengths = sc.get("strengths", [])
            if strengths:
                lines.append(f"  优势: {', '.join(strengths[:3])}")
            missing = sc.get("missing", [])
            if missing:
                lines.append(f"  缺失: {', '.join(missing[:3])}")
            fixes = sc.get("fix_suggestions", [])
            if fixes:
                lines.append(f"  建议: {fixes[0]}")
            lines.append("")

        recs = visual.get("recommendations", [])
        if recs:
            lines.append("全局建议:")
            for r in recs:
                lines.append(f"  • {r}")

        save_result("06_视觉评估.txt", "\n".join(lines))
        summary_lines.append(f"  [PASS] PS04 视觉评估 — {len(scenes_for_eval)}/{len(all_scenes)}场景, 总分: {visual.get('overall_score', 'N/A')}  |  {info['elapsed']}s")
        print(f"  PASS: {len(scenes_for_eval)}/{len(all_scenes)} scenes evaluated, score={visual.get('overall_score', 'N/A')}")
    else:
        raise RuntimeError("No scenes data from Stage 3")
except Exception as e:
    all_ok = False
    save_result("06_视觉评估.txt", f"FAIL: {e}\n{traceback.format_exc()}")
    summary_lines.append(f"  [FAIL] PS04 视觉评估 — {e}")
    print(f"  FAIL: {e}")

# ────────────────────────────────────────────────────────────────
# Stage 7: PS05 — 分镜优化 (more scenes)
# ────────────────────────────────────────────────────────────────
print("[7/10] PS05_STORYBOARD_OPTIMIZE — 分镜优化...")
try:
    if all_scenes:
        # Process up to 6 scenes
        scenes_to_optimize = all_scenes[:6]
        scenes_json = json.dumps(scenes_to_optimize, ensure_ascii=False)
        optimized, info = call_ai("PS05_STORYBOARD_OPTIMIZE", text=scenes_json)

        lines = []
        lines.append(f"模型: {info['model']}  |  耗时: {info['elapsed']}s")
        lines.append(f"优化场景数: {len(optimized)}")
        lines.append("")

        for i, sc in enumerate(optimized):
            lines.append(f"{'='*60}")
            lines.append(f"场景 {i+1}: {sc.get('heading', '?')}")
            lines.append(f"{'='*60}")
            lines.append(f"  地点: {sc.get('location', 'N/A')}")
            lines.append(f"  时间: {sc.get('time_of_day', 'N/A')}")
            lines.append(f"  描述: {sc.get('description', 'N/A')}")
            lines.append(f"  动作: {sc.get('action', 'N/A')}")
            lines.append(f"  张力: {sc.get('tension_score', 'N/A')}")
            dialogues = sc.get("dialogue", [])
            if dialogues:
                lines.append(f"  对话:")
                for d in dialogues:
                    lines.append(f"    {d.get('character', '?')}: {d.get('line', '')}")
                    if d.get("parallel_action"):
                        lines.append(f"      [动作: {d['parallel_action']}]")
            vn = sc.get("visual_notes", {})
            if vn:
                lines.append(f"  ── 视觉笔记 ──")
                shots = vn.get("shot_suggestions", [])
                if shots:
                    lines.append(f"    镜头建议: {'; '.join(shots[:3])}")
                lines.append(f"    情绪曲线: {vn.get('emotional_curve', 'N/A')}")
                lines.append(f"    转场入: {vn.get('transition_in', 'N/A')}")
                lines.append(f"    转场出: {vn.get('transition_out', 'N/A')}")
                lines.append(f"    声音设计: {vn.get('sound_design', 'N/A')}")
                lines.append(f"    核心视觉: {vn.get('key_visual', 'N/A')}")
            lines.append("")

        save_result("07_分镜优化.txt", "\n".join(lines))
        has_vn = any("visual_notes" in s for s in optimized)
        summary_lines.append(f"  [PASS] PS05 分镜优化 — {len(optimized)} 场景, visual_notes={'有' if has_vn else '无'}  |  {info['elapsed']}s")
        print(f"  PASS: {len(optimized)} optimized scenes")
    else:
        raise RuntimeError("No scenes data from Stage 3")
except Exception as e:
    all_ok = False
    save_result("07_分镜优化.txt", f"FAIL: {e}\n{traceback.format_exc()}")
    summary_lines.append(f"  [FAIL] PS05 分镜优化 — {e}")
    print(f"  FAIL: {e}")

# ────────────────────────────────────────────────────────────────
# Stage 8: P12 — AI 改写 (pick a paragraph from the novel)
# ────────────────────────────────────────────────────────────────
print("[8/10] P12_REWRITE — AI 改写...")
try:
    sample_para = "我和沈词的长子成了一代名相。是以双双重生后，哪怕我们相看两厌，还是捏着鼻子订了亲。他救回了落水早亡的青梅，认作义妹，极尽疼爱。我也改变了家破人亡的命运，重振门楣。"
    prompt = render_prompt("P12_REWRITE", text=sample_para, operation="改写",
                          context="场景：古风重生文，女主视角，冷静克制但内心翻涌。要求增强画面感和情感张力。")
    start = time.time()
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    elapsed = time.time() - start
    content = result["content"]
    time.sleep(2)

    lines = []
    lines.append(f"模型: {result['model']}  |  耗时: {round(elapsed, 1)}s")
    lines.append("")
    lines.append("【原文】")
    lines.append(sample_para)
    lines.append("")
    lines.append("【改写结果】")
    lines.append(content)

    save_result("08_AI改写.txt", "\n".join(lines))
    summary_lines.append(f"  [PASS] P12 AI改写 — {len(content)} 字  |  {round(elapsed, 1)}s  |  {result['model']}")
    print(f"  PASS: {len(content)} chars")
except Exception as e:
    all_ok = False
    save_result("08_AI改写.txt", f"FAIL: {e}\n{traceback.format_exc()}")
    summary_lines.append(f"  [FAIL] P12 AI改写 — {e}")
    print(f"  FAIL: {e}")

# ────────────────────────────────────────────────────────────────
# Stage 9: PS01 — 格式检测 (treat novel as script input)
# ────────────────────────────────────────────────────────────────
print("[9/10] PS01_FORMAT_DETECT — 格式检测...")
try:
    fmt, info = call_ai("PS01_FORMAT_DETECT", text=NOVEL_TEXT[:2000])

    lines = []
    lines.append(f"模型: {info['model']}  |  耗时: {info['elapsed']}s")
    lines.append("")
    lines.append(f"检测格式: {fmt.get('format', 'N/A')}")
    lines.append(f"置信度: {fmt.get('confidence', 'N/A')}")
    lines.append(f"详情: {fmt.get('details', 'N/A')}")

    save_result("09_格式检测.txt", "\n".join(lines))
    summary_lines.append(f"  [PASS] PS01 格式检测 — {fmt.get('format', '?')} ({fmt.get('confidence', '?')})  |  {info['elapsed']}s  |  {info['model']}")
    print(f"  PASS: {fmt.get('format', '?')} ({fmt.get('confidence', '?')})")
except Exception as e:
    all_ok = False
    save_result("09_格式检测.txt", f"FAIL: {e}\n{traceback.format_exc()}")
    summary_lines.append(f"  [FAIL] PS01 格式检测 — {e}")
    print(f"  FAIL: {e}")

# ────────────────────────────────────────────────────────────────
# Stage 10: Streaming 测试
# ────────────────────────────────────────────────────────────────
print("[10/10] Streaming — 流式输出测试...")
try:
    prompt = render_prompt("P01_CHAPTER_SPLIT", text=NOVEL_TEXT[:1000])
    chunks = []
    start = time.time()
    for chunk in ai_engine.stream(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    ):
        chunks.append(chunk)
    elapsed = time.time() - start
    full_text = "".join(chunks)

    lines = []
    lines.append(f"耗时: {round(elapsed, 1)}s")
    lines.append(f"分块数: {len(chunks)}")
    lines.append(f"总字符: {len(full_text)}")
    lines.append("")
    lines.append("【流式输出内容】")
    lines.append(full_text)

    save_result("10_流式测试.txt", "\n".join(lines))
    summary_lines.append(f"  [PASS] Streaming — {len(chunks)} chunks, {len(full_text)} chars  |  {round(elapsed, 1)}s")
    print(f"  PASS: {len(chunks)} chunks, {len(full_text)} chars")
except Exception as e:
    all_ok = False
    save_result("10_流式测试.txt", f"FAIL: {e}\n{traceback.format_exc()}")
    summary_lines.append(f"  [FAIL] Streaming — {e}")
    print(f"  FAIL: {e}")

# ── Cleanup ──────────────────────────────────────────────────────
db.query(AIProvider).filter(AIProvider.name == "_novel_pipeline").delete()
db.commit()
db.close()
ai_engine.invalidate_cache()

# ── Summary ─────────────────────────────────────────────────────
summary_lines.append("")
summary_lines.append("=" * 70)
summary_lines.append(f"  总结: {'ALL PASS — 全部通过' if all_ok else 'FAIL — 存在失败项'}")
summary_lines.append("=" * 70)

summary_text = "\n".join(summary_lines)
save_result("00_测试总结.txt", summary_text)

# Clean up temp files
for f in ["_preview.txt", "我和沈词的长子_utf8.txt"]:
    p = os.path.join(OUTPUT_DIR, f)
    if os.path.exists(p):
        os.remove(p)

print()
print(summary_text)
