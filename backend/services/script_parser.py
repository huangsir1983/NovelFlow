"""Script parser — format detection and parsing for Fountain, FDX, and free-form scripts."""

import json
import logging
import re
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


def detect_format(text: str, db=None) -> dict:
    """Detect script format using heuristics + AI fallback.

    Returns: {"format": "fountain"|"fdx"|"custom", "confidence": float}
    """
    # Check for FDX (XML-based)
    if text.strip().startswith('<?xml') or '<FinalDraft' in text[:500]:
        return {"format": "fdx", "confidence": 0.95}

    # Check for Fountain markers
    fountain_score = 0
    fountain_patterns = [
        r'^INT\.',            # INT. scene heading
        r'^EXT\.',            # EXT. scene heading
        r'^INT\./EXT\.',      # INT./EXT. scene heading
        r'^[A-Z ]{2,}$',     # CHARACTER NAME (all caps on its own line)
        r'^\(.*\)$',         # (parenthetical)
        r'^FADE IN:',        # FADE IN:
        r'^FADE OUT',        # FADE OUT
        r'^CUT TO:',         # CUT TO:
        r'^Title:',          # Title page
        r'^Credit:',         # Credit
    ]
    for pattern in fountain_patterns:
        if re.search(pattern, text[:5000], re.MULTILINE):
            fountain_score += 1

    if fountain_score >= 3:
        return {"format": "fountain", "confidence": min(0.5 + fountain_score * 0.1, 0.95)}

    # Fallback: AI-based detection
    try:
        from services.ai_engine import ai_engine
        from services.prompt_templates import render_prompt

        prompt = render_prompt("PS01_FORMAT_DETECT", text=text[:2000])
        result = ai_engine.call(
            system=prompt["system"],
            messages=[{"role": "user", "content": prompt["user"]}],
            capability_tier=prompt["capability_tier"],
            temperature=prompt["temperature"],
            max_tokens=prompt["max_tokens"],
            db=db,
        )
        data = _parse_json(result["content"])
        if data and "format" in data:
            return data
    except Exception as e:
        logger.warning(f"AI format detection failed: {e}")

    return {"format": "custom", "confidence": 0.5}


def parse_fountain(text: str) -> list[dict]:
    """Parse Fountain-format script into structured scenes."""
    scenes = []
    current_scene = None
    current_character = None

    for line in text.split('\n'):
        stripped = line.strip()

        # Scene heading
        if re.match(r'^(INT\.|EXT\.|INT\./EXT\.|I/E\.)\s*', stripped, re.IGNORECASE):
            if current_scene:
                scenes.append(current_scene)

            # Parse heading: INT. LOCATION - TIME
            heading = stripped
            location = ""
            time_of_day = ""
            parts = re.split(r'\s*[-–—]\s*', stripped, maxsplit=1)
            if len(parts) >= 1:
                location = re.sub(r'^(INT\.|EXT\.|INT\./EXT\.|I/E\.)\s*', '', parts[0], flags=re.IGNORECASE).strip()
            if len(parts) >= 2:
                time_of_day = parts[1].strip().lower()
                if 'day' in time_of_day:
                    time_of_day = 'day'
                elif 'night' in time_of_day:
                    time_of_day = 'night'
                elif 'dawn' in time_of_day or 'morning' in time_of_day:
                    time_of_day = 'dawn'
                elif 'dusk' in time_of_day or 'evening' in time_of_day:
                    time_of_day = 'dusk'

            current_scene = {
                "heading": heading,
                "location": location,
                "time_of_day": time_of_day,
                "description": "",
                "action": "",
                "dialogue": [],
                "order": len(scenes),
            }
            current_character = None
            continue

        if not current_scene:
            continue

        # Character name (all caps, possibly with extension)
        if re.match(r'^[A-Z][A-Z\s.\']+(\s*\(.*\))?$', stripped) and len(stripped) < 50:
            current_character = re.sub(r'\s*\(.*\)$', '', stripped).strip()
            continue

        # Parenthetical
        if current_character and re.match(r'^\(.*\)$', stripped):
            continue

        # Dialogue (after character name)
        if current_character and stripped:
            current_scene["dialogue"].append({
                "character": current_character,
                "line": stripped,
            })
            current_character = None
            continue

        # Action / description
        if stripped and not current_character:
            if current_scene["action"]:
                current_scene["action"] += "\n" + stripped
            else:
                current_scene["action"] = stripped

    if current_scene:
        scenes.append(current_scene)

    return scenes


def parse_fdx(text: str) -> list[dict]:
    """Parse Final Draft XML (FDX) format into structured scenes."""
    scenes = []
    current_scene = None
    current_character = None

    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        logger.error(f"FDX XML parse error: {e}")
        return []

    # Find all paragraphs
    for para in root.iter('Paragraph'):
        ptype = para.get('Type', '')
        text_content = ''.join(t.text or '' for t in para.iter('Text')).strip()

        if not text_content:
            continue

        if ptype == 'Scene Heading':
            if current_scene:
                scenes.append(current_scene)

            location = ""
            time_of_day = ""
            parts = re.split(r'\s*[-–—]\s*', text_content, maxsplit=1)
            if len(parts) >= 1:
                location = re.sub(r'^(INT\.|EXT\.|INT\./EXT\.)\s*', '', parts[0], flags=re.IGNORECASE).strip()
            if len(parts) >= 2:
                tod = parts[1].strip().lower()
                time_of_day = 'day' if 'day' in tod else 'night' if 'night' in tod else tod

            current_scene = {
                "heading": text_content,
                "location": location,
                "time_of_day": time_of_day,
                "description": "",
                "action": "",
                "dialogue": [],
                "order": len(scenes),
            }
            current_character = None

        elif ptype == 'Character' and current_scene:
            current_character = text_content

        elif ptype == 'Dialogue' and current_scene and current_character:
            current_scene["dialogue"].append({
                "character": current_character,
                "line": text_content,
            })
            current_character = None

        elif ptype == 'Action' and current_scene:
            if current_scene["action"]:
                current_scene["action"] += "\n" + text_content
            else:
                current_scene["action"] = text_content

    if current_scene:
        scenes.append(current_scene)

    return scenes


def parse_free_text(text: str, db=None) -> list[dict]:
    """Parse free-form script text using AI."""
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    prompt = render_prompt("P13_FREE_SCRIPT_PARSE", text=text[:40000])
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    scenes = _parse_json(result["content"])
    return scenes if isinstance(scenes, list) else []


def standardize(scenes: list[dict]) -> list[dict]:
    """Ensure all scenes conform to the internal JSON schema."""
    standardized = []
    for i, scene in enumerate(scenes):
        standardized.append({
            "heading": scene.get("heading", ""),
            "location": scene.get("location", ""),
            "time_of_day": scene.get("time_of_day", ""),
            "description": scene.get("description", ""),
            "action": scene.get("action", ""),
            "dialogue": scene.get("dialogue", []),
            "order": scene.get("order", i),
            "tension_score": float(scene.get("tension_score", 0.0)),
        })
    return standardized


def _parse_json(text: str):
    """Extract JSON from text."""
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for pattern in [r'(\[[\s\S]*\])', r'(\{[\s\S]*\})']:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
    return None
