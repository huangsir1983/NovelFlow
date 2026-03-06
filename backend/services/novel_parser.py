"""Novel parsing pipeline — file reading, chapter splitting, character/scene extraction, beat generation."""

import json
import logging
import re
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

    prompt = render_prompt("P04_SCENE_EXTRACT", text=chapter_text[:40000])
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    return _parse_json_response(result["content"], default=[])


def generate_beats(chapter_text: str, db=None) -> list[dict]:
    """Generate beat sheet from a chapter using AI (standard tier)."""
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    prompt = render_prompt("P10_NOVEL_TO_BEAT", text=chapter_text[:40000])
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
