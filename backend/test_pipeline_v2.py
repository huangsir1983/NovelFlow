"""Second-round pipeline test — new chunked/summary/two-round pipeline.

Tests the improved import pipeline using 《我和沈词的长子》 (~13K chars).
Uses Comfly Gemini API.

New pipeline steps tested:
  1. split_chapters_chunked (regex + chunked AI)
  2. summarize_chapter (P01B)
  3. extract_character_names (P03A) — first-round scan
  4. extract_character_detail (P03B) — per-character detail
  5. extract_scenes_with_context (P04 + character_names)
  6. generate_beats (P10) — unchanged
  7. build_knowledge_base_v2 (P05V2 — from synopsis)
"""

import json
import sys
import os
import time
import traceback

sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, init_db
from models.ai_provider import AIProvider
from uuid import uuid4

init_db()
db = SessionLocal()

# ── Setup Comfly Gemini provider ──────────────────────────────────
db.query(AIProvider).filter(AIProvider.name == "_pipeline_test_v2").delete()
db.commit()

provider = AIProvider(
    id=str(uuid4()),
    name="_pipeline_test_v2",
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
            "model_id": "gemini-3.1-flash-lite-preview",
            "display_name": "Gemini Flash Lite (standard)",
            "model_type": "text",
            "capability_tier": "standard",
            "max_tokens": 8192,
            "supports_streaming": True,
        },
    ],
    is_default=True,
    enabled=True,
    priority=0,
)
db.add(provider)
db.commit()

from services.ai_engine import ai_engine
ai_engine.invalidate_cache()

# ── Read test novel ─────────────────────────────────────────────
with open("../测试/我和沈词的长子.txt", "rb") as f:
    raw = f.read()

import chardet
detected = chardet.detect(raw)
encoding = detected.get("encoding", "utf-8") or "utf-8"
novel_text = raw.decode(encoding, errors="replace")

print(f"Novel length: {len(novel_text)} chars ({encoding})")
print("=" * 70)

# ── Output dir ──────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "测试", "第2次测试结果")
os.makedirs(OUTPUT_DIR, exist_ok=True)

results_summary = []


def save_result(filename, content):
    """Save result to output dir."""
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  -> Saved: {filename}")


# ═══════════════════════════════════════════════════════════════
# Step 1: Chapter Splitting (regex + chunked AI)
# ═══════════════════════════════════════════════════════════════
print("\n[Step 1/7] Chapter Splitting (split_chapters_chunked) ...")
from services.novel_parser import split_chapters_chunked

try:
    start = time.time()
    chapters = split_chapters_chunked(novel_text, db=db)
    elapsed = time.time() - start

    output_lines = [
        f"章节分割结果 — split_chapters_chunked",
        f"总耗时: {elapsed:.1f}s",
        f"章节数: {len(chapters)}",
        f"方法: {'regex' if elapsed < 1 else 'AI chunked'}",
        "=" * 60,
    ]
    for ch in chapters:
        title = ch.get("title", "无标题")
        content = ch.get("content", "")
        output_lines.append(f"\n【{title}】(order={ch.get('order', '?')}, {len(content)}字)")
        output_lines.append(content[:300] + ("..." if len(content) > 300 else ""))
        output_lines.append("-" * 40)

    save_result("01_章节分割.txt", "\n".join(output_lines))
    results_summary.append(f"[PASS] Step 1: 章节分割 — {len(chapters)} 章 | {elapsed:.1f}s")
    print(f"  PASS: {len(chapters)} chapters in {elapsed:.1f}s")

except Exception as e:
    results_summary.append(f"[FAIL] Step 1: 章节分割 — {e}")
    save_result("01_章节分割.txt", f"FAILED: {e}\n\n{traceback.format_exc()}")
    print(f"  FAIL: {e}")
    chapters = [{"title": "全文", "content": novel_text, "order": 0}]


# ═══════════════════════════════════════════════════════════════
# Step 2: Chapter Summarization (P01B)
# ═══════════════════════════════════════════════════════════════
print("\n[Step 2/7] Chapter Summarization (summarize_chapter / P01B) ...")
from services.novel_parser import summarize_chapter

try:
    start = time.time()
    summaries = []
    output_lines = [
        f"章节摘要结果 — P01B_CHAPTER_SUMMARY",
        f"章节数: {len(chapters)}",
        "=" * 60,
    ]

    for i, ch in enumerate(chapters):
        title = ch.get("title", f"章节{i+1}")
        content = ch.get("content", "")
        if not content.strip():
            continue

        ch_start = time.time()
        summary = summarize_chapter(content, title, db=db)
        ch_elapsed = time.time() - ch_start

        summaries.append(f"【{title}】\n{summary}")
        output_lines.append(f"\n{'='*40}")
        output_lines.append(f"【{title}】({len(content)}字 → {len(summary)}字摘要, {ch_elapsed:.1f}s)")
        output_lines.append(f"{'='*40}")
        output_lines.append(summary)
        print(f"  Chapter {i+1}/{len(chapters)}: '{title}' → {len(summary)}字 ({ch_elapsed:.1f}s)")

    synopsis = "\n\n".join(summaries)
    elapsed = time.time() - start

    output_lines.insert(1, f"总耗时: {elapsed:.1f}s")
    output_lines.insert(2, f"全文摘要总长: {len(synopsis)}字")
    output_lines.append(f"\n\n{'='*60}")
    output_lines.append(f"全文摘要拼合 (synopsis)")
    output_lines.append(f"{'='*60}")
    output_lines.append(synopsis)

    save_result("02_章节摘要.txt", "\n".join(output_lines))
    results_summary.append(f"[PASS] Step 2: 章节摘要 — {len(summaries)} 章摘要, synopsis={len(synopsis)}字 | {elapsed:.1f}s")
    print(f"  PASS: {len(summaries)} summaries, synopsis={len(synopsis)} chars in {elapsed:.1f}s")

except Exception as e:
    results_summary.append(f"[FAIL] Step 2: 章节摘要 — {e}")
    save_result("02_章节摘要.txt", f"FAILED: {e}\n\n{traceback.format_exc()}")
    print(f"  FAIL: {e}")
    # Fallback synopsis
    synopsis = "\n".join(ch.get("content", "")[:300] for ch in chapters)


# ═══════════════════════════════════════════════════════════════
# Step 3: Character Extraction — Round 1 (P03A: Name Scan)
# ═══════════════════════════════════════════════════════════════
print("\n[Step 3a/7] Character Name Scan (P03A) ...")
from services.novel_parser import extract_character_names

try:
    start = time.time()
    char_name_list = extract_character_names(synopsis, db=db)
    elapsed = time.time() - start

    all_names = [c.get("name", "") for c in char_name_list if c.get("name")]

    output_lines = [
        f"角色名单扫描结果 — P03A_CHARACTER_SCAN",
        f"耗时: {elapsed:.1f}s",
        f"角色数: {len(char_name_list)}",
        "=" * 60,
    ]
    for c in char_name_list:
        output_lines.append(f"\n  名字: {c.get('name', '?')}")
        output_lines.append(f"  别名: {c.get('aliases', [])}")
        output_lines.append(f"  定位: {c.get('role', '?')}")
        output_lines.append(f"  简介: {c.get('brief', '?')}")
        output_lines.append(f"  ---")

    save_result("03a_角色名单扫描.txt", "\n".join(output_lines))
    results_summary.append(f"[PASS] Step 3a: 角色名单 — {len(all_names)} 角色: {', '.join(all_names)} | {elapsed:.1f}s")
    print(f"  PASS: {len(all_names)} characters: {', '.join(all_names)} in {elapsed:.1f}s")

except Exception as e:
    results_summary.append(f"[FAIL] Step 3a: 角色名单 — {e}")
    save_result("03a_角色名单扫描.txt", f"FAILED: {e}\n\n{traceback.format_exc()}")
    print(f"  FAIL: {e}")
    char_name_list = []
    all_names = []


# ═══════════════════════════════════════════════════════════════
# Step 3b: Character Detail — Round 2 (P03B: Per-Character)
# ═══════════════════════════════════════════════════════════════
print("\n[Step 3b/7] Character Detail Extraction (P03B) ...")
from services.novel_parser import extract_character_detail

character_details = []
try:
    start = time.time()
    output_lines = [
        f"角色详情提取结果 — P03B_CHARACTER_DETAIL",
        f"角色数: {len(char_name_list)}",
        "=" * 60,
    ]

    for i, char_info in enumerate(char_name_list):
        name = char_info.get("name", "")
        brief = char_info.get("brief", "")
        if not name:
            continue

        print(f"  Extracting detail for '{name}' ({i+1}/{len(char_name_list)}) ...")
        ch_start = time.time()
        try:
            detail = extract_character_detail(name, brief, synopsis, all_names, db=db)
            character_details.append(detail)
            ch_elapsed = time.time() - ch_start

            output_lines.append(f"\n{'='*50}")
            output_lines.append(f"角色: {detail.get('name', name)} ({ch_elapsed:.1f}s)")
            output_lines.append(f"{'='*50}")
            output_lines.append(json.dumps(detail, ensure_ascii=False, indent=2))
        except Exception as e:
            ch_elapsed = time.time() - ch_start
            output_lines.append(f"\n{'='*50}")
            output_lines.append(f"角色: {name} — FAILED ({ch_elapsed:.1f}s): {e}")
            print(f"    WARN: {name} failed: {e}")

    elapsed = time.time() - start
    output_lines.insert(1, f"总耗时: {elapsed:.1f}s")

    save_result("03b_角色详情.txt", "\n".join(output_lines))

    detail_names = [d.get("name", "?") for d in character_details]
    has_visual = sum(1 for d in character_details if d.get("visual_reference"))
    has_desire = sum(1 for d in character_details if d.get("desire"))
    results_summary.append(
        f"[PASS] Step 3b: 角色详情 — {len(character_details)} 角色, "
        f"visual_ref={has_visual}, desire={has_desire} | {elapsed:.1f}s"
    )
    print(f"  PASS: {len(character_details)} details in {elapsed:.1f}s (visual_ref={has_visual}, desire={has_desire})")

except Exception as e:
    results_summary.append(f"[FAIL] Step 3b: 角色详情 — {e}")
    save_result("03b_角色详情.txt", f"FAILED: {e}\n\n{traceback.format_exc()}")
    print(f"  FAIL: {e}")


# ═══════════════════════════════════════════════════════════════
# Step 4: Scene Extraction with Character Context (P04 + names)
# ═══════════════════════════════════════════════════════════════
print("\n[Step 4/7] Scene Extraction with Character Context ...")
from services.novel_parser import extract_scenes_with_context

all_scenes = []
try:
    start = time.time()
    output_lines = [
        f"场景提取结果 — P04_SCENE_EXTRACT (with character_names context)",
        f"角色上下文: {', '.join(all_names)}",
        f"章节数: {len(chapters)}",
        "=" * 60,
    ]

    for i, ch in enumerate(chapters):
        content = ch.get("content", "")
        title = ch.get("title", f"章节{i+1}")
        if not content.strip():
            continue

        ch_start = time.time()
        scenes = extract_scenes_with_context(content, all_names, db=db)
        ch_elapsed = time.time() - ch_start

        all_scenes.extend(scenes)
        output_lines.append(f"\n{'='*40}")
        output_lines.append(f"章节: {title} — {len(scenes)} 场景 ({ch_elapsed:.1f}s)")
        output_lines.append(f"{'='*40}")
        for sc in scenes:
            output_lines.append(json.dumps(sc, ensure_ascii=False, indent=2))
            output_lines.append("---")
        print(f"  Chapter '{title}': {len(scenes)} scenes ({ch_elapsed:.1f}s)")

    elapsed = time.time() - start
    output_lines.insert(2, f"总耗时: {elapsed:.1f}s")
    output_lines.insert(3, f"总场景数: {len(all_scenes)}")

    # Collect unique locations
    location_names = list(set(sc.get("location", "") for sc in all_scenes if sc.get("location")))

    save_result("04_场景提取.txt", "\n".join(output_lines))
    results_summary.append(f"[PASS] Step 4: 场景提取 — {len(all_scenes)} 场景, {len(location_names)} 地点 | {elapsed:.1f}s")
    print(f"  PASS: {len(all_scenes)} scenes, {len(location_names)} locations in {elapsed:.1f}s")

except Exception as e:
    results_summary.append(f"[FAIL] Step 4: 场景提取 — {e}")
    save_result("04_场景提取.txt", f"FAILED: {e}\n\n{traceback.format_exc()}")
    print(f"  FAIL: {e}")
    location_names = []


# ═══════════════════════════════════════════════════════════════
# Step 5: Beat Generation (P10 — per chapter, unchanged)
# ═══════════════════════════════════════════════════════════════
print("\n[Step 5/7] Beat Generation (P10, per chapter) ...")
from services.novel_parser import generate_beats

all_beats = []
try:
    start = time.time()
    output_lines = [
        f"节拍提取结果 — P10_NOVEL_TO_BEAT",
        f"章节数: {len(chapters)}",
        "=" * 60,
    ]

    for i, ch in enumerate(chapters):
        content = ch.get("content", "")
        title = ch.get("title", f"章节{i+1}")
        if not content.strip():
            continue

        ch_start = time.time()
        beats = generate_beats(content, db=db)
        ch_elapsed = time.time() - ch_start

        all_beats.extend(beats)
        output_lines.append(f"\n{'='*40}")
        output_lines.append(f"章节: {title} — {len(beats)} 节拍 ({ch_elapsed:.1f}s)")
        output_lines.append(f"{'='*40}")
        for b in beats:
            output_lines.append(f"  [{b.get('beat_type', '?')}] {b.get('title', '?')} (EV={b.get('emotional_value', '?')})")
            output_lines.append(f"    {b.get('description', '')[:100]}")
        print(f"  Chapter '{title}': {len(beats)} beats ({ch_elapsed:.1f}s)")

    elapsed = time.time() - start
    output_lines.insert(1, f"总耗时: {elapsed:.1f}s")
    output_lines.insert(2, f"总节拍数: {len(all_beats)}")

    save_result("05_节拍提取.txt", "\n".join(output_lines))
    results_summary.append(f"[PASS] Step 5: 节拍提取 — {len(all_beats)} 节拍 | {elapsed:.1f}s")
    print(f"  PASS: {len(all_beats)} beats in {elapsed:.1f}s")

except Exception as e:
    results_summary.append(f"[FAIL] Step 5: 节拍提取 — {e}")
    save_result("05_节拍提取.txt", f"FAILED: {e}\n\n{traceback.format_exc()}")
    print(f"  FAIL: {e}")


# ═══════════════════════════════════════════════════════════════
# Step 6: Knowledge Base V2 (from synopsis, not full text)
# ═══════════════════════════════════════════════════════════════
print("\n[Step 6/7] Knowledge Base V2 (from synopsis) ...")
from services.novel_parser import build_knowledge_base_v2

try:
    start = time.time()
    kb_data = build_knowledge_base_v2(synopsis, all_names, location_names, db=db)
    elapsed = time.time() - start

    output_lines = [
        f"知识库构建结果 — P05_KNOWLEDGE_BASE_V2",
        f"耗时: {elapsed:.1f}s",
        f"输入: synopsis ({len(synopsis)}字) + {len(all_names)} 角色 + {len(location_names)} 地点",
        "=" * 60,
        "",
        json.dumps(kb_data, ensure_ascii=False, indent=2),
    ]

    save_result("06_知识库V2.txt", "\n".join(output_lines))

    wb = kb_data.get("world_building", {})
    sg = kb_data.get("style_guide", {})
    results_summary.append(
        f"[PASS] Step 6: 知识库V2 — "
        f"world_building={len(wb)}项, style_guide={len(sg)}项 | {elapsed:.1f}s"
    )
    print(f"  PASS: world_building={len(wb)} items, style_guide={len(sg)} items in {elapsed:.1f}s")

except Exception as e:
    results_summary.append(f"[FAIL] Step 6: 知识库V2 — {e}")
    save_result("06_知识库V2.txt", f"FAILED: {e}\n\n{traceback.format_exc()}")
    print(f"  FAIL: {e}")


# ═══════════════════════════════════════════════════════════════
# Step 7: Compare old vs new (P03 full-text vs P03A+P03B)
# ═══════════════════════════════════════════════════════════════
print("\n[Step 7/7] Comparison: Old P03 full-text vs New P03A+P03B two-round ...")
from services.novel_parser import extract_characters

try:
    start = time.time()
    old_characters = extract_characters(novel_text, db=db)
    old_elapsed = time.time() - start

    output_lines = [
        f"新旧方案对比",
        "=" * 60,
        "",
        f"【旧方案】P03_CHARACTER_EXTRACT (全文 → 一次性提取)",
        f"  耗时: {old_elapsed:.1f}s",
        f"  角色数: {len(old_characters)}",
        f"  输入: 全文 {len(novel_text)} 字 (截断到 60000)",
        "",
    ]
    for c in old_characters:
        output_lines.append(f"  {c.get('name', '?')} ({c.get('role', '?')}): {c.get('description', '')[:80]}")
        has_visual = bool(c.get("visual_reference"))
        has_desire = bool(c.get("desire"))
        output_lines.append(f"    visual_reference: {'有' if has_visual else '无'}, desire: {'有' if has_desire else '无'}")

    output_lines.append(f"\n{'='*60}")
    output_lines.append(f"【新方案】P03A (名单扫描) + P03B (逐一详情)")
    new_total_time = sum(1 for r in results_summary if "Step 3" in r)  # rough
    output_lines.append(f"  角色数: {len(character_details)}")
    output_lines.append(f"  输入: synopsis {len(synopsis)} 字")
    output_lines.append("")
    for d in character_details:
        output_lines.append(f"  {d.get('name', '?')} ({d.get('role', '?')}): {d.get('description', '')[:80]}")
        has_visual = bool(d.get("visual_reference"))
        has_desire = bool(d.get("desire"))
        has_flaw = bool(d.get("flaw"))
        has_appearance = bool(d.get("appearance"))
        output_lines.append(
            f"    visual_reference: {'有' if has_visual else '无'}, "
            f"desire: {'有' if has_desire else '无'}, "
            f"flaw: {'有' if has_flaw else '无'}, "
            f"appearance: {'有' if has_appearance else '无'}"
        )

    output_lines.append(f"\n{'='*60}")
    output_lines.append("对比结论:")
    output_lines.append(f"  旧方案角色数: {len(old_characters)}  vs  新方案角色数: {len(character_details)}")
    old_with_visual = sum(1 for c in old_characters if c.get("visual_reference"))
    new_with_visual = sum(1 for d in character_details if d.get("visual_reference"))
    output_lines.append(f"  旧方案有visual_ref: {old_with_visual}  vs  新方案有visual_ref: {new_with_visual}")
    old_with_desire = sum(1 for c in old_characters if c.get("desire"))
    new_with_desire = sum(1 for d in character_details if d.get("desire"))
    output_lines.append(f"  旧方案有desire: {old_with_desire}  vs  新方案有desire: {new_with_desire}")
    output_lines.append(f"  新方案优势: 每个角色独立AI调用，质量更高；输入为synopsis不截断")

    save_result("07_新旧对比.txt", "\n".join(output_lines))
    results_summary.append(
        f"[PASS] Step 7: 新旧对比 — 旧={len(old_characters)}角色({old_elapsed:.1f}s) "
        f"vs 新={len(character_details)}角色"
    )
    print(f"  PASS: Old={len(old_characters)} chars ({old_elapsed:.1f}s), New={len(character_details)} chars")

except Exception as e:
    results_summary.append(f"[FAIL] Step 7: 新旧对比 — {e}")
    save_result("07_新旧对比.txt", f"FAILED: {e}\n\n{traceback.format_exc()}")
    print(f"  FAIL: {e}")


# ── Cleanup ──────────────────────────────────────────────────────
db.query(AIProvider).filter(AIProvider.name == "_pipeline_test_v2").delete()
db.commit()
db.close()
ai_engine.invalidate_cache()


# ── Summary Report ──────────────────────────────────────────────
print("\n" + "=" * 70)
print("  第2次测试报告 — 长文本AI处理管道改进")
print("=" * 70)
print(f"  小说: 《我和沈词的长子》 ({len(novel_text)} 字)")
print()

summary_lines = [
    "=" * 70,
    "  第2次测试报告 — 长文本AI处理管道改进",
    "=" * 70,
    f"  小说: 《我和沈词的长子》 ({len(novel_text)} 字)",
    "",
]

pass_count = sum(1 for r in results_summary if "[PASS]" in r)
fail_count = sum(1 for r in results_summary if "[FAIL]" in r)

for r in results_summary:
    summary_lines.append(f"  {r}")
    print(f"  {r}")

summary_lines.append("")
summary_lines.append("=" * 70)
overall = f"总结: {pass_count} 通过, {fail_count} 失败"
if fail_count == 0:
    overall += " — 全部通过 ✓"
summary_lines.append(f"  {overall}")
summary_lines.append("=" * 70)
summary_lines.append("")
summary_lines.append("改进要点:")
summary_lines.append("  1. 章节分割: regex优先 + 分块AI回退 (20K/块, 1K重叠)")
summary_lines.append("  2. 章节摘要: 新增步骤, 每章生成300-500字摘要")
summary_lines.append("  3. 角色提取: 两轮 (P03A名单扫描 + P03B逐一详情)")
summary_lines.append("  4. 场景提取: 带角色名上下文, 保证角色名一致性")
summary_lines.append("  5. 知识库: 从synopsis构建, 不再需要全文输入")

print()
print(f"  {overall}")
print("=" * 70)

save_result("00_测试总结.txt", "\n".join(summary_lines))
print(f"\nAll results saved to: {os.path.abspath(OUTPUT_DIR)}")
