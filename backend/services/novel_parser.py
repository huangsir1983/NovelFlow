"""Novel parsing pipeline — file reading, chapter splitting, character/scene extraction, beat generation."""

import json
import logging
import re
import difflib
from uuid import uuid4

logger = logging.getLogger(__name__)


def read_file(file_bytes: bytes, filename: str) -> str:
    """Read uploaded file into plain text. Supports TXT, MD, DOCX, EPUB, PDF."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext in ("txt", "md"):
        return _read_text(file_bytes)
    elif ext == "docx":
        return _read_docx(file_bytes)
    elif ext == "epub":
        return _read_epub(file_bytes)
    elif ext == "pdf":
        return _read_pdf(file_bytes)
    else:
        # Fallback: try as plain text
        return _read_text(file_bytes)


def _read_text(data: bytes) -> str:
    """Read plain text, auto-detect encoding."""
    import chardet
    detected = chardet.detect(data)
    encoding = detected.get("encoding", "utf-8") or "utf-8"
    return data.decode(encoding, errors="replace")


def _read_docx(data: bytes) -> str:
    """Read DOCX file."""
    import io
    from docx import Document
    doc = Document(io.BytesIO(data))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _read_epub(data: bytes) -> str:
    """Read EPUB file."""
    import io
    import tempfile
    import os
    import ebooklib
    from ebooklib import epub
    from html.parser import HTMLParser

    class _HTMLTextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.result = []
        def handle_data(self, d):
            self.result.append(d)
        def get_text(self):
            return "".join(self.result)

    # ebooklib needs a file path
    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
        f.write(data)
        tmp_path = f.name

    try:
        book = epub.read_epub(tmp_path)
        texts = []
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            extractor = _HTMLTextExtractor()
            extractor.feed(item.get_content().decode("utf-8", errors="replace"))
            text = extractor.get_text().strip()
            if text:
                texts.append(text)
        return "\n\n".join(texts)
    finally:
        os.unlink(tmp_path)


def _read_pdf(data: bytes) -> str:
    """Read PDF file using pymupdf."""
    import io
    import fitz  # pymupdf
    doc = fitz.open(stream=data, filetype="pdf")
    texts = []
    for page in doc:
        texts.append(page.get_text())
    doc.close()
    return "\n\n".join(texts)


def split_chapters(text: str, db=None) -> list[dict]:
    """Split novel text into chapters using AI (fast tier) with regex pre-check.

    P01 now returns marker-based output (start_marker/end_marker) instead of full content.
    This function resolves markers back to full text using string matching.
    """
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    # Try regex-based splitting first for clearly marked chapters
    chapters = _regex_split(text)
    if chapters and len(chapters) > 1:
        logger.info(f"Regex split found {len(chapters)} chapters")
        return chapters

    # Fallback to AI splitting (marker-based)
    prompt = render_prompt("P01_CHAPTER_SPLIT", text=text[:80000])  # limit input
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    markers = _parse_json_response(result["content"], default=[])

    # Resolve markers to full content
    if markers:
        chapters = _resolve_markers(text, markers)
        if chapters:
            return chapters

    # Ultimate fallback
    return [{"title": "全文", "content": text, "order": 0}]


def _resolve_markers(text: str, markers: list[dict]) -> list[dict]:
    """Resolve start_marker/end_marker pairs back to full chapter content from original text."""
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
            # Try fuzzy: first 10 chars
            start_pos = text.find(start_marker[:10])
        if start_pos == -1:
            logger.warning(f"Chapter '{title}': start_marker not found, skipping")
            continue

        # Find end position
        if end_marker:
            end_pos = text.find(end_marker, start_pos)
            if end_pos == -1:
                # Try fuzzy: last 10 chars
                end_pos = text.find(end_marker[-10:], start_pos)
            if end_pos != -1:
                end_pos += len(end_marker)
            else:
                # Fallback: use next chapter's start or end of text
                if i + 1 < len(markers):
                    next_marker = markers[i + 1].get("start_marker", "")
                    next_pos = text.find(next_marker, start_pos + 1) if next_marker else -1
                    end_pos = next_pos if next_pos != -1 else len(text)
                else:
                    end_pos = len(text)
        else:
            # No end marker: use next chapter's start or end of text
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

    return chapters if chapters else None


def _regex_split(text: str) -> list[dict]:
    """Try to split by common chapter markers."""
    pattern = r'(?m)^(第[一二三四五六七八九十百零\d]+[章节回][\s：:]*.*?)$'
    matches = list(re.finditer(pattern, text))
    if len(matches) < 2:
        return []

    chapters = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        title = match.group(1).strip()
        chapters.append({
            "title": title,
            "content": content,
            "order": i,
        })
    return chapters


def extract_characters(text: str, db=None) -> list[dict]:
    """Extract characters from novel text using AI (standard tier)."""
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    prompt = render_prompt("P03_CHARACTER_EXTRACT", text=text[:60000])
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    return _parse_json_response(result["content"], default=[])


def extract_scenes(chapter_text: str, db=None) -> list[dict]:
    """Extract scenes from a chapter using AI (standard tier)."""
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    prompt = render_prompt("P04_SCENE_EXTRACT", text=chapter_text[:40000], character_names="未提取")
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    return _parse_json_response(result["content"], default=[])


def generate_beats(chapter_text: str, prev_scene_emotion: str = "",
                    next_scene_emotion: str = "", db=None) -> list[dict]:
    """Generate beat sheet from a chapter using AI (standard tier)."""
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    prompt = render_prompt(
        "P10_NOVEL_TO_BEAT",
        text=chapter_text[:40000],
        prev_scene_emotion=prev_scene_emotion or "（无前序场景情绪信息）",
        next_scene_emotion=next_scene_emotion or "（无后续场景情绪信息）",
    )
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    return _parse_json_response(result["content"], default=[])


def build_knowledge_base(text: str, db=None) -> dict:
    """Build knowledge base (world building + style guide) from novel text."""
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    prompt = render_prompt("P05_KNOWLEDGE_BASE", text=text[:30000])
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    return _parse_json_response(result["content"], default={
        "world_building": {},
        "style_guide": {},
        "locations": [],
    })


# ─── New Pipeline Functions (v2) ───────────────────────────────────


def split_chapters_chunked(text: str, db=None, chunk_size: int = 20000, overlap: int = 1000) -> list[dict]:
    """Split novel text into chapters using regex first, then chunked AI fallback.

    Splits text into chunks of `chunk_size` characters with `overlap` overlap,
    sends each chunk to AI for chapter boundary detection, then merges results.
    """
    # Try regex-based splitting first
    chapters = _regex_split(text)
    if chapters and len(chapters) > 1:
        logger.info(f"Regex split found {len(chapters)} chapters")
        return chapters

    # Chunked AI fallback
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    all_markers = []
    text_len = len(text)

    if text_len <= chunk_size:
        # Small enough for single call
        prompt = render_prompt("P01_CHAPTER_SPLIT", text=text)
        result = ai_engine.call(
            system=prompt["system"],
            messages=[{"role": "user", "content": prompt["user"]}],
            capability_tier=prompt["capability_tier"],
            temperature=prompt["temperature"],
            max_tokens=prompt["max_tokens"],
            db=db,
        )
        all_markers = _parse_json_response(result["content"], default=[])
    else:
        # Split into overlapping chunks
        start = 0
        chunk_index = 0
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk = text[start:end]

            prompt = render_prompt("P01_CHAPTER_SPLIT", text=chunk)
            try:
                result = ai_engine.call(
                    system=prompt["system"],
                    messages=[{"role": "user", "content": prompt["user"]}],
                    capability_tier=prompt["capability_tier"],
                    temperature=prompt["temperature"],
                    max_tokens=prompt["max_tokens"],
                    db=db,
                )
                chunk_markers = _parse_json_response(result["content"], default=[])
                # Tag markers with chunk offset for dedup
                for m in chunk_markers:
                    m["_chunk_offset"] = start
                all_markers.extend(chunk_markers)
            except Exception as e:
                logger.warning(f"Chunk {chunk_index} chapter split failed: {e}")

            chunk_index += 1
            start = end - overlap if end < text_len else text_len

        # Deduplicate markers that fall in overlap zones
        all_markers = _deduplicate_markers(text, all_markers)

    # Resolve markers to full content
    if all_markers:
        chapters = _resolve_markers(text, all_markers)
        if chapters:
            return chapters

    # Ultimate fallback
    return [{"title": "全文", "content": text, "order": 0}]


def _deduplicate_markers(text: str, markers: list[dict]) -> list[dict]:
    """Deduplicate chapter markers that may appear in overlapping chunks."""
    if not markers:
        return markers

    seen_positions = []
    unique_markers = []
    for m in markers:
        start_marker = m.get("start_marker", "")
        if not start_marker:
            continue
        pos = text.find(start_marker)
        if pos == -1:
            pos = text.find(start_marker[:10])
        if pos == -1:
            continue
        # Check if we already have a marker within 200 chars of this position
        is_dup = False
        for seen_pos in seen_positions:
            if abs(pos - seen_pos) < 200:
                is_dup = True
                break
        if not is_dup:
            seen_positions.append(pos)
            unique_markers.append(m)

    # Sort by position in text
    unique_markers.sort(key=lambda m: text.find(m.get("start_marker", "")[:10]))
    # Re-number order
    for i, m in enumerate(unique_markers):
        m["order"] = i
        m.pop("_chunk_offset", None)

    return unique_markers


def summarize_chapter(chapter_text: str, chapter_title: str, db=None) -> str:
    """Generate a 300-500 word summary for a single chapter."""
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    prompt = render_prompt("P01B_CHAPTER_SUMMARY", text=chapter_text, chapter_title=chapter_title)
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    return result["content"].strip()


def build_synopsis(chapters: list[dict], db=None) -> str:
    """Build full-text synopsis by summarizing each chapter and concatenating."""
    summaries = []
    for ch in chapters:
        title = ch.get("title", "")
        content = ch.get("content", "")
        if not content.strip():
            continue
        try:
            summary = summarize_chapter(content, title, db=db)
            summaries.append(f"【{title}】\n{summary}")
        except Exception as e:
            logger.warning(f"Failed to summarize chapter '{title}': {e}")
            # Fallback: use first 300 chars as summary
            summaries.append(f"【{title}】\n{content[:300]}...")
    return "\n\n".join(summaries)


def extract_character_names(synopsis: str, db=None) -> list[dict]:
    """First-pass character scan: extract character names and brief descriptions from synopsis."""
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    prompt = render_prompt("P03A_CHARACTER_SCAN", synopsis=synopsis)
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    return _parse_json_response(result["content"], default=[])


def extract_character_detail(name: str, brief: str, synopsis: str, all_names: list[str], db=None) -> dict:
    """Second-pass character extraction: detailed profile for a single character."""
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    other_chars = ", ".join(n for n in all_names if n != name)
    prompt = render_prompt(
        "P03B_CHARACTER_DETAIL",
        character_name=name,
        character_brief=brief,
        other_characters=other_chars or "无",
        synopsis=synopsis,
    )
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    parsed = _parse_json_response(result["content"], default={})
    # AI may wrap single object in array — unwrap
    if isinstance(parsed, list) and len(parsed) > 0:
        parsed = parsed[0]
    if not isinstance(parsed, dict):
        parsed = {}
    return parsed


def extract_scenes_with_context(chapter_text: str, character_names: list[str], db=None) -> list[dict]:
    """Extract scenes from a chapter with character name context for consistency."""
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    names_str = ", ".join(character_names) if character_names else "未提取"
    prompt = render_prompt("P04_SCENE_EXTRACT", text=chapter_text[:40000], character_names=names_str)
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    return _parse_json_response(result["content"], default=[])


def build_knowledge_base_v2(synopsis: str, character_names: list[str], location_names: list[str], db=None) -> dict:
    """Build knowledge base from synopsis (not full text), with known entity lists."""
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    chars_str = ", ".join(character_names) if character_names else "未提取"
    locs_str = ", ".join(location_names) if location_names else "未提取"
    prompt = render_prompt(
        "P05_KNOWLEDGE_BASE_V2",
        synopsis=synopsis,
        character_names=chars_str,
        location_names=locs_str,
    )
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    return _parse_json_response(result["content"], default={
        "world_building": {},
        "style_guide": {},
    })


# ─── Scene-Axis Pipeline Functions (v3) ──────────────────────────


def smart_segment(text: str, window_size: int = 20000, overlap: int = 2000) -> list[dict]:
    """Phase 0: Split text into overlapping windows for scene extraction. Zero AI calls.

    Algorithm:
    1. Detect chapter markers (reuse _regex_split patterns)
    2. Step through text by window_size
    3. At each cut point, find nearest chapter marker or paragraph break within ±500 chars
    4. Keep overlap bytes between windows
    5. Record chapter_hints within each window
    """
    if not text or not text.strip():
        return []

    text_len = len(text)
    if text_len <= window_size:
        return [{
            "window_index": 0,
            "text": text,
            "start_offset": 0,
            "end_offset": text_len,
            "chapter_hints": _find_chapter_hints(text, 0),
        }]

    # Find all chapter marker positions
    chapter_pattern = r'(?m)^(第[一二三四五六七八九十百零\d]+[章节回][\s：:]*.*?)$'
    chapter_positions = [m.start() for m in re.finditer(chapter_pattern, text)]

    # Find all paragraph break positions
    para_breaks = [m.start() for m in re.finditer(r'\n\n', text)]

    windows = []
    start = 0
    window_idx = 0

    while start < text_len:
        raw_end = min(start + window_size, text_len)

        if raw_end >= text_len:
            # Last window
            end = text_len
        else:
            # Find best cut point near raw_end (within ±500 chars)
            end = _find_best_cut(raw_end, chapter_positions, para_breaks, text_len, margin=500)

        window_text = text[start:end]
        chapter_hints = _find_chapter_hints(window_text, start)

        windows.append({
            "window_index": window_idx,
            "text": window_text,
            "start_offset": start,
            "end_offset": end,
            "chapter_hints": chapter_hints,
        })

        window_idx += 1
        # Next window starts with overlap
        next_start = end - overlap
        if next_start <= start:
            next_start = end  # Avoid infinite loop
        start = next_start

    logger.info(f"smart_segment: {text_len} chars → {len(windows)} windows")
    return windows


def _find_best_cut(target: int, chapter_positions: list[int], para_breaks: list[int],
                   text_len: int, margin: int = 500) -> int:
    """Find the best cut point near target position."""
    best = target

    # Prefer chapter marker within margin
    for pos in chapter_positions:
        if abs(pos - target) <= margin:
            best = pos
            return best

    # Fallback to nearest paragraph break
    nearest_para = None
    nearest_dist = margin + 1
    for pos in para_breaks:
        dist = abs(pos - target)
        if dist < nearest_dist:
            nearest_dist = dist
            nearest_para = pos
    if nearest_para is not None:
        best = nearest_para

    return min(best, text_len)


def _find_chapter_hints(window_text: str, offset: int) -> list[dict]:
    """Find chapter markers within a window text."""
    pattern = r'(?m)^(第[一二三四五六七八九十百零\d]+[章节回][\s：:]*.*?)$'
    hints = []
    for m in re.finditer(pattern, window_text):
        hints.append({
            "title": m.group(1).strip(),
            "position": offset + m.start(),
        })
    return hints


def extract_scenes_windowed(window_text: str, character_names: list[str],
                            previous_scene_summary: str, window_index: int,
                            db=None) -> list[dict]:
    """Phase 1: Extract scenes from a text window with continuity context.

    Uses enhanced P04_SCENE_EXTRACT template with:
    - Previous window's last scene summary for continuity
    - Known character names for consistency
    - Window index for global ordering reference
    """
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    names_str = ", ".join(character_names) if character_names else "未提取"
    prev_summary = previous_scene_summary or "无（这是第一个窗口）"

    prompt = render_prompt(
        "P04_SCENE_EXTRACT",
        text=window_text[:40000],
        character_names=names_str,
        previous_scene_summary=prev_summary,
        window_index=str(window_index),
    )
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    logger.info(f"extract_scenes_windowed: AI response len={len(result['content'])}, provider={result.get('provider')}")
    scenes = _parse_json_response(result["content"], default=[])
    logger.info(f"extract_scenes_windowed: parsed {len(scenes)} scenes from response")

    # Tag each scene with window_index
    for s in scenes:
        s["window_index"] = window_index

    return scenes


def deduplicate_scenes(all_scenes: list[dict], overlap_chars: int = 50) -> list[dict]:
    """Phase 1 post-processing: Remove duplicate scenes from overlapping windows.

    Deduplication key: normalize(heading) + "|" + normalize(action[:50])
    Uses difflib.SequenceMatcher with ratio > 0.8 threshold.
    Keeps the richer version (longer action + description).
    """
    if not all_scenes:
        return []

    unique_scenes = []
    seen_keys = []

    for scene in all_scenes:
        heading = _normalize(scene.get("heading", ""))
        action_prefix = _normalize(scene.get("action", "")[:overlap_chars])
        key = f"{heading}|{action_prefix}"

        is_dup = False
        dup_idx = -1
        for i, seen_key in enumerate(seen_keys):
            ratio = difflib.SequenceMatcher(None, key, seen_key).ratio()
            if ratio > 0.8:
                is_dup = True
                dup_idx = i
                break

        if is_dup:
            # Keep the richer version
            existing = unique_scenes[dup_idx]
            existing_len = len(existing.get("action", "")) + len(existing.get("description", ""))
            new_len = len(scene.get("action", "")) + len(scene.get("description", ""))
            if new_len > existing_len:
                unique_scenes[dup_idx] = scene
                seen_keys[dup_idx] = key
        else:
            unique_scenes.append(scene)
            seen_keys.append(key)

    # Re-number order
    for i, scene in enumerate(unique_scenes):
        scene["order"] = i

    logger.info(f"deduplicate_scenes: {len(all_scenes)} → {len(unique_scenes)} scenes")
    return unique_scenes


def _normalize(text: str) -> str:
    """Normalize text for comparison: lowercase, strip whitespace, remove punctuation."""
    text = text.lower().strip()
    text = re.sub(r'[\s\.\,\!\?\;\:\-\—\–\(\)\[\]\{\}\'\"\'\'\"\"、，。！？；：（）【】《》]', '', text)
    return text


def decompose_scene_to_shots(scene_json: dict, character_profiles: str,
                              style_guide: str, prev_scene_context: str = "",
                              next_scene_context: str = "", db=None) -> list[dict]:
    """Phase 3: Decompose a scene into individual shot cards.

    Uses existing P06_SCENE_TO_SHOT template.
    """
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    prompt = render_prompt(
        "P06_SCENE_TO_SHOT",
        scene_json=json.dumps(scene_json, ensure_ascii=False),
        character_profiles=character_profiles,
        style_guide=style_guide,
        prev_scene_context=prev_scene_context or "（无前序场景）",
        next_scene_context=next_scene_context or "（无后续场景）",
    )
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    return _parse_json_response(result["content"], default=[])


def merge_shots_to_groups(scene_json: dict, shots_json: list[dict],
                          char_profiles: str, style_guide: str,
                          scene_id: str, target_duration: str = "6s",
                          target_model: str = "jimeng", db=None) -> list[dict]:
    """Phase 4: Merge shots into VFF-format shot groups.

    Uses existing P11_VFF_GENERATE template.
    Merge boundaries based on: character set changes, emotional arc shifts,
    space-time jumps, duration constraints (4-10s).
    """
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    prompt = render_prompt(
        "P11_VFF_GENERATE",
        scene_json=json.dumps(scene_json, ensure_ascii=False),
        shots_json=json.dumps(shots_json, ensure_ascii=False),
        character_profiles=char_profiles,
        style_guide=style_guide,
        target_duration=target_duration,
        scene_id=scene_id,
    )
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    return _parse_json_response(result["content"], default=[])


def generate_visual_prompts(shot_cards: list[dict], character_profiles: str,
                            style_guide: str, db=None) -> list[dict]:
    """Phase 5: Generate visual prompts for shot groups.

    Uses existing P11_VISUAL_PROMPT template.
    Character appearances injected from global profiles for cross-shot visual consistency.
    """
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    prompt = render_prompt(
        "P11_VISUAL_PROMPT",
        shot_cards=json.dumps(shot_cards, ensure_ascii=False),
        character_profiles=character_profiles,
        style_guide=style_guide,
    )
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    return _parse_json_response(result["content"], default=[])


def _parse_json_response(text: str, default):
    """Extract JSON from AI response text."""
    # Try to find JSON in code block
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to parse the whole text as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find array or object in text
    for pattern in [r'(\[[\s\S]*\])', r'(\{[\s\S]*\})']:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    logger.warning(f"Failed to parse JSON from AI response, using default")
    return default


def extract_scenes_standalone(full_text: str, character_names: list[str], ai_engine_instance=None) -> list[dict]:
    """Standalone scene extraction fallback (加固5).

    Used when streaming extraction got characters but zero scenes.
    Reuses P04_SCENE_EXTRACT template with full text and known character names.

    Args:
        full_text: Full novel text (will be truncated to 80K chars).
        character_names: List of known character names from prior extraction.
        ai_engine_instance: Optional AIEngine instance; uses global singleton if None.

    Returns:
        List of scene dicts.
    """
    if ai_engine_instance is None:
        from services.ai_engine import ai_engine as _ai
        ai_engine_instance = _ai
    from services.prompt_templates import render_prompt

    names_str = ", ".join(character_names) if character_names else "未提取"

    prompt = render_prompt(
        "P04_SCENE_EXTRACT",
        text=full_text[:80000],
        character_names=names_str,
        previous_scene_summary="无（独立场景提取模式）",
        window_index="0",
    )
    result = ai_engine_instance.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        operation_type="scene_fallback",
    )
    scenes = _parse_json_response(result["content"], default=[])
    logger.info(f"extract_scenes_standalone: recovered {len(scenes)} scenes")

    # Ensure scene_id and order fields
    for i, s in enumerate(scenes):
        if "scene_id" not in s:
            s["scene_id"] = f"scene_{i + 1:03d}"
        if "order" not in s:
            s["order"] = i

    return scenes
