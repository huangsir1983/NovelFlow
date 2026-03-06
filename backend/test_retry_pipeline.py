"""Retry failed tests with delay to avoid 429 rate limiting."""

import json
import sys
import os
import time
import traceback
import re

sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, init_db
from models.ai_provider import AIProvider
from uuid import uuid4

init_db()
db = SessionLocal()

# Setup
db.query(AIProvider).filter(AIProvider.name == "_retry_test").delete()
db.commit()

provider = AIProvider(
    id=str(uuid4()),
    name="_retry_test",
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


def fix_json(raw):
    """Try to extract and fix JSON from AI response."""
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    # Fix trailing commas before } or ]
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)

    return json.loads(text)


output = []

# Test 1: P03 Character Extraction (was JSON parse error)
output.append("=" * 60)
output.append("[1/3] P03_CHARACTER_EXTRACT — Retry")
output.append("=" * 60)
try:
    prompt = render_prompt("P03_CHARACTER_EXTRACT", text=SAMPLE_NOVEL)
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    content = result["content"]
    output.append(f"Model: {result['model']}  |  Elapsed: {result['elapsed']}s  |  Chars: {len(content)}")

    parsed = fix_json(content)
    output.append(f"Characters found: {len(parsed)}")
    for ch in parsed:
        name = ch.get("name", "?")
        role = ch.get("role", "?")
        desire = ch.get("desire", "N/A")
        flaw = ch.get("flaw", "N/A")
        output.append(f"  - {name} ({role})")
        output.append(f"    Desire: {desire}")
        output.append(f"    Flaw: {flaw}")
        rels = ch.get("relationships", [])
        if rels:
            for r in rels:
                output.append(f"    Rel -> {r.get('target', '?')}: {r.get('dynamic', r.get('description', ''))}")
    output.append("[PASS] P03 Character Extraction")
except Exception as e:
    output.append(f"[FAIL] P03: {e}")
    output.append(traceback.format_exc())

output.append("")
time.sleep(3)  # Avoid 429

# Test 2: P04 Scene Extraction (was 429)
output.append("=" * 60)
output.append("[2/3] P04_SCENE_EXTRACT — Retry")
output.append("=" * 60)
try:
    ch1_text = SAMPLE_NOVEL[:len(SAMPLE_NOVEL)//2]
    prompt = render_prompt("P04_SCENE_EXTRACT", text=ch1_text)
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    content = result["content"]
    output.append(f"Model: {result['model']}  |  Elapsed: {result['elapsed']}s  |  Chars: {len(content)}")

    parsed = fix_json(content)
    output.append(f"Scenes found: {len(parsed)}")
    for sc in parsed:
        heading = sc.get("heading", "?")
        tension = sc.get("tension_score", "?")
        purpose = sc.get("dramatic_purpose", "N/A")
        output.append(f"  - {heading}  (tension: {tension})")
        output.append(f"    Purpose: {purpose}")
        dialogues = sc.get("dialogue", [])
        for d in dialogues[:2]:
            subtext = d.get("subtext", "")
            output.append(f"    Dialog: {d.get('character','?')}: {d.get('line','')[:50]}")
            if subtext:
                output.append(f"      Subtext: {subtext}")
    output.append("[PASS] P04 Scene Extraction")
except Exception as e:
    output.append(f"[FAIL] P04: {e}")
    output.append(traceback.format_exc())

output.append("")
time.sleep(3)

# Test 3: PS04 Visual Readiness (was 429)
output.append("=" * 60)
output.append("[3/3] PS04_VISUAL_READINESS — Retry")
output.append("=" * 60)
try:
    prompt = render_prompt("PS04_VISUAL_READINESS", text=SAMPLE_SCENES_JSON)
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    content = result["content"]
    output.append(f"Model: {result['model']}  |  Elapsed: {result['elapsed']}s  |  Chars: {len(content)}")

    parsed = fix_json(content)
    overall = parsed.get("overall_score", "?")
    assessment = parsed.get("overall_assessment", "N/A")
    output.append(f"Overall score: {overall}")
    output.append(f"Assessment: {assessment}")
    scenes = parsed.get("scenes", [])
    for sc in scenes:
        sid = sc.get("scene_id", "?")
        score = sc.get("score", "?")
        missing = sc.get("missing", [])
        fixes = sc.get("fix_suggestions", [])
        output.append(f"  Scene '{sid}': score={score}")
        if missing:
            output.append(f"    Missing: {', '.join(missing[:3])}")
        if fixes:
            output.append(f"    Fix: {fixes[0][:80]}")
    recs = parsed.get("recommendations", [])
    if recs:
        output.append(f"  Recommendations: {recs[0][:80]}")
    output.append("[PASS] PS04 Visual Readiness")
except Exception as e:
    output.append(f"[FAIL] PS04: {e}")
    output.append(traceback.format_exc())

# Cleanup
db.query(AIProvider).filter(AIProvider.name == "_retry_test").delete()
db.commit()
db.close()
ai_engine.invalidate_cache()

# Write report
report = "\n".join(output)
with open("test_retry_report.txt", "w", encoding="utf-8") as f:
    f.write(report)

for line in output:
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode())
