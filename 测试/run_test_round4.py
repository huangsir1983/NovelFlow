"""第4轮测试 — 逐步手动触发模式.

用法:
  python run_test_round4.py step1      # 章节分割
  python run_test_round4.py step2      # 章节摘要
  python run_test_round4.py step3a     # 角色名单扫描
  python run_test_round4.py step3b     # 角色详情
  python run_test_round4.py step4      # 场景提取
  python run_test_round4.py step5      # 节拍提取
  python run_test_round4.py step6      # 知识库V2
  python run_test_round4.py step7      # 视觉评估
  python run_test_round4.py step8      # 分镜优化
  python run_test_round4.py step9      # AI改写
  python run_test_round4.py step10     # 格式检测
  python run_test_round4.py step11     # 流式测试
  python run_test_round4.py summary    # 生成总结报告

每步完全独立:
  - 从文件读取上一步的输出（不共享内存状态）
  - 每次 API 调用都是全新的对话（无上下文关联）
  - 失败可单独重跑，不影响其他步骤
"""

import json
import os
import re
import sys
import time
import httpx

# ── 配置 ──────────────────────────────────────────────────────────
API_BASE = "https://www.openclaudecode.cn/v1/responses"
API_KEY = "sk-S2HdTVByFCfJcZ3oM3BUBQio0CGtty7xA2aTHdCP9occt50e"
MODEL = "gpt-5.4"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NOVEL_PATH = os.path.join(SCRIPT_DIR, "我和沈词的长子.txt")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "第4次测试结果")
TIMEOUT = 500  # 秒

sys.stdout.reconfigure(encoding="utf-8")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── prompt 模板 ──────────────────────────────────────────────────
sys.path.insert(0, os.path.join(SCRIPT_DIR, "..", "backend"))
from services.prompt_templates import TEMPLATES


# ── 基础工具 ──────────────────────────────────────────────────────

def read_novel() -> str:
    with open(NOVEL_PATH, "rb") as f:
        return f.read().decode("gb18030")


def call_api(system: str, user: str, temperature: float = 0.7,
             max_tokens: int = 4096) -> str:
    """单次独立 API 调用，无上下文关联。"""
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


def call_api_stream(system: str, user: str, temperature: float = 0.7,
                    max_tokens: int = 4096) -> list[str]:
    """流式 API 调用。"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": MODEL,
        "input": [{"role": "user", "content": user}],
        "temperature": temperature,
        "max_output_tokens": max_tokens,
        "stream": True,
    }
    if system:
        body["instructions"] = system

    chunks = []
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        with client.stream("POST", API_BASE, json=body, headers=headers) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                    if chunk.get("type") == "response.output_text.delta":
                        text = chunk.get("delta", "")
                        if text:
                            chunks.append(text)
                except json.JSONDecodeError:
                    continue
    return chunks


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


def fmt_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def save(filename: str, content: str):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  → 已保存: {filename}")


def load(filename: str) -> str:
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_json_from_file(filename: str):
    """从结果文件中提取 JSON 数据。"""
    raw = load(filename)
    # 找到第一个 [ 或 { 开始的位置
    for i, ch in enumerate(raw):
        if ch in ("[", "{"):
            try:
                return json.loads(raw[i:])
            except json.JSONDecodeError:
                # 试着用 extract_json
                return extract_json(raw[i:])
    raise ValueError(f"文件 {filename} 中无 JSON 数据")


# ── 各步骤（完全独立，从文件读取依赖） ──────────────────────────

def step1():
    """Step 1: 章节分割 (P01)"""
    print("=" * 60)
    print("  Step 1: 章节分割 (P01_CHAPTER_SPLIT)")
    print("=" * 60)

    novel = read_novel()
    tmpl = TEMPLATES["P01_CHAPTER_SPLIT"]

    print(f"  小说长度: {len(novel)} 字")
    print(f"  调用 API...")

    t0 = time.time()
    resp = call_api(
        system=tmpl["system"],
        user=tmpl["user"].format(text=novel),
        temperature=tmpl["temperature"],
        max_tokens=tmpl["max_tokens"],
    )
    elapsed = time.time() - t0

    data = extract_json(resp)

    out = f"章节分割结果 — 共 {len(data)} 章\n"
    out += f"模型: {MODEL} | 耗时: {elapsed:.1f}s\n\n"
    out += fmt_json(data)
    save("01_章节分割.txt", out)
    print(f"  [PASS] {len(data)} 章 | {elapsed:.1f}s")


def step2():
    """Step 2: 章节摘要 (P01B) — 逐章独立调用"""
    print("=" * 60)
    print("  Step 2: 章节摘要 (P01B_CHAPTER_SUMMARY)")
    print("=" * 60)

    novel = read_novel()
    chapters = load_json_from_file("01_章节分割.txt")
    tmpl = TEMPLATES["P01B_CHAPTER_SUMMARY"]

    print(f"  共 {len(chapters)} 章待摘要")

    summaries = []
    total_time = 0

    for i, ch in enumerate(chapters):
        title = ch.get("title", f"第{i+1}章")

        # 用 marker 从原文提取章节文本
        start = ch.get("start_marker", "")
        end = ch.get("end_marker", "")
        si = novel.find(start) if start else -1
        ei = novel.find(end) if end else -1
        if si >= 0 and ei >= 0:
            ch_text = novel[si:ei + len(end)]
        else:
            ch_text = f"（章节: {title}, 标记: {start} ... {end}）"

        print(f"  [{i+1}/{len(chapters)}] {title} ({len(ch_text)}字)...", end="", flush=True)

        t0 = time.time()
        resp = call_api(
            system=tmpl["system"],
            user=tmpl["user"].format(chapter_title=title, text=ch_text),
            temperature=tmpl["temperature"],
            max_tokens=tmpl["max_tokens"],
        )
        elapsed = time.time() - t0
        total_time += elapsed

        summaries.append({"chapter": title, "summary": resp.strip(), "time": f"{elapsed:.1f}s"})
        print(f" {elapsed:.1f}s")

    # 拼接 synopsis
    synopsis = "\n\n".join(f"【{s['chapter']}】\n{s['summary']}" for s in summaries)

    out = f"章节摘要结果 — 共 {len(summaries)} 章 | synopsis 总长: {len(synopsis)} 字\n"
    out += f"模型: {MODEL} | 总耗时: {total_time:.1f}s\n\n"
    for s in summaries:
        out += f"{'='*50}\n"
        out += f"【{s['chapter']}】 ({s['time']})\n"
        out += f"{s['summary']}\n\n"
    save("02_章节摘要.txt", out)

    # 额外保存纯 synopsis 文本，供后续步骤读取
    save("02_synopsis.txt", synopsis)
    print(f"  [PASS] {len(summaries)} 章摘要, synopsis={len(synopsis)}字 | {total_time:.1f}s")


def step3a():
    """Step 3a: 角色名单扫描 (P03A)"""
    print("=" * 60)
    print("  Step 3a: 角色名单扫描 (P03A_CHARACTER_SCAN)")
    print("=" * 60)

    synopsis = load("02_synopsis.txt")
    tmpl = TEMPLATES["P03A_CHARACTER_SCAN"]

    print(f"  Synopsis 长度: {len(synopsis)} 字")
    print(f"  调用 API...")

    t0 = time.time()
    resp = call_api(
        system=tmpl["system"],
        user=tmpl["user"].format(synopsis=synopsis),
        temperature=tmpl["temperature"],
        max_tokens=tmpl["max_tokens"],
    )
    elapsed = time.time() - t0

    data = extract_json(resp)
    names = [c.get("name", "?") for c in data]

    out = f"角色名单扫描结果 — 共 {len(data)} 角色\n"
    out += f"模型: {MODEL} | 耗时: {elapsed:.1f}s\n"
    out += f"角色: {', '.join(names)}\n\n"
    out += fmt_json(data)
    save("03a_角色名单扫描.txt", out)
    print(f"  [PASS] {len(data)} 角色: {', '.join(names)} | {elapsed:.1f}s")


def step3b():
    """Step 3b: 角色详情 (P03B) — 逐角色独立调用"""
    print("=" * 60)
    print("  Step 3b: 角色详情 (P03B_CHARACTER_DETAIL)")
    print("=" * 60)

    synopsis = load("02_synopsis.txt")
    characters = load_json_from_file("03a_角色名单扫描.txt")
    tmpl = TEMPLATES["P03B_CHARACTER_DETAIL"]

    # 只处理主要角色（protagonist/antagonist/supporting），跳过 minor
    main_chars = [c for c in characters if c.get("role") in ("protagonist", "antagonist", "supporting")]
    minor_chars = [c for c in characters if c.get("role") == "minor"]

    print(f"  主要角色: {len(main_chars)}, 次要角色: {len(minor_chars)} (跳过)")

    all_names = [c.get("name", "?") for c in characters]
    details = []
    total_time = 0

    for i, ch in enumerate(main_chars):
        name = ch.get("name", "?")
        brief = ch.get("brief", ch.get("description", ""))
        other_names = [n for n in all_names if n != name]

        print(f"  [{i+1}/{len(main_chars)}] {name}...", end="", flush=True)

        t0 = time.time()
        resp = call_api(
            system=tmpl["system"],
            user=tmpl["user"].format(
                character_name=name,
                character_brief=brief,
                other_characters=", ".join(other_names[:10]),
                synopsis=synopsis,
            ),
            temperature=tmpl["temperature"],
            max_tokens=tmpl["max_tokens"],
        )
        elapsed = time.time() - t0
        total_time += elapsed

        detail = extract_json(resp)
        details.append(detail)
        print(f" {elapsed:.1f}s")

    out = f"角色详情结果 — 共 {len(details)} 角色 (主要角色)\n"
    out += f"模型: {MODEL} | 总耗时: {total_time:.1f}s\n\n"
    for d in details:
        out += f"{'='*50}\n"
        out += fmt_json(d) + "\n\n"
    save("03b_角色详情.txt", out)
    print(f"  [PASS] {len(details)} 角色详情 | {total_time:.1f}s")


def step4():
    """Step 4: 场景提取 (P04) — 分批独立调用"""
    print("=" * 60)
    print("  Step 4: 场景提取 (P04_SCENE_EXTRACT)")
    print("=" * 60)

    synopsis = load("02_synopsis.txt")
    characters = load_json_from_file("03a_角色名单扫描.txt")
    tmpl = TEMPLATES["P04_SCENE_EXTRACT"]

    char_names = ", ".join(c.get("name", "?") for c in characters[:10])

    # 按【章节标题】分批，每批 1 个章节（避免 524 超时）
    batches = []
    current_parts = []
    for line in synopsis.split("\n"):
        if line.startswith("【") and current_parts:
            batches.append("\n".join(current_parts))
            current_parts = []
        current_parts.append(line)
    if current_parts:
        batches.append("\n".join(current_parts))

    print(f"  分 {len(batches)} 批处理")

    all_scenes = []
    total_time = 0
    scene_order = 0

    for i, batch_text in enumerate(batches):
        print(f"  [Batch {i+1}/{len(batches)}] ({len(batch_text)} 字)...", end="", flush=True)

        t0 = time.time()
        resp = call_api(
            system=tmpl["system"],
            user=tmpl["user"].format(text=batch_text, character_names=char_names),
            temperature=tmpl["temperature"],
            max_tokens=4096,
        )
        elapsed = time.time() - t0
        total_time += elapsed

        scenes = extract_json(resp)
        for s in scenes:
            s["order"] = scene_order
            scene_order += 1
        all_scenes.extend(scenes)
        print(f" {len(scenes)} 场景 ({elapsed:.1f}s)")

    out = f"场景提取结果 — 共 {len(all_scenes)} 场景 (分{len(batches)}批)\n"
    out += f"模型: {MODEL} | 总耗时: {total_time:.1f}s\n\n"
    out += fmt_json(all_scenes)
    save("04_场景提取.txt", out)
    print(f"  [PASS] {len(all_scenes)} 场景 | {total_time:.1f}s")


def step5():
    """Step 5: 节拍提取 (P10)"""
    print("=" * 60)
    print("  Step 5: 节拍提取 (P10_NOVEL_TO_BEAT)")
    print("=" * 60)

    synopsis = load("02_synopsis.txt")
    tmpl = TEMPLATES["P10_NOVEL_TO_BEAT"]

    print(f"  Synopsis 长度: {len(synopsis)} 字")
    print(f"  调用 API...")

    t0 = time.time()
    resp = call_api(
        system=tmpl["system"],
        user=tmpl["user"].format(text=synopsis),
        temperature=tmpl["temperature"],
        max_tokens=tmpl["max_tokens"],
    )
    elapsed = time.time() - t0

    data = extract_json(resp)

    out = f"节拍提取结果 — 共 {len(data)} 节拍\n"
    out += f"模型: {MODEL} | 耗时: {elapsed:.1f}s\n\n"
    out += fmt_json(data)
    save("05_节拍提取.txt", out)
    print(f"  [PASS] {len(data)} 节拍 | {elapsed:.1f}s")


def step6():
    """Step 6: 知识库V2 (P05V2)"""
    print("=" * 60)
    print("  Step 6: 知识库V2 (P05_KNOWLEDGE_BASE_V2)")
    print("=" * 60)

    synopsis = load("02_synopsis.txt")
    characters = load_json_from_file("03a_角色名单扫描.txt")
    tmpl = TEMPLATES["P05_KNOWLEDGE_BASE_V2"]

    char_names = ", ".join(c.get("name", "?") for c in characters[:10])

    # 尝试读取场景数据获取地点名
    loc_names = "未知"
    try:
        scenes = load_json_from_file("04_场景提取.txt")
        loc_names = ", ".join(s.get("location", "?") for s in scenes[:10])
    except:
        pass

    print(f"  调用 API...")

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

    out = f"知识库V2结果\n"
    out += f"模型: {MODEL} | 耗时: {elapsed:.1f}s\n"
    out += f"world_building={len(wb)}项, style_guide={len(sg)}项\n\n"
    out += fmt_json(data)
    save("06_知识库V2.txt", out)
    print(f"  [PASS] world_building={len(wb)}, style_guide={len(sg)} | {elapsed:.1f}s")


def step7():
    """Step 7: 视觉评估 (PS04)"""
    print("=" * 60)
    print("  Step 7: 视觉评估 (PS04_VISUAL_READINESS)")
    print("=" * 60)

    scenes = load_json_from_file("04_场景提取.txt")
    tmpl = TEMPLATES["PS04_VISUAL_READINESS"]

    scenes_text = fmt_json(scenes[:6])
    print(f"  评估前 6 个场景...")

    t0 = time.time()
    resp = call_api(
        system=tmpl["system"],
        user=tmpl["user"].format(text=scenes_text),
        temperature=tmpl["temperature"],
        max_tokens=tmpl["max_tokens"],
    )
    elapsed = time.time() - t0

    data = extract_json(resp)
    score = data.get("overall_score", "N/A")

    out = f"视觉评估结果 — 总分: {score}\n"
    out += f"模型: {MODEL} | 耗时: {elapsed:.1f}s\n\n"
    out += fmt_json(data)
    save("07_视觉评估.txt", out)
    print(f"  [PASS] 总分: {score} | {elapsed:.1f}s")


def step8():
    """Step 8: 分镜优化 (PS05)"""
    print("=" * 60)
    print("  Step 8: 分镜优化 (PS05_STORYBOARD_OPTIMIZE)")
    print("=" * 60)

    scenes = load_json_from_file("04_场景提取.txt")
    tmpl = TEMPLATES["PS05_STORYBOARD_OPTIMIZE"]

    scenes_text = fmt_json(scenes[:3])
    print(f"  优化前 3 个场景...")

    t0 = time.time()
    resp = call_api(
        system=tmpl["system"],
        user=tmpl["user"].format(text=scenes_text),
        temperature=tmpl["temperature"],
        max_tokens=tmpl["max_tokens"],
    )
    elapsed = time.time() - t0

    data = extract_json(resp)
    has_vn = any("visual_notes" in s for s in data) if isinstance(data, list) else False

    out = f"分镜优化结果 — {len(data)} 场景, visual_notes={'有' if has_vn else '无'}\n"
    out += f"模型: {MODEL} | 耗时: {elapsed:.1f}s\n\n"
    out += fmt_json(data)
    save("08_分镜优化.txt", out)
    print(f"  [PASS] {len(data)} 场景, visual_notes={'有' if has_vn else '无'} | {elapsed:.1f}s")


def step9():
    """Step 9: AI改写 (P12)"""
    print("=" * 60)
    print("  Step 9: AI改写 (P12_REWRITE)")
    print("=" * 60)

    novel = read_novel()
    tmpl = TEMPLATES["P12_REWRITE"]
    sample = novel[200:700]

    print(f"  改写样本: {len(sample)} 字")
    print(f"  调用 API...")

    t0 = time.time()
    resp = call_api(
        system=tmpl["system"],
        user=tmpl["user"].format(
            operation="改写",
            text=sample,
            context="请以更强的画面感和影视叙事节奏重新表达这段内容。",
        ),
        temperature=tmpl["temperature"],
        max_tokens=tmpl["max_tokens"],
    )
    elapsed = time.time() - t0

    out = f"AI改写结果 — {len(resp)} 字\n"
    out += f"模型: {MODEL} | 耗时: {elapsed:.1f}s\n\n"
    out += f"原文 ({len(sample)} 字):\n{sample}\n\n"
    out += f"{'='*50}\n\n"
    out += f"改写后 ({len(resp)} 字):\n{resp}"
    save("09_AI改写.txt", out)
    print(f"  [PASS] {len(resp)} 字 | {elapsed:.1f}s")


def step10():
    """Step 10: 格式检测 (PS01)"""
    print("=" * 60)
    print("  Step 10: 格式检测 (PS01_FORMAT_DETECT)")
    print("=" * 60)

    novel = read_novel()
    tmpl = TEMPLATES["PS01_FORMAT_DETECT"]

    print(f"  调用 API...")

    t0 = time.time()
    resp = call_api(
        system=tmpl["system"],
        user=tmpl["user"].format(text=novel[:2000]),
        temperature=tmpl["temperature"],
        max_tokens=tmpl["max_tokens"],
    )
    elapsed = time.time() - t0

    data = extract_json(resp)
    fmt = data.get("format", "?")
    conf = data.get("confidence", "?")

    out = f"格式检测结果 — {fmt} (置信度: {conf})\n"
    out += f"模型: {MODEL} | 耗时: {elapsed:.1f}s\n\n"
    out += fmt_json(data)
    save("10_格式检测.txt", out)
    print(f"  [PASS] {fmt} ({conf}) | {elapsed:.1f}s")


def step11():
    """Step 11: 流式测试"""
    print("=" * 60)
    print("  Step 11: 流式输出测试")
    print("=" * 60)

    print(f"  调用流式 API...")

    t0 = time.time()
    chunks = call_api_stream(
        system="你是一位创意写作助手。",
        user="用100字描述一个古代书房的场景，要有画面感。",
        temperature=0.7,
        max_tokens=256,
    )
    elapsed = time.time() - t0
    full_text = "".join(chunks)

    out = f"流式测试结果 — {len(chunks)} chunks, {len(full_text)} 字\n"
    out += f"模型: {MODEL} | 耗时: {elapsed:.1f}s\n\n"
    out += f"完整输出:\n{full_text}"
    save("11_流式测试.txt", out)
    print(f"  [PASS] {len(chunks)} chunks, {len(full_text)} chars | {elapsed:.1f}s")


def summary():
    """汇总所有步骤结果，生成总结报告。"""
    print("=" * 60)
    print("  生成测试总结报告")
    print("=" * 60)

    novel = read_novel()
    steps = [
        ("Step 1: 章节分割 (P01)", "01_章节分割.txt"),
        ("Step 2: 章节摘要 (P01B)", "02_章节摘要.txt"),
        ("Step 3a: 角色名单 (P03A)", "03a_角色名单扫描.txt"),
        ("Step 3b: 角色详情 (P03B)", "03b_角色详情.txt"),
        ("Step 4: 场景提取 (P04)", "04_场景提取.txt"),
        ("Step 5: 节拍提取 (P10)", "05_节拍提取.txt"),
        ("Step 6: 知识库V2 (P05V2)", "06_知识库V2.txt"),
        ("Step 7: 视觉评估 (PS04)", "07_视觉评估.txt"),
        ("Step 8: 分镜优化 (PS05)", "08_分镜优化.txt"),
        ("Step 9: AI改写 (P12)", "09_AI改写.txt"),
        ("Step 10: 格式检测 (PS01)", "10_格式检测.txt"),
        ("Step 11: 流式测试", "11_流式测试.txt"),
    ]

    lines = []
    lines.append("=" * 70)
    lines.append("  第4轮测试报告 — OpenClaudeCode API + gpt-5.4")
    lines.append("=" * 70)
    lines.append(f"  小说: 《我和沈词的长子》 ({len(novel)} 字)")
    lines.append(f"  API: OpenClaudeCode (www.openclaudecode.cn)")
    lines.append(f"  协议: OpenAI Responses API (/v1/responses)")
    lines.append(f"  模型: {MODEL}")
    lines.append("")

    passed = 0
    failed = 0

    for step_name, filename in steps:
        filepath = os.path.join(OUTPUT_DIR, filename)
        if not os.path.exists(filepath):
            lines.append(f"  [SKIP] {step_name} — 未执行")
            failed += 1
            continue

        content = load(filename)
        first_line = content.split("\n")[0]

        if content.startswith("[FAIL]"):
            lines.append(f"  [FAIL] {step_name} — {first_line}")
            failed += 1
        else:
            lines.append(f"  [PASS] {step_name} — {first_line}")
            passed += 1

    lines.append("")
    lines.append("=" * 70)
    lines.append(f"  总结: {passed} 通过, {failed} 失败/跳过")
    lines.append("=" * 70)

    report = "\n".join(lines)
    save("00_测试总结.txt", report)
    print(f"\n{report}")


# ── 主入口 ──────────────────────────────────────────────────────

STEPS = {
    "step1": step1,
    "step2": step2,
    "step3a": step3a,
    "step3b": step3b,
    "step4": step4,
    "step5": step5,
    "step6": step6,
    "step7": step7,
    "step8": step8,
    "step9": step9,
    "step10": step10,
    "step11": step11,
    "summary": summary,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in STEPS:
        print("用法: python run_test_round4.py <step>")
        print()
        print("可用步骤:")
        print("  step1   — 章节分割")
        print("  step2   — 章节摘要 (依赖 step1)")
        print("  step3a  — 角色名单扫描 (依赖 step2)")
        print("  step3b  — 角色详情 (依赖 step2, step3a)")
        print("  step4   — 场景提取 (依赖 step2, step3a)")
        print("  step5   — 节拍提取 (依赖 step2)")
        print("  step6   — 知识库V2 (依赖 step2, step3a)")
        print("  step7   — 视觉评估 (依赖 step4)")
        print("  step8   — 分镜优化 (依赖 step4)")
        print("  step9   — AI改写 (独立)")
        print("  step10  — 格式检测 (独立)")
        print("  step11  — 流式测试 (独立)")
        print("  summary — 生成总结报告")
        sys.exit(0)

    step_name = sys.argv[1]
    try:
        STEPS[step_name]()
    except FileNotFoundError as e:
        print(f"\n  [ERROR] 缺少依赖文件: {e}")
        print(f"  请先运行前置步骤。")
        sys.exit(1)
    except Exception as e:
        print(f"\n  [FAIL] {e}")
        sys.exit(1)
