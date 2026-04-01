"""Asset enrichment service — location cards, prop cards, character variants.

Post-processing functions for Mode C pipeline Stage 2 & 3.
Ported from: 测试/第10轮测试结果/run_test_round10.py
"""

import json
import re
import logging
from collections import Counter, defaultdict

from services.streaming_parser import extract_json_robust
from services.prompt_templates import render_prompt

logger = logging.getLogger(__name__)


# ─── Stage 2A: Location grouping & card generation ─────────────────


def group_scenes_by_location(narrative_scenes: list[dict]) -> dict:
    """Group narrative scenes by location, collect visual cues.

    Returns dict keyed by location name with aggregated info.
    Ported from run_test_round10.py lines 934-971.
    """
    groups = defaultdict(lambda: {
        "scene_ids": [],
        "time_variations": set(),
        "all_props": set(),
        "all_characters": set(),
        "events": [],
        "emotional_peaks": [],
    })

    for scene in narrative_scenes:
        loc = scene.get("location", "未知地点")
        g = groups[loc]
        g["scene_ids"].append(scene.get("scene_id", ""))
        g["time_variations"].add(scene.get("time_of_day", ""))
        g["all_props"].update(scene.get("key_props", []))
        g["all_characters"].update(scene.get("characters_present", []))
        g["events"].append(scene.get("core_event", ""))
        g["emotional_peaks"].append(scene.get("emotional_peak", ""))

    # Convert sets to sorted lists for JSON serialization
    result = {}
    for loc, g in groups.items():
        result[loc] = {
            "scene_ids": g["scene_ids"],
            "time_variations": sorted(g["time_variations"]),
            "all_props": sorted(g["all_props"]),
            "all_characters": sorted(g["all_characters"]),
            "events": g["events"],
            "emotional_peaks": g["emotional_peaks"],
        }
    return result


def generate_location_cards(groups: dict, full_text: str, ai_engine, db=None) -> list[dict]:
    """Generate location visual asset cards from grouped narrative scenes.

    Ported from run_test_round10.py lines 974-1049.
    Adapted: smart_call() → ai_engine.call(), extract_json() → extract_json_robust().

    Args:
        groups: Output of group_scenes_by_location().
        full_text: Full novel text for snippet extraction.
        ai_engine: AIEngine instance.

    Returns:
        List of location card dicts.
    """
    if not groups:
        logger.info("No location groups — skipping location card generation")
        return []

    # Collect relevant novel snippets
    snippets = []
    for loc_name in groups:
        for m in re.finditer(re.escape(loc_name), full_text):
            start = max(0, m.start() - 150)
            end = min(len(full_text), m.end() + 150)
            snippets.append(f"[{loc_name}] ...{full_text[start:end]}...")
            if len(snippets) >= 30:
                break
        if len(snippets) >= 30:
            break

    groups_json = json.dumps(groups, ensure_ascii=False, indent=2)
    rendered = render_prompt(
        "P_LOCATION_CARD",
        location_groups_json=groups_json,
        relevant_text_snippets="\n".join(snippets[:30]),
    )

    resp = ai_engine.call(
        system=rendered["system"],
        messages=[{"role": "user", "content": rendered["user"]}],
        capability_tier=rendered["capability_tier"],
        temperature=rendered["temperature"],
        max_tokens=rendered["max_tokens"],
        operation_type="location_card",
        db=db,
    )

    location_cards = []
    try:
        cards = extract_json_robust(resp["content"])
        if not isinstance(cards, list):
            cards = [cards]
        for i, card in enumerate(cards):
            if not card.get("location_id"):
                card["location_id"] = f"loc_{i + 1:03d}"
            location_cards.append(card)
        logger.info(f"Location cards generated: {len(location_cards)}")
    except Exception as e:
        logger.warning(f"Location card parse failed: {e}")

    return location_cards


# ─── Stage 2B: Prop collection & tiering ──────────────────────────


def collect_and_tier_props(narrative_scenes: list[dict], top_n: int = 10) -> dict:
    """Collect props from ALL narrative scenes, deduplicate, keep only top_n by frequency.

    Rules:
    - Deduplicate by name, count appearances
    - Keep only top_n props by appearance count (all treated as major)
    - Minor props are discarded entirely
    """
    prop_counter = Counter()
    prop_scenes = defaultdict(list)

    for scene in narrative_scenes:
        scene_id = scene.get("scene_id", "")
        for prop in scene.get("key_props", []):
            prop = prop.strip()
            if not prop:
                continue
            prop_counter[prop] += 1
            if scene_id not in prop_scenes[prop]:
                prop_scenes[prop].append(scene_id)

    # Only keep top_n props by appearance count
    top_props = prop_counter.most_common(top_n)

    major_props = {
        p: {"count": c, "scenes": prop_scenes[p]}
        for p, c in top_props
    }

    return {
        "major": major_props,
        "minor": {},
        "total_unique": len(prop_counter),
        "top_n": top_n,
        "major_count": len(major_props),
        "minor_count": 0,
    }


# ─── Stage 2C: Prop card generation ──────────────────────────────


def generate_prop_cards(major_props: dict, full_text: str, ai_engine, db=None) -> list[dict]:
    """Generate prop visual asset cards for major props.

    Ported from run_test_round10.py run_phase2() lines 1121-1158.

    Args:
        major_props: Dict of major props {name: {count, scenes}}.
        full_text: Full novel text for snippet extraction.
        ai_engine: AIEngine instance.

    Returns:
        List of prop card dicts.
    """
    if not major_props:
        logger.info("No major props — skipping prop card generation")
        return []

    prop_list_str = json.dumps(major_props, ensure_ascii=False, indent=2)

    # Extract relevant novel snippets for each prop
    snippets = []
    for prop_name in major_props:
        for m in re.finditer(re.escape(prop_name), full_text):
            start = max(0, m.start() - 100)
            end = min(len(full_text), m.end() + 100)
            snippets.append(f"[{prop_name}] ...{full_text[start:end]}...")
            if len(snippets) >= 20:
                break
        if len(snippets) >= 20:
            break

    rendered = render_prompt(
        "P_PROP_CARD",
        prop_list_with_scenes=prop_list_str,
        relevant_text_snippets="\n".join(snippets[:20]),
    )

    resp = ai_engine.call(
        system=rendered["system"],
        messages=[{"role": "user", "content": rendered["user"]}],
        capability_tier=rendered["capability_tier"],
        temperature=rendered["temperature"],
        max_tokens=rendered["max_tokens"],
        operation_type="prop_card",
        db=db,
    )

    prop_cards = []
    try:
        cards = extract_json_robust(resp["content"])
        if not isinstance(cards, list):
            cards = [cards]
        prop_cards = cards
        logger.info(f"Prop cards generated: {len(prop_cards)}")
    except Exception as e:
        logger.warning(f"Prop card parse failed: {e}")

    return prop_cards


# ─── Stage 3: Character variant generation ────────────────────────


def generate_character_variant(char_data: dict, char_scenes: list[dict], ai_engine, db=None) -> list[dict]:
    """Generate character variants for a single character.

    Ported from run_test_round10.py run_phase3() gen_variant() lines 1203-1239.
    Adapted: smart_call() → ai_engine.call().

    Args:
        char_data: Character profile dict.
        char_scenes: List of narrative scene dicts where character appears.
        ai_engine: AIEngine instance.

    Returns:
        List of variant dicts.
    """
    name = char_data.get("name", "unnamed")

    rendered = render_prompt(
        "P_CHARACTER_VARIANT",
        character_card_json=json.dumps(char_data, ensure_ascii=False, indent=2),
        character_scenes_json=json.dumps(char_scenes, ensure_ascii=False, indent=2),
    )

    resp = ai_engine.call(
        system=rendered["system"],
        messages=[{"role": "user", "content": rendered["user"]}],
        capability_tier=rendered["capability_tier"],
        temperature=rendered["temperature"],
        max_tokens=rendered["max_tokens"],
        operation_type="character_variant",
        db=db,
    )

    try:
        variants = extract_json_robust(resp["content"])
        if not isinstance(variants, list):
            variants = [variants]
        logger.info(f"Character variants for '{name}': {len(variants)}")
        return variants
    except Exception as e:
        logger.warning(f"Variant parse failed for '{name}': {e}")
        return []


# ─── Minor prop visual generation ────────────────────────────────


def generate_minor_prop_visuals(
    minor_props: dict, era_context: str, ai_engine, db=None
) -> list[dict]:
    """Batch-generate basic visual prompts for minor props.

    Uses P_MINOR_PROP_VISUAL template to generate visual_reference +
    visual_prompt_negative for all minor props in a single AI call.

    Args:
        minor_props: Dict of minor props {name: {count, scenes}}.
        era_context: Era/period context string from knowledge base.
        ai_engine: AIEngine instance.

    Returns:
        List of dicts with name, visual_reference, visual_prompt_negative.
    """
    if not minor_props:
        logger.info("No minor props — skipping minor prop visual generation")
        return []

    # Build simple list for the prompt
    prop_list = [
        {"name": name, "scenes": info.get("scenes", []), "count": info.get("count", 0)}
        for name, info in minor_props.items()
    ]

    rendered = render_prompt(
        "P_MINOR_PROP_VISUAL",
        era_context=era_context or "未知时代背景",
        minor_props_json=json.dumps(prop_list, ensure_ascii=False, indent=2),
    )

    resp = ai_engine.call(
        system=rendered["system"],
        messages=[{"role": "user", "content": rendered["user"]}],
        capability_tier=rendered["capability_tier"],
        temperature=rendered["temperature"],
        max_tokens=rendered["max_tokens"],
        operation_type="minor_prop_visual",
        db=db,
    )

    try:
        results = extract_json_robust(resp["content"])
        if not isinstance(results, list):
            results = [results]
        logger.info(f"Minor prop visuals generated: {len(results)}")
        return results
    except Exception as e:
        logger.warning(f"Minor prop visual parse failed: {e}")
        return []
