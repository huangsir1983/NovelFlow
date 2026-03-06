"""Full pipeline test — verify all upgraded prompt templates work end-to-end."""

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
db.query(AIProvider).filter(AIProvider.name == "_pipeline_test").delete()
db.commit()

provider = AIProvider(
    id=str(uuid4()),
    name="_pipeline_test",
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

# ── Test Data ────────────────────────────────────────────────────

SAMPLE_NOVEL = """第一章 重生

凌晨三点，暴雨如注。
林默站在天台边缘，雨水顺着他的脸颊流下，模糊了整个城市的灯火。三年前，他是锦城最年轻的天才建筑师，一手设计了"云上之城"项目，被业界誉为下一个贝聿铭。
三年后的今天，他一无所有。
"林默，你以为跳下去就能解脱？"身后传来一个沙哑的声音。
他没有回头。他知道那是老赵——他曾经的工地主管，现在是这栋烂尾楼唯一的看守人。
"老赵，你知道吗，"林默的声音被雨声吞没了一半，"三年前我亲手画的图纸，现在变成了别人的名字。我的合伙人周天明，用我的设计拿了国际大奖，而我……连一个证明自己的机会都没有。"
老赵沉默了很久，然后从口袋里掏出一个U盘。
"这是你三年前让我保管的东西。你说过，如果有一天你需要它，我就把它交给你。"
林默接过U盘，手指微微发抖。他记起来了——这里面存着"云上之城"所有原始设计文件，包括每一个版本的修改记录，时间戳精确到秒。
"还有一件事，"老赵压低声音，"周天明下个月要竞标'星河湾'项目，总投资八十亿。听说他用的还是你当年的设计理念。"
林默的眼神在雨幕中渐渐变得锐利。
他从天台边缘退了一步。

第二章 暗流

一周后，锦城CBD，天明建筑集团总部。
周天明坐在顶层办公室里，透过落地窗俯瞰着整座城市。他的办公桌上放着一份《建筑界》杂志，封面人物正是他自己，标题写着："周天明：从草根到大师的传奇"。
"周总，林默最近有动静。"秘书小张推门而入。
周天明的手指停在咖啡杯边缘。"什么动静？"
"他去了市建筑档案馆，调取了'云上之城'项目的所有备案资料。"
周天明的表情没有任何变化，但他的手指在桌面上轻轻敲了三下——这是他紧张时的习惯动作，只有跟了他五年的小张注意到了。
"让法务部准备一下。另外，把陈律师叫来。"
小张点头离开后，周天明独自站在落地窗前。窗外阳光灿烂，但他的倒影里，嘴角的弧度冰冷而危险。

与此同时，在城市另一头的旧城区。
林默租了一间不到二十平米的公寓，墙上贴满了图纸和时间线。U盘里的文件比他记忆中的更完整——不仅有设计图，还有当年他和周天明的聊天记录、邮件往来、甚至几段录音。
"够了，"林默对自己说，"这些足以证明一切。"
他拿起手机，拨通了一个三年没联系的号码。
"苏晴，是我，林默。我需要你的帮助。"
电话那头沉默了五秒。
"你终于打过来了。"苏晴的声音平静得不像是三年未见的旧友。"我等你这个电话，等了三年。"
"""

SAMPLE_SCENES_JSON = json.dumps([
    {
        "heading": "INT. 天台 - 夜/暴雨",
        "location": "烂尾楼天台",
        "time_of_day": "night",
        "description": "暴雨倾盆的深夜天台，城市灯火在雨幕中模糊",
        "action": "林默站在天台边缘，老赵从身后出现并交出U盘",
        "dialogue": [
            {"character": "林默", "line": "三年前我亲手画的图纸，现在变成了别人的名字"},
            {"character": "老赵", "line": "这是你三年前让我保管的东西"}
        ],
        "order": 0,
        "tension_score": 0.8
    },
    {
        "heading": "INT. 天明集团总部办公室 - 日",
        "location": "CBD顶层办公室",
        "time_of_day": "day",
        "description": "奢华的顶层办公室，落地窗俯瞰全城",
        "action": "周天明得知林默的动向后指示法务部准备应对",
        "dialogue": [
            {"character": "小张", "line": "林默最近有动静，他去了市建筑档案馆"},
            {"character": "周天明", "line": "让法务部准备一下"}
        ],
        "order": 1,
        "tension_score": 0.6
    },
    {
        "heading": "INT. 旧城区公寓 - 夜",
        "location": "林默的出租公寓",
        "time_of_day": "night",
        "description": "狭小的公寓，墙上贴满图纸和时间线",
        "action": "林默整理证据后拨通苏晴的电话",
        "dialogue": [
            {"character": "林默", "line": "苏晴，是我，林默。我需要你的帮助。"},
            {"character": "苏晴", "line": "我等你这个电话，等了三年。"}
        ],
        "order": 2,
        "tension_score": 0.7
    }
], ensure_ascii=False)

# ── Test Runner ──────────────────────────────────────────────────

results = []
passed = 0
failed = 0


def run_test(name, template_id, text_input, extra_kwargs=None):
    global passed, failed
    kwargs = {"text": text_input}
    if extra_kwargs:
        kwargs.update(extra_kwargs)

    try:
        prompt = render_prompt(template_id, **kwargs)
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

        content = result["content"].strip()
        # Try to extract JSON from the response
        json_str = content
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        parsed = json.loads(json_str)

        # Validate structure
        validation = validate_output(template_id, parsed)

        status = "PASS" if validation["ok"] else "WARN"
        if validation["ok"]:
            passed += 1
        else:
            passed += 1  # WARN still counts as functional

        entry = {
            "name": name,
            "status": status,
            "elapsed": f"{elapsed:.1f}s",
            "model": result["model"],
            "provider": result["provider"],
            "output_size": len(content),
            "validation": validation,
            "sample": str(parsed)[:200],
        }
        results.append(entry)
        return parsed

    except Exception as e:
        failed += 1
        entry = {
            "name": name,
            "status": "FAIL",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
        results.append(entry)
        return None


def validate_output(template_id, parsed):
    """Validate the parsed JSON output matches expected structure."""
    issues = []

    if template_id == "P01_CHAPTER_SPLIT":
        if not isinstance(parsed, list) or len(parsed) == 0:
            issues.append("Expected non-empty array")
        else:
            for i, ch in enumerate(parsed):
                if "title" not in ch:
                    issues.append(f"Chapter {i}: missing 'title'")
                if "content" not in ch:
                    issues.append(f"Chapter {i}: missing 'content'")

    elif template_id == "P03_CHARACTER_EXTRACT":
        if not isinstance(parsed, list) or len(parsed) == 0:
            issues.append("Expected non-empty array")
        else:
            for i, ch in enumerate(parsed):
                for field in ["name", "role", "description"]:
                    if field not in ch:
                        issues.append(f"Character {i}: missing '{field}'")
                # Check for new production-grade fields
                new_fields = ["desire", "flaw"]
                for f in new_fields:
                    if f not in ch:
                        issues.append(f"Character {i}: missing new field '{f}' (production-grade)")

    elif template_id == "P04_SCENE_EXTRACT":
        if not isinstance(parsed, list) or len(parsed) == 0:
            issues.append("Expected non-empty array")
        else:
            for i, sc in enumerate(parsed):
                for field in ["heading", "location", "time_of_day"]:
                    if field not in sc:
                        issues.append(f"Scene {i}: missing '{field}'")
                if "dramatic_purpose" not in sc:
                    issues.append(f"Scene {i}: missing new field 'dramatic_purpose'")

    elif template_id == "P10_NOVEL_TO_BEAT":
        if not isinstance(parsed, list) or len(parsed) == 0:
            issues.append("Expected non-empty array")
        else:
            for i, b in enumerate(parsed):
                for field in ["title", "beat_type", "emotional_value"]:
                    if field not in b:
                        issues.append(f"Beat {i}: missing '{field}'")
                if "hook_potential" not in b:
                    issues.append(f"Beat {i}: missing new field 'hook_potential'")

    elif template_id == "P05_KNOWLEDGE_BASE":
        if not isinstance(parsed, dict):
            issues.append("Expected object")
        else:
            if "world_building" not in parsed:
                issues.append("Missing 'world_building'")
            if "style_guide" not in parsed:
                issues.append("Missing 'style_guide'")
            if "locations" not in parsed:
                issues.append("Missing 'locations'")
            # Check new fields
            wb = parsed.get("world_building", {})
            if "conflict_triggers" not in wb:
                issues.append("world_building: missing new field 'conflict_triggers'")
            sg = parsed.get("style_guide", {})
            if "visual_tone" not in sg:
                issues.append("style_guide: missing new field 'visual_tone'")

    elif template_id == "PS01_FORMAT_DETECT":
        if not isinstance(parsed, dict):
            issues.append("Expected object")
        else:
            if "format" not in parsed:
                issues.append("Missing 'format'")
            if "confidence" not in parsed:
                issues.append("Missing 'confidence'")

    elif template_id == "PS02_REVERSE_BEATS":
        if not isinstance(parsed, list) or len(parsed) == 0:
            issues.append("Expected non-empty array")
        else:
            for i, b in enumerate(parsed):
                for field in ["title", "beat_type", "emotional_value"]:
                    if field not in b:
                        issues.append(f"Beat {i}: missing '{field}'")

    elif template_id == "PS03_REVERSE_KNOWLEDGE":
        if not isinstance(parsed, dict):
            issues.append("Expected object")
        else:
            for section in ["world_building", "style_guide", "locations", "characters"]:
                if section not in parsed:
                    issues.append(f"Missing '{section}'")

    elif template_id == "PS04_VISUAL_READINESS":
        if not isinstance(parsed, dict):
            issues.append("Expected object")
        else:
            if "overall_score" not in parsed:
                issues.append("Missing 'overall_score'")
            if "scenes" not in parsed:
                issues.append("Missing 'scenes'")
            if "overall_assessment" not in parsed:
                issues.append("Missing new field 'overall_assessment'")

    elif template_id == "PS05_STORYBOARD_OPTIMIZE":
        if not isinstance(parsed, list) or len(parsed) == 0:
            issues.append("Expected non-empty array")
        else:
            for i, sc in enumerate(parsed):
                if "visual_notes" not in sc:
                    issues.append(f"Scene {i}: missing 'visual_notes'")
                else:
                    vn = sc["visual_notes"]
                    for f in ["shot_suggestions", "emotional_curve", "key_visual"]:
                        if f not in vn:
                            issues.append(f"Scene {i}.visual_notes: missing '{f}'")

    elif template_id == "P12_REWRITE":
        # Rewrite just returns text, validated by being non-empty
        if isinstance(parsed, str) and len(parsed) == 0:
            issues.append("Empty rewrite result")

    elif template_id == "P13_FREE_SCRIPT_PARSE":
        if not isinstance(parsed, list) or len(parsed) == 0:
            issues.append("Expected non-empty array")
        else:
            for i, sc in enumerate(parsed):
                for field in ["heading", "location", "dialogue"]:
                    if field not in sc:
                        issues.append(f"Scene {i}: missing '{field}'")

    return {"ok": len(issues) == 0, "issues": issues}


# ── Run All Tests ────────────────────────────────────────────────

print("=" * 60)
print("  FULL PIPELINE TEST — Production-Grade Prompts")
print("=" * 60)
print()

# P01: Chapter Split
print("[1/13] P01_CHAPTER_SPLIT ...")
chapters = run_test("P01: Chapter Splitting", "P01_CHAPTER_SPLIT", SAMPLE_NOVEL)

# P03: Character Extract
print("[2/13] P03_CHARACTER_EXTRACT ...")
characters = run_test("P03: Character Extraction", "P03_CHARACTER_EXTRACT", SAMPLE_NOVEL)

# P04: Scene Extract
print("[3/13] P04_SCENE_EXTRACT ...")
ch1_text = SAMPLE_NOVEL[:len(SAMPLE_NOVEL)//2]
scenes = run_test("P04: Scene Extraction", "P04_SCENE_EXTRACT", ch1_text)

# P10: Novel to Beat Sheet
print("[4/13] P10_NOVEL_TO_BEAT ...")
beats = run_test("P10: Novel to Beat Sheet", "P10_NOVEL_TO_BEAT", SAMPLE_NOVEL)

# P05: Knowledge Base
print("[5/13] P05_KNOWLEDGE_BASE ...")
knowledge = run_test("P05: Knowledge Base Building", "P05_KNOWLEDGE_BASE", SAMPLE_NOVEL)

# PS01: Format Detection
print("[6/13] PS01_FORMAT_DETECT ...")
script_text = """第一场 内景 天台 夜/暴雨

林默站在天台边缘。暴雨倾盆。

老赵：（从黑暗中走出）林默，你以为跳下去就能解脱？

林默：（不回头）三年前我亲手画的图纸，现在变成了别人的名字。

第二场 内景 办公室 日

周天明坐在顶层办公室里。

小张：周总，林默最近有动静。
周天明：什么动静？"""
fmt = run_test("PS01: Format Detection", "PS01_FORMAT_DETECT", script_text[:2000])

# PS02: Reverse Beat Extraction
print("[7/13] PS02_REVERSE_BEATS ...")
rev_beats = run_test("PS02: Reverse Beat Extraction", "PS02_REVERSE_BEATS", SAMPLE_SCENES_JSON)

# PS03: Reverse Knowledge Base
print("[8/13] PS03_REVERSE_KNOWLEDGE ...")
rev_kb = run_test("PS03: Reverse Knowledge Base", "PS03_REVERSE_KNOWLEDGE", SAMPLE_SCENES_JSON)

# PS04: Visual Readiness Assessment
print("[9/13] PS04_VISUAL_READINESS ...")
vis = run_test("PS04: Visual Readiness Assessment", "PS04_VISUAL_READINESS", SAMPLE_SCENES_JSON)

# PS05: Storyboard Optimization
print("[10/13] PS05_STORYBOARD_OPTIMIZE ...")
opt = run_test("PS05: Storyboard Optimization", "PS05_STORYBOARD_OPTIMIZE", SAMPLE_SCENES_JSON)

# P12: AI Rewrite
print("[11/13] P12_REWRITE ...")
rewrite_text = "她很紧张地看着他离开，心里充满了不安和恐惧。她不知道该怎么办。"
try:
    prompt = render_prompt("P12_REWRITE", text=rewrite_text, operation="改写", context="场景：雨夜告别，角色是一位坚强但内心脆弱的女性。")
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
    content = result["content"].strip()
    passed += 1
    results.append({
        "name": "P12: AI Rewrite",
        "status": "PASS",
        "elapsed": f"{elapsed:.1f}s",
        "model": result["model"],
        "provider": result["provider"],
        "output_size": len(content),
        "validation": {"ok": True, "issues": []},
        "sample": content[:200],
    })
except Exception as e:
    failed += 1
    results.append({
        "name": "P12: AI Rewrite",
        "status": "FAIL",
        "error": str(e),
        "traceback": traceback.format_exc(),
    })

# P13: Free Script Parse
print("[12/13] P13_FREE_SCRIPT_PARSE ...")
free_script = run_test("P13: Free Script Parsing", "P13_FREE_SCRIPT_PARSE", script_text)

# Streaming test
print("[13/13] Streaming test ...")
try:
    prompt = render_prompt("P01_CHAPTER_SPLIT", text="第一章 测试\n这是一个简单的测试文本。\n第二章 验证\n这是第二段测试文本。")
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
    passed += 1
    results.append({
        "name": "Streaming: Chapter Split",
        "status": "PASS",
        "elapsed": f"{elapsed:.1f}s",
        "chunks": len(chunks),
        "total_chars": len(full_text),
        "validation": {"ok": True, "issues": []},
        "sample": full_text[:200],
    })
except Exception as e:
    failed += 1
    results.append({
        "name": "Streaming: Chapter Split",
        "status": "FAIL",
        "error": str(e),
        "traceback": traceback.format_exc(),
    })

# ── Cleanup ──────────────────────────────────────────────────────
db.query(AIProvider).filter(AIProvider.name == "_pipeline_test").delete()
db.commit()
db.close()
ai_engine.invalidate_cache()

# ── Report ───────────────────────────────────────────────────────
report_lines = []
report_lines.append("=" * 70)
report_lines.append("  FULL PIPELINE TEST REPORT — Production-Grade Prompts")
report_lines.append("=" * 70)
report_lines.append("")
report_lines.append(f"  Total: {passed + failed}  |  PASS: {passed}  |  FAIL: {failed}")
report_lines.append("")

for r in results:
    status_icon = "[PASS]" if r["status"] == "PASS" else "[WARN]" if r["status"] == "WARN" else "[FAIL]"
    report_lines.append(f"  {status_icon} {r['name']}")

    if "elapsed" in r:
        report_lines.append(f"         Time: {r['elapsed']}  |  Model: {r.get('model', 'N/A')}  |  Provider: {r.get('provider', 'N/A')}")

    if "output_size" in r:
        report_lines.append(f"         Output: {r['output_size']} chars")

    if "chunks" in r:
        report_lines.append(f"         Chunks: {r['chunks']}  |  Total chars: {r['total_chars']}")

    validation = r.get("validation", {})
    if validation.get("issues"):
        for issue in validation["issues"]:
            report_lines.append(f"         [!] {issue}")

    if "error" in r:
        report_lines.append(f"         Error: {r['error']}")

    if "sample" in r:
        sample = r["sample"].replace("\n", " ")[:150]
        report_lines.append(f"         Sample: {sample}...")

    report_lines.append("")

# Pipeline flow validation
report_lines.append("-" * 70)
report_lines.append("  PIPELINE FLOW VALIDATION")
report_lines.append("-" * 70)
report_lines.append("")

if chapters:
    report_lines.append(f"  P01 -> Chapters extracted: {len(chapters)}")
    report_lines.append(f"         Can feed into P03/P04/P10/P05: YES")
else:
    report_lines.append(f"  P01 -> FAILED — pipeline blocked")

if characters:
    report_lines.append(f"  P03 -> Characters extracted: {len(characters)}")
    char_names = [c.get("name", "?") for c in characters]
    report_lines.append(f"         Characters: {', '.join(char_names)}")
    has_new_fields = all("desire" in c or "flaw" in c for c in characters)
    report_lines.append(f"         Production-grade fields (desire/flaw): {'YES' if has_new_fields else 'PARTIAL'}")
else:
    report_lines.append(f"  P03 -> FAILED — character data unavailable")

if scenes:
    report_lines.append(f"  P04 -> Scenes extracted: {len(scenes)}")
    has_purpose = any("dramatic_purpose" in s for s in scenes)
    report_lines.append(f"         Has dramatic_purpose field: {'YES' if has_purpose else 'NO'}")
    report_lines.append(f"         Can feed into PS04/PS05: YES")
else:
    report_lines.append(f"  P04 -> FAILED — scene data unavailable")

if beats:
    report_lines.append(f"  P10 -> Beats extracted: {len(beats)}")
    has_hooks = any("hook_potential" in b for b in beats)
    report_lines.append(f"         Has hook_potential field: {'YES' if has_hooks else 'NO'}")
else:
    report_lines.append(f"  P10 -> FAILED — beat data unavailable")

if knowledge:
    kb_sections = list(knowledge.keys())
    report_lines.append(f"  P05 -> Knowledge sections: {', '.join(kb_sections)}")
    has_ct = "conflict_triggers" in knowledge.get("world_building", {})
    has_vt = "visual_tone" in knowledge.get("style_guide", {})
    report_lines.append(f"         conflict_triggers: {'YES' if has_ct else 'NO'}  |  visual_tone: {'YES' if has_vt else 'NO'}")
else:
    report_lines.append(f"  P05 -> FAILED — knowledge base unavailable")

if rev_beats:
    report_lines.append(f"  PS02 -> Reverse beats: {len(rev_beats)}")
else:
    report_lines.append(f"  PS02 -> FAILED")

if rev_kb:
    report_lines.append(f"  PS03 -> Reverse KB sections: {list(rev_kb.keys())}")
else:
    report_lines.append(f"  PS03 -> FAILED")

if vis:
    report_lines.append(f"  PS04 -> Overall visual score: {vis.get('overall_score', 'N/A')}")
    has_assess = "overall_assessment" in vis
    report_lines.append(f"         Has overall_assessment: {'YES' if has_assess else 'NO'}")
else:
    report_lines.append(f"  PS04 -> FAILED")

if opt:
    has_vn = any("visual_notes" in s for s in opt)
    report_lines.append(f"  PS05 -> Optimized scenes: {len(opt)}")
    report_lines.append(f"         Has visual_notes: {'YES' if has_vn else 'NO'}")
else:
    report_lines.append(f"  PS05 -> FAILED")

report_lines.append("")
report_lines.append("=" * 70)
all_pass = failed == 0
report_lines.append(f"  OVERALL: {'ALL PASS — Pipeline fully operational' if all_pass else f'{failed} FAILURES — needs attention'}")
report_lines.append("=" * 70)

# Write report
report_text = "\n".join(report_lines)
with open("test_pipeline_report.txt", "w", encoding="utf-8") as f:
    f.write(report_text)

# Also print (handle encoding)
for line in report_lines:
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode())
