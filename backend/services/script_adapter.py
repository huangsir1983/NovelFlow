"""Script adapter — reverse engineering beats and knowledge from parsed scripts."""

import json
import logging

logger = logging.getLogger(__name__)


def reverse_extract_beats(scenes_json: str, db=None) -> list[dict]:
    """PS02: Reverse-extract beats from parsed script scenes."""
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    prompt = render_prompt("PS02_REVERSE_BEATS", text=scenes_json[:40000])
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    return _parse_json_list(result["content"])


def reverse_build_knowledge(scenes_json: str, db=None) -> dict:
    """PS03: Reverse-build knowledge base from parsed script."""
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    prompt = render_prompt("PS03_REVERSE_KNOWLEDGE", text=scenes_json[:40000])
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    data = _parse_json_obj(result["content"])
    return data or {"world_building": {}, "style_guide": {}, "locations": [], "characters": []}


def assess_visual_readiness(scenes_json: str, db=None) -> dict:
    """PS04: Assess storyboard readiness of parsed script scenes."""
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    prompt = render_prompt("PS04_VISUAL_READINESS", text=scenes_json[:40000])
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    data = _parse_json_obj(result["content"])
    return data or {"overall_score": 0.0, "scenes": [], "recommendations": []}


def optimize_for_storyboard(scenes_json: str, db=None) -> list[dict]:
    """PS05: Optimize scenes for storyboard production."""
    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    prompt = render_prompt("PS05_STORYBOARD_OPTIMIZE", text=scenes_json[:40000])
    result = ai_engine.call(
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
        capability_tier=prompt["capability_tier"],
        temperature=prompt["temperature"],
        max_tokens=prompt["max_tokens"],
        db=db,
    )
    return _parse_json_list(result["content"])


def _parse_json_list(text: str) -> list[dict]:
    """Parse JSON list from AI response."""
    import re
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        try:
            result = json.loads(json_match.group(1))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    return []


def _parse_json_obj(text: str) -> dict | None:
    """Parse JSON object from AI response."""
    import re
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        try:
            result = json.loads(json_match.group(1))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass
    return None
