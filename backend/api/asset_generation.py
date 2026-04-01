"""Asset on-demand generation API — characters, props, locations, variants.

Endpoints:
  POST /projects/{id}/assets/generate/characters   — batch character generation from scenes
  POST /projects/{id}/assets/generate/props         — batch prop generation from scenes
  POST /projects/{id}/assets/generate/locations      — batch location generation from scenes
  POST /projects/{id}/assets/generate/variants       — batch variant generation from characters
  POST /projects/{id}/assets/regenerate/{type}/{asset_id} — single asset regeneration
"""

import json
import logging
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models.project import Project
from models.scene import Scene
from models.character import Character
from models.location import Location
from models.prop import Prop
from models.character_variant import CharacterVariant
from models.import_task import ImportTask
from services.ai_engine import ai_engine
from services.asset_enrichment import (
    group_scenes_by_location,
    generate_location_cards,
    generate_prop_cards,
    generate_character_variant,
    collect_and_tier_props,
    generate_minor_prop_visuals,
)
from services.streaming_parser import extract_json_robust
from services.prompt_templates import render_prompt
from services.event_bus import push_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["assets"])

_asset_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="asset_gen")

# ─── Task status tracking ─────────────────────────────────────────
# In-memory dict: { "project_id:asset_type" -> { status, generated, total } }
_generation_status: dict[str, dict] = {}


def _status_key(project_id: str, asset_type: str) -> str:
    return f"{project_id}:{asset_type}"


def _set_status(project_id: str, asset_type: str, status: str, generated: int = 0, total: int = 0):
    _generation_status[_status_key(project_id, asset_type)] = {
        "status": status,
        "generated": generated,
        "total": total,
    }


def _clear_status(project_id: str, asset_type: str):
    _generation_status.pop(_status_key(project_id, asset_type), None)


# ─── Request / Response Models ────────────────────────────────────

class GenerateRequest(BaseModel):
    mode: str = "overwrite"  # "overwrite" | "enhance"


class RegenerateResponse(BaseModel):
    success: bool
    message: str


# ─── Helpers ──────────────────────────────────────────────────────

def _get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _load_scenes_as_dicts(db: Session, project_id: str) -> list[dict]:
    """Load all scenes for a project as dicts (matching enrichment input format)."""
    scenes = (
        db.query(Scene)
        .filter(Scene.project_id == project_id)
        .order_by(Scene.order)
        .all()
    )
    return [
        {
            "scene_id": f"scene_{i + 1:03d}",
            "heading": s.heading or "",
            "location": s.location or "",
            "time_of_day": s.time_of_day or "",
            "description": s.description or "",
            "action": s.action or "",
            "dialogue": s.dialogue or [],
            "characters_present": s.characters_present or [],
            "key_props": s.key_props or [],
            "core_event": s.core_event or "",
            "key_dialogue": s.key_dialogue or "",
            "emotional_peak": s.emotional_peak or "",
            "estimated_duration_s": s.estimated_duration_s,
            "source_text_start": s.source_text_start or "",
            "source_text_end": s.source_text_end or "",
            "edited_source_text": s.edited_source_text or "",
            "_db_id": s.id,
        }
        for i, s in enumerate(scenes)
    ]


def _get_full_text(db: Session, project_id: str) -> str:
    """Get the original novel full text from the import task."""
    task = (
        db.query(ImportTask)
        .filter(ImportTask.project_id == project_id)
        .order_by(ImportTask.created_at.desc())
        .first()
    )
    return task.full_text if task and task.full_text else ""


def _get_scene_source_text(scene: dict, max_chars: int = 1500) -> str:
    """Extract source text for a scene, preferring edited_source_text."""
    text = scene.get("edited_source_text", "")
    if not text:
        start = scene.get("source_text_start", "")
        end = scene.get("source_text_end", "")
        text = f"{start}\n...\n{end}" if start or end else ""
    return text[:max_chars]


def _push_asset_event(project_id: str, event_type: str, data: dict):
    """Push an asset generation event via event bus."""
    # Use project_id as the channel (same as import events)
    task = None
    db = SessionLocal()
    try:
        task = (
            db.query(ImportTask)
            .filter(ImportTask.project_id == project_id)
            .order_by(ImportTask.created_at.desc())
            .first()
        )
    finally:
        db.close()
    if task:
        push_event(task.id, {"type": event_type, "phase": "asset_generation", "data": data})


# ─── Character Generation ────────────────────────────────────────

def _generate_characters_task(project_id: str, mode: str):
    """Background task: generate characters from scene data."""
    _set_status(project_id, "character", "running")
    db = SessionLocal()
    try:
        scenes_data = _load_scenes_as_dicts(db, project_id)
        if not scenes_data:
            logger.warning(f"No scenes found for project {project_id}")
            _set_status(project_id, "character", "done")
            return

        full_text = _get_full_text(db, project_id)

        # Collect all characters from scenes
        char_counter = Counter()
        char_scenes = defaultdict(list)
        for scene in scenes_data:
            for char_name in scene.get("characters_present", []):
                char_name = char_name.strip()
                if not char_name:
                    continue
                char_counter[char_name] += 1
                char_scenes[char_name].append(scene)

        if not char_counter:
            logger.warning(f"No characters found in scenes for project {project_id}")
            _set_status(project_id, "character", "done")
            return

        # Handle mode
        if mode == "overwrite":
            db.query(Character).filter(Character.project_id == project_id).delete()
            db.commit()

        existing_names = set()
        if mode == "enhance":
            existing = db.query(Character).filter(Character.project_id == project_id).all()
            existing_names = {c.name for c in existing}

        total = len(char_counter)
        generated = 0
        _set_status(project_id, "character", "running", generated, total)

        for char_name, count in char_counter.most_common():
            if mode == "enhance" and char_name in existing_names:
                generated += 1
                _set_status(project_id, "character", "running", generated, total)
                continue

            # Collect source texts from character's scenes (up to ~3000 chars)
            source_texts = []
            total_len = 0
            for scene in char_scenes[char_name]:
                st = _get_scene_source_text(scene, max_chars=800)
                if st and total_len + len(st) < 3000:
                    source_texts.append(st)
                    total_len += len(st)

            # Also search full text for character name context
            import re
            if full_text:
                for m in re.finditer(re.escape(char_name), full_text):
                    start = max(0, m.start() - 200)
                    end = min(len(full_text), m.end() + 200)
                    snippet = full_text[start:end]
                    if total_len + len(snippet) < 3000:
                        source_texts.append(f"...{snippet}...")
                        total_len += len(snippet)
                    if total_len >= 3000:
                        break

            # Build AI prompt using P_CHAR_ONLY_EXTRACT with focused input
            context_text = f"角色名: {char_name}\n出场次数: {count}\n\n相关原文:\n" + "\n---\n".join(source_texts)

            rendered = render_prompt(
                "P_CHAR_ONLY_EXTRACT",
                text=context_text,
            )

            try:
                resp = ai_engine.call(
                    system=rendered["system"],
                    messages=[{"role": "user", "content": rendered["user"]}],
                    capability_tier=rendered["capability_tier"],
                    temperature=rendered["temperature"],
                    max_tokens=rendered["max_tokens"],
                    operation_type="character_generation",
                    db=db,
                )

                result = extract_json_robust(resp["content"])
                chars = result.get("characters", [result]) if isinstance(result, dict) else result
                if not isinstance(chars, list):
                    chars = [chars]

                # Find the matching character (or use the first one)
                char_data = None
                for c in chars:
                    if c.get("name", "").strip() == char_name:
                        char_data = c
                        break
                if not char_data and chars:
                    char_data = chars[0]
                    char_data["name"] = char_name

                if char_data:
                    character = Character(
                        id=str(uuid4()),
                        project_id=project_id,
                        name=char_data.get("name", char_name),
                        aliases=char_data.get("aliases", []),
                        role=char_data.get("role", "supporting"),
                        description=char_data.get("description", ""),
                        personality=char_data.get("personality", ""),
                        arc=char_data.get("arc", ""),
                        relationships=char_data.get("relationships", []),
                        age_range=char_data.get("age_range", ""),
                        appearance=char_data.get("appearance", {}),
                        costume=char_data.get("costume", {}),
                        casting_tags=char_data.get("casting_tags", []),
                        visual_reference=char_data.get("visual_reference", ""),
                        visual_prompt_negative=char_data.get("visual_prompt_negative", ""),
                        desire=char_data.get("desire", ""),
                        flaw=char_data.get("flaw", ""),
                        scene_presence=char_data.get("scene_presence", ""),
                    )
                    db.add(character)
                    db.commit()  # commit per character so frontend can poll

                generated += 1
                _set_status(project_id, "character", "running", generated, total)
                _push_asset_event(project_id, "character_generated", {
                    "name": char_name,
                    "index": generated,
                    "total": total,
                })
                logger.info(f"Character generated: {char_name} ({generated}/{total})")

            except Exception as e:
                logger.warning(f"Failed to generate character '{char_name}': {e}")
                generated += 1
                _set_status(project_id, "character", "running", generated, total)

        _set_status(project_id, "character", "done", generated, total)
        _push_asset_event(project_id, "characters_complete", {"count": generated})
        logger.info(f"Character generation complete for project {project_id}: {generated} characters")

    except Exception as e:
        logger.error(f"Character generation failed: {e}", exc_info=True)
        _set_status(project_id, "character", "error", 0, 0)
        db.rollback()
    finally:
        db.close()


# ─── Prop Generation ──────────────────────────────────────────────

def _generate_props_task(project_id: str, mode: str):
    """Background task: generate props from scene data."""
    _set_status(project_id, "prop", "running")
    db = SessionLocal()
    try:
        scenes_data = _load_scenes_as_dicts(db, project_id)
        if not scenes_data:
            _set_status(project_id, "prop", "done")
            return

        full_text = _get_full_text(db, project_id)

        # Collect and tier props
        tiered = collect_and_tier_props(scenes_data)
        major_props = tiered["major"]
        minor_props = tiered["minor"]

        if mode == "overwrite":
            db.query(Prop).filter(Prop.project_id == project_id).delete()
            db.commit()

        existing_names = set()
        if mode == "enhance":
            existing = db.query(Prop).filter(Prop.project_id == project_id).all()
            existing_names = {p.name for p in existing}

        total = tiered["major_count"] + tiered["minor_count"]
        _set_status(project_id, "prop", "running", 0, total)

        # Generate major prop cards via AI
        if major_props:
            filtered_major = {k: v for k, v in major_props.items() if k not in existing_names} if mode == "enhance" else major_props
            if filtered_major:
                cards = generate_prop_cards(filtered_major, full_text, ai_engine, db=db)
                for card in cards:
                    prop_name = card.get("name", "")
                    prop = Prop(
                        id=str(uuid4()),
                        project_id=project_id,
                        name=prop_name,
                        category=card.get("category", ""),
                        description=card.get("description", ""),
                        visual_reference=card.get("visual_reference", ""),
                        visual_prompt_negative=card.get("visual_prompt_negative", ""),
                        narrative_function=card.get("narrative_function", ""),
                        is_motif=card.get("is_motif", False),
                        is_major=True,
                        scenes_present=card.get("scenes_present", major_props.get(prop_name, {}).get("scenes", [])),
                        appearance_count=major_props.get(prop_name, {}).get("count", 0),
                        emotional_association=card.get("emotional_association", ""),
                    )
                    db.add(prop)
                db.commit()
                _set_status(project_id, "prop", "running", len(cards), total)
                _push_asset_event(project_id, "props_major_done", {"count": len(cards)})

        # Generate minor prop visuals
        if minor_props:
            filtered_minor = {k: v for k, v in minor_props.items() if k not in existing_names} if mode == "enhance" else minor_props
            if filtered_minor:
                visuals = generate_minor_prop_visuals(filtered_minor, "", ai_engine, db=db)
                for vis in visuals:
                    prop_name = vis.get("name", "")
                    minor_info = minor_props.get(prop_name, {})
                    prop = Prop(
                        id=str(uuid4()),
                        project_id=project_id,
                        name=prop_name,
                        category="",
                        description="",
                        visual_reference=vis.get("visual_reference", ""),
                        visual_prompt_negative=vis.get("visual_prompt_negative", ""),
                        is_major=False,
                        scenes_present=minor_info.get("scenes", []),
                        appearance_count=minor_info.get("count", 0),
                    )
                    db.add(prop)
                db.commit()
                _push_asset_event(project_id, "props_minor_done", {"count": len(visuals)})

        _set_status(project_id, "prop", "done", total, total)
        _push_asset_event(project_id, "props_complete", {
            "major": tiered["major_count"],
            "minor": tiered["minor_count"],
        })
        logger.info(f"Props generation complete for project {project_id}")

    except Exception as e:
        logger.error(f"Props generation failed: {e}", exc_info=True)
        _set_status(project_id, "prop", "error")
        db.rollback()
    finally:
        db.close()


# ─── Location Generation ─────────────────────────────────────────

def _generate_locations_task(project_id: str, mode: str):
    """Background task: generate locations from scene data."""
    _set_status(project_id, "location", "running")
    db = SessionLocal()
    try:
        scenes_data = _load_scenes_as_dicts(db, project_id)
        if not scenes_data:
            _set_status(project_id, "location", "done")
            return

        full_text = _get_full_text(db, project_id)

        # Group scenes by location
        groups = group_scenes_by_location(scenes_data)
        if not groups:
            _set_status(project_id, "location", "done")
            return

        if mode == "overwrite":
            db.query(Location).filter(Location.project_id == project_id).delete()
            db.commit()

        existing_names = set()
        if mode == "enhance":
            existing = db.query(Location).filter(Location.project_id == project_id).all()
            existing_names = {loc.name for loc in existing}

        # Filter groups if enhance mode
        filtered_groups = {k: v for k, v in groups.items() if k not in existing_names} if mode == "enhance" else groups

        if not filtered_groups:
            _set_status(project_id, "location", "done")
            _push_asset_event(project_id, "locations_complete", {"count": 0})
            return

        total = len(filtered_groups)
        _set_status(project_id, "location", "running", 0, total)

        # Generate location cards via AI
        cards = generate_location_cards(filtered_groups, full_text, ai_engine, db=db)

        for i, card in enumerate(cards):
            card["location_id"] = f"loc_{i + 1:03d}"
            loc_name = card.get("name", f"unnamed_{i}")
            location = Location(
                id=str(uuid4()),
                project_id=project_id,
                name=loc_name,
                description=card.get("description", ""),
                visual_description=card.get("description", ""),
                type=card.get("type", ""),
                era_style=card.get("era_style", ""),
                visual_reference=card.get("visual_reference", ""),
                visual_prompt_negative=card.get("visual_prompt_negative", ""),
                atmosphere=card.get("atmosphere", ""),
                color_palette=card.get("color_palette", []),
                lighting=card.get("lighting", ""),
                key_features=card.get("key_features", []),
                narrative_scene_ids=card.get("narrative_scenes", []),
                scene_count=card.get("scene_count", 0),
                time_variations=card.get("time_variations", []),
                emotional_range=card.get("emotional_range", ""),
            )
            db.add(location)

        db.commit()
        _set_status(project_id, "location", "done", len(cards), total)
        _push_asset_event(project_id, "locations_complete", {"count": len(cards)})
        logger.info(f"Location generation complete for project {project_id}: {len(cards)} locations")

    except Exception as e:
        logger.error(f"Location generation failed: {e}", exc_info=True)
        _set_status(project_id, "location", "error")
        db.rollback()
    finally:
        db.close()


# ─── Variant Generation ──────────────────────────────────────────

def _generate_variants_task(project_id: str, mode: str):
    """Background task: generate character variants."""
    _set_status(project_id, "variant", "running")
    db = SessionLocal()
    try:
        characters = db.query(Character).filter(Character.project_id == project_id).all()
        if not characters:
            logger.warning(f"No characters found for variant generation in project {project_id}")
            _set_status(project_id, "variant", "done")
            return

        scenes_data = _load_scenes_as_dicts(db, project_id)

        if mode == "overwrite":
            db.query(CharacterVariant).filter(CharacterVariant.project_id == project_id).delete()
            db.commit()

        total = len(characters)
        generated = 0
        _set_status(project_id, "variant", "running", generated, total)

        for char in characters:
            char_data = {
                "name": char.name,
                "aliases": char.aliases or [],
                "role": char.role or "supporting",
                "personality": char.personality or "",
                "appearance": char.appearance or {},
                "costume": char.costume or {},
                "arc": char.arc or "",
                "desire": char.desire or "",
                "flaw": char.flaw or "",
            }

            # Find scenes where this character appears
            char_scenes = [
                s for s in scenes_data
                if char.name in s.get("characters_present", [])
            ]

            try:
                variants = generate_character_variant(char_data, char_scenes, ai_engine, db=db)
                for v in variants:
                    variant = CharacterVariant(
                        id=str(uuid4()),
                        project_id=project_id,
                        character_id=char.id,
                        variant_type=v.get("variant_type", ""),
                        variant_name=v.get("variant_name", ""),
                        tags=v.get("tags", []),
                        scene_ids=v.get("scene_ids", []),
                        trigger=v.get("trigger", ""),
                        appearance_delta=v.get("appearance_delta", {}),
                        costume_override=v.get("costume_override", {}),
                        visual_reference=v.get("visual_reference", ""),
                        visual_prompt_negative=v.get("visual_prompt_negative", ""),
                        emotional_tone=v.get("emotional_tone", ""),
                    )
                    db.add(variant)
                db.commit()  # commit per character so frontend can poll

                generated += 1
                _set_status(project_id, "variant", "running", generated, total)
                _push_asset_event(project_id, "variant_generated", {
                    "character": char.name,
                    "variant_count": len(variants),
                    "index": generated,
                    "total": total,
                })

            except Exception as e:
                logger.warning(f"Variant generation failed for '{char.name}': {e}")
                generated += 1
                _set_status(project_id, "variant", "running", generated, total)

        _set_status(project_id, "variant", "done", generated, total)
        _push_asset_event(project_id, "variants_complete", {"count": generated})
        logger.info(f"Variant generation complete for project {project_id}")

    except Exception as e:
        logger.error(f"Variant generation failed: {e}", exc_info=True)
        _set_status(project_id, "variant", "error")
        db.rollback()
    finally:
        db.close()


# ─── Single Asset Regeneration ────────────────────────────────────

def _regenerate_single_asset(project_id: str, asset_type: str, asset_id: str):
    """Background task: regenerate a single asset."""
    db = SessionLocal()
    try:
        scenes_data = _load_scenes_as_dicts(db, project_id)
        full_text = _get_full_text(db, project_id)

        if asset_type == "character":
            char = db.query(Character).filter(Character.id == asset_id).first()
            if not char:
                return

            # Find scenes where this character appears
            char_scenes = [s for s in scenes_data if char.name in s.get("characters_present", [])]
            source_texts = []
            total_len = 0
            for scene in char_scenes:
                st = _get_scene_source_text(scene, max_chars=800)
                if st and total_len + len(st) < 3000:
                    source_texts.append(st)
                    total_len += len(st)

            import re
            if full_text:
                for m in re.finditer(re.escape(char.name), full_text):
                    start = max(0, m.start() - 200)
                    end = min(len(full_text), m.end() + 200)
                    snippet = full_text[start:end]
                    if total_len + len(snippet) < 3000:
                        source_texts.append(f"...{snippet}...")
                        total_len += len(snippet)
                    if total_len >= 3000:
                        break

            context_text = f"角色名: {char.name}\n\n相关原文:\n" + "\n---\n".join(source_texts)
            rendered = render_prompt("P_CHAR_ONLY_EXTRACT", text=context_text)

            resp = ai_engine.call(
                system=rendered["system"],
                messages=[{"role": "user", "content": rendered["user"]}],
                capability_tier=rendered["capability_tier"],
                temperature=rendered["temperature"],
                max_tokens=rendered["max_tokens"],
                operation_type="character_regeneration",
                db=db,
            )

            result = extract_json_robust(resp["content"])
            chars = result.get("characters", [result]) if isinstance(result, dict) else result
            if not isinstance(chars, list):
                chars = [chars]

            char_data = chars[0] if chars else {}
            if char_data:
                char.aliases = char_data.get("aliases", char.aliases)
                char.role = char_data.get("role", char.role)
                char.description = char_data.get("description", char.description)
                char.personality = char_data.get("personality", char.personality)
                char.arc = char_data.get("arc", char.arc)
                char.relationships = char_data.get("relationships", char.relationships)
                char.age_range = char_data.get("age_range", char.age_range)
                char.appearance = char_data.get("appearance", char.appearance)
                char.costume = char_data.get("costume", char.costume)
                char.casting_tags = char_data.get("casting_tags", char.casting_tags)
                char.visual_reference = char_data.get("visual_reference", char.visual_reference)
                char.visual_prompt_negative = char_data.get("visual_prompt_negative", char.visual_prompt_negative)
                char.desire = char_data.get("desire", char.desire)
                char.flaw = char_data.get("flaw", char.flaw)
                char.scene_presence = char_data.get("scene_presence", char.scene_presence)

        elif asset_type == "prop":
            prop = db.query(Prop).filter(Prop.id == asset_id).first()
            if not prop:
                return

            major_props = {prop.name: {"count": prop.appearance_count, "scenes": prop.scenes_present or []}}
            cards = generate_prop_cards(major_props, full_text, ai_engine, db=db)
            if cards:
                card = cards[0]
                prop.category = card.get("category", prop.category)
                prop.description = card.get("description", prop.description)
                prop.visual_reference = card.get("visual_reference", prop.visual_reference)
                prop.visual_prompt_negative = card.get("visual_prompt_negative", prop.visual_prompt_negative)
                prop.narrative_function = card.get("narrative_function", prop.narrative_function)
                prop.is_motif = card.get("is_motif", prop.is_motif)
                prop.emotional_association = card.get("emotional_association", prop.emotional_association)

        elif asset_type == "location":
            loc = db.query(Location).filter(Location.id == asset_id).first()
            if not loc:
                return

            groups = {loc.name: {
                "scene_ids": loc.narrative_scene_ids or [],
                "time_variations": loc.time_variations or [],
                "all_props": [],
                "all_characters": [],
                "events": [],
                "emotional_peaks": [],
            }}
            # Re-collect from scenes
            for scene in scenes_data:
                if scene.get("location", "") == loc.name:
                    groups[loc.name]["all_props"].extend(scene.get("key_props", []))
                    groups[loc.name]["all_characters"].extend(scene.get("characters_present", []))
                    groups[loc.name]["events"].append(scene.get("core_event", ""))
                    groups[loc.name]["emotional_peaks"].append(scene.get("emotional_peak", ""))

            cards = generate_location_cards(groups, full_text, ai_engine, db=db)
            if cards:
                card = cards[0]
                loc.description = card.get("description", loc.description)
                loc.visual_description = card.get("description", loc.visual_description)
                loc.type = card.get("type", loc.type)
                loc.era_style = card.get("era_style", loc.era_style)
                loc.visual_reference = card.get("visual_reference", loc.visual_reference)
                loc.visual_prompt_negative = card.get("visual_prompt_negative", loc.visual_prompt_negative)
                loc.atmosphere = card.get("atmosphere", loc.atmosphere)
                loc.color_palette = card.get("color_palette", loc.color_palette)
                loc.lighting = card.get("lighting", loc.lighting)
                loc.key_features = card.get("key_features", loc.key_features)
                loc.time_variations = card.get("time_variations", loc.time_variations)
                loc.emotional_range = card.get("emotional_range", loc.emotional_range)

        db.commit()
        _push_asset_event(project_id, "asset_regenerated", {
            "type": asset_type,
            "id": asset_id,
        })
        logger.info(f"Asset regenerated: {asset_type}/{asset_id}")

    except Exception as e:
        logger.error(f"Asset regeneration failed: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


# ─── API Endpoints ────────────────────────────────────────────────

@router.post("/projects/{project_id}/assets/generate/characters")
def generate_characters(
    project_id: str,
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Batch generate characters from scene data."""
    _get_project_or_404(db, project_id)

    scenes = db.query(Scene).filter(Scene.project_id == project_id).count()
    if scenes == 0:
        raise HTTPException(status_code=400, detail="No scenes found. Import a novel first.")

    background_tasks.add_task(_generate_characters_task, project_id, req.mode)
    return {"status": "started", "message": f"Character generation started (mode={req.mode})"}


@router.post("/projects/{project_id}/assets/generate/props")
def generate_props(
    project_id: str,
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Batch generate props from scene data."""
    _get_project_or_404(db, project_id)

    scenes = db.query(Scene).filter(Scene.project_id == project_id).count()
    if scenes == 0:
        raise HTTPException(status_code=400, detail="No scenes found. Import a novel first.")

    background_tasks.add_task(_generate_props_task, project_id, req.mode)
    return {"status": "started", "message": f"Props generation started (mode={req.mode})"}


@router.post("/projects/{project_id}/assets/generate/locations")
def generate_locations(
    project_id: str,
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Batch generate locations from scene data."""
    _get_project_or_404(db, project_id)

    scenes = db.query(Scene).filter(Scene.project_id == project_id).count()
    if scenes == 0:
        raise HTTPException(status_code=400, detail="No scenes found. Import a novel first.")

    background_tasks.add_task(_generate_locations_task, project_id, req.mode)
    return {"status": "started", "message": f"Location generation started (mode={req.mode})"}


@router.post("/projects/{project_id}/assets/generate/variants")
def generate_variants(
    project_id: str,
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Batch generate character variants."""
    _get_project_or_404(db, project_id)

    chars = db.query(Character).filter(Character.project_id == project_id).count()
    if chars == 0:
        raise HTTPException(status_code=400, detail="No characters found. Generate characters first.")

    background_tasks.add_task(_generate_variants_task, project_id, req.mode)
    return {"status": "started", "message": f"Variant generation started (mode={req.mode})"}


@router.post("/projects/{project_id}/assets/regenerate/{asset_type}/{asset_id}")
def regenerate_asset(
    project_id: str,
    asset_type: str,
    asset_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Regenerate a single asset."""
    _get_project_or_404(db, project_id)

    if asset_type not in ("character", "prop", "location"):
        raise HTTPException(status_code=400, detail=f"Invalid asset type: {asset_type}")

    # Verify asset exists
    model_map = {"character": Character, "prop": Prop, "location": Location}
    model = model_map[asset_type]
    asset = db.query(model).filter(model.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail=f"{asset_type} not found")

    background_tasks.add_task(_regenerate_single_asset, project_id, asset_type, asset_id)
    return {"status": "started", "message": f"Regenerating {asset_type}/{asset_id}"}


@router.get("/projects/{project_id}/assets/generate/status")
def get_generation_status(
    project_id: str,
    db: Session = Depends(get_db),
):
    """Get the current status of all asset generation tasks for a project."""
    _get_project_or_404(db, project_id)

    result = {}
    for asset_type in ("character", "prop", "location", "variant"):
        key = _status_key(project_id, asset_type)
        if key in _generation_status:
            result[asset_type] = _generation_status[key]
        else:
            result[asset_type] = {"status": "idle", "generated": 0, "total": 0}

    return result
