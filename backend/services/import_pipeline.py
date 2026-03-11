"""Import pipeline executor — R29 dual-stream extraction with asset enrichment.

Pipeline stages:
  Phase: streaming   — R29 dual-stream: character stream + scene stream in parallel
  Phase: enrichment  — locations (progressive) + props + variants (parallel, overlapped with streaming)
  Phase: knowledge   — knowledge base construction (1 AI call)
  Phase: shots+merge — per-scene shot decompose + beats + merge in parallel (unchanged)
  Phase: prompts     — parallel visual prompt generation per scene (unchanged)

R29 optimizations:
  - Dual-stream separation (char stream + scene stream in parallel)
  - Character garbage filtering (_is_valid_char)
  - Early variant start (only waits for chars, not scenes)
  - Progressive location card firing (every 4 new locations)
  - Location ID forced sequential override
"""

import logging
import time
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4
from typing import Any

from sqlalchemy.orm import Session

from models.chapter import Chapter
from models.beat import Beat
from models.scene import Scene
from models.character import Character
from models.location import Location
from models.knowledge_base import KnowledgeBase
from models.import_task import ImportTask
from models.shot import Shot
from models.shot_group import ShotGroup
from models.prop import Prop
from models.character_variant import CharacterVariant

logger = logging.getLogger(__name__)

# Concurrency settings — kept low to bound total threads per process
MAX_VARIANT_CONCURRENCY = 2
MAX_SCENE_CONCURRENCY = 2
MAX_PROMPT_CONCURRENCY = 2
# Maximum retries per AI call
MAX_RETRIES = 2
# Streaming retry settings (加固1)
MAX_STREAM_RETRIES = 3
# Maximum response buffer size (chars) — stop accumulating after this
MAX_RESPONSE_BUFFER_CHARS = 500_000
# Batch flush sizes for DB writes
CHAR_FLUSH_BATCH = 5
SCENE_FLUSH_BATCH = 10


def _safe_float(val, default: float = 0.0) -> float:
    """B2.3: Safe numeric conversion with fallback."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


class ImportPipeline:
    """Orchestrates the full novel import pipeline with Mode C streaming extraction.

    Mode C: single streaming AI call extracts characters + scenes simultaneously,
    followed by asset enrichment (locations, props, variants) and shot pipeline.
    """

    PHASES = ["streaming", "enrichment", "knowledge",
              "shots", "merging", "prompts"]

    # Active pipelines for graceful shutdown
    _active_pipelines: list["ImportPipeline"] = []
    _active_lock = threading.Lock()

    def __init__(self, task_id: str, project_id: str, full_text: str, db_factory):
        self.task_id = task_id
        self.project_id = project_id
        self.full_text = full_text
        self.db_factory = db_factory  # callable that returns a new Session
        self._cancelled = False
        self._progress_lock = threading.Lock()
        self._scene_fallback_done = False  # B2.1: prevent double scene fallback

    def _emit(self, event: dict):
        """Thread-safe: push an SSE event via the Redis event bus."""
        from services.event_bus import push_event
        event["timestamp"] = time.time()
        push_event(self.task_id, event)

    def _call_with_retry(self, fn, *args, retries: int = MAX_RETRIES, **kwargs):
        """Call fn with exponential backoff retry."""
        last_exc = None
        for attempt in range(retries + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                last_exc = e
                if attempt < retries:
                    wait = 2 ** attempt
                    logger.warning(f"Retry {attempt + 1}/{retries} for {fn.__name__} after {wait}s: {e}")
                    time.sleep(wait)
        raise last_exc

    # ─── Per-scene character profile filtering ────────────────────

    @staticmethod
    def _filter_char_profiles(all_profiles: list[dict], characters_present: list[str]) -> str:
        """Return JSON string of character profiles filtered to scene-relevant characters."""
        if not characters_present:
            return json.dumps(all_profiles, ensure_ascii=False)

        present_lower = {n.lower().strip() for n in characters_present if n}
        filtered = [p for p in all_profiles if p["name"].lower().strip() in present_lower]
        result = filtered if filtered else all_profiles
        return json.dumps(result, ensure_ascii=False)

    # ─── R29: Character garbage filter ─────────────────────────────

    @staticmethod
    def _is_valid_char(c: dict) -> bool:
        """R29: 严格校验 — 必须有 name + 至少一个角色专属字段."""
        name = c.get("name")
        if not name or not isinstance(name, str) or len(name.strip()) == 0:
            return False
        char_fields = {"role", "age_range", "personality", "appearance", "visual_reference", "arc"}
        return bool(char_fields & set(c.keys()))

    # ─── R29: Dual-stream extraction ─────────────────────────────

    # Location card batch size for progressive firing
    LOC_BATCH_SIZE = 4

    def _stream_characters(self, db: Session) -> list[dict]:
        """R29: 角色独立流式提取 (threading 版)."""
        from services.ai_engine import ai_engine
        from services.streaming_parser import ProgressiveAssetParser, extract_json_robust
        from services.prompt_templates import render_prompt

        text_for_prompt = self.full_text[:80000]
        rendered = render_prompt("P_CHAR_ONLY_EXTRACT", text=text_for_prompt)

        parser = ProgressiveAssetParser()
        response_chunks: list[str] = []
        response_total_chars = 0
        chunk_count = 0
        char_count = 0
        characters_data = []

        logger.info("R29 dual-stream: character stream starting")

        try:
            stream = ai_engine.stream(
                system=rendered["system"],
                messages=[{"role": "user", "content": rendered["user"]}],
                capability_tier=rendered["capability_tier"],
                temperature=rendered["temperature"],
                max_tokens=rendered["max_tokens"],
            )

            for chunk in stream:
                if response_total_chars < MAX_RESPONSE_BUFFER_CHARS:
                    response_chunks.append(chunk)
                    response_total_chars += len(chunk)
                chunk_count += 1

                if chunk_count % 100 == 0 and self._cancelled:
                    break

                result = parser.feed(chunk)

                for char in result["characters"]:
                    if not self._is_valid_char(char):
                        continue
                    name = char.get("name", f"unknown_{char_count}")
                    char_id = str(uuid4())
                    character = Character(
                        id=char_id,
                        project_id=self.project_id,
                        name=name,
                        aliases=char.get("aliases", []),
                        role=char.get("role", "supporting"),
                        description=char.get("description", ""),
                        personality=char.get("personality", ""),
                        arc=char.get("arc", ""),
                        relationships=char.get("relationships", []),
                        age_range=char.get("age_range", ""),
                        appearance=char.get("appearance", {}),
                        costume=char.get("costume", {}),
                        casting_tags=char.get("casting_tags", []),
                        visual_reference=char.get("visual_reference", ""),
                        visual_prompt_negative=char.get("visual_prompt_negative", ""),
                        desire=char.get("desire", ""),
                        flaw=char.get("flaw", ""),
                    )
                    db.add(character)
                    if char_count % CHAR_FLUSH_BATCH == 0:
                        db.flush()
                    char["_db_id"] = char_id
                    char_count += 1

                    self._emit({
                        "type": "character_found",
                        "phase": "streaming",
                        "data": {"name": name, "role": char.get("role", ""), "index": char_count - 1},
                    })

        except Exception as e:
            logger.warning(f"R29 character stream error: {e}")

        # Post-stream: 完整响应恢复 + R29 严格过滤
        characters_data = [c for c in parser.found_chars if self._is_valid_char(c)]
        if response_chunks:
            full_response = "".join(response_chunks)
            try:
                parsed = extract_json_robust(full_response)
                parsed_chars = []
                if isinstance(parsed, dict):
                    parsed_chars = parsed.get("characters", [])
                elif isinstance(parsed, list):
                    parsed_chars = parsed
                parsed_chars = [c for c in parsed_chars if self._is_valid_char(c)]
                if len(parsed_chars) >= len(characters_data) and parsed_chars:
                    if len(parsed_chars) > len(characters_data):
                        logger.info(f"R29 char recovery: {len(characters_data)} -> {len(parsed_chars)}")
                    characters_data = parsed_chars
                    # Write recovered chars to DB
                    for i, char in enumerate(characters_data):
                        if "_db_id" not in char:
                            char_id = str(uuid4())
                            character = Character(
                                id=char_id,
                                project_id=self.project_id,
                                name=char.get("name", f"unknown_{i}"),
                                aliases=char.get("aliases", []),
                                role=char.get("role", "supporting"),
                                description=char.get("description", ""),
                                personality=char.get("personality", ""),
                                arc=char.get("arc", ""),
                                relationships=char.get("relationships", []),
                                age_range=char.get("age_range", ""),
                                appearance=char.get("appearance", {}),
                                costume=char.get("costume", {}),
                                casting_tags=char.get("casting_tags", []),
                                visual_reference=char.get("visual_reference", ""),
                                visual_prompt_negative=char.get("visual_prompt_negative", ""),
                                desire=char.get("desire", ""),
                                flaw=char.get("flaw", ""),
                            )
                            db.add(character)
                            char["_db_id"] = char_id
                    db.flush()
            except Exception as e:
                logger.warning(f"R29 char full-response parse failed: {e}")

        db.flush()
        db.commit()

        # Signal: characters done
        self._characters_data = characters_data
        self._chars_done.set()

        logger.info(f"R29 character stream done: {len(characters_data)} valid characters")
        return characters_data

    def _stream_scenes(self, db: Session) -> list[dict]:
        """R29: 场景独立流式提取 + 渐进位置卡发射 (threading 版)."""
        from services.ai_engine import ai_engine
        from services.streaming_parser import ProgressiveAssetParser, extract_json_robust
        from services.prompt_templates import render_prompt
        from collections import defaultdict

        text_for_prompt = self.full_text[:80000]
        rendered = render_prompt("P_SCENE_ONLY_EXTRACT", text=text_for_prompt)

        parser = ProgressiveAssetParser()
        parser._chars_closed = True  # skip char scanning, only scan scenes

        response_chunks: list[str] = []
        response_total_chars = 0
        chunk_count = 0
        scene_count = 0
        scenes_data = []

        # Progressive location grouping
        loc_groups = {}
        unfired_locs = []
        fired_locs = set()
        batch_idx = 0

        def _add_scene_to_groups(scene_obj):
            nonlocal batch_idx
            loc = scene_obj.get("location", "未知地点")
            if loc not in loc_groups:
                loc_groups[loc] = {
                    "scene_ids": [],
                    "time_variations": set(),
                    "all_props": set(),
                    "all_characters": set(),
                    "events": [],
                    "emotional_peaks": [],
                }
                if loc not in fired_locs:
                    unfired_locs.append(loc)

            g = loc_groups[loc]
            g["scene_ids"].append(scene_obj.get("scene_id", ""))
            g["time_variations"].add(scene_obj.get("time_of_day", ""))
            g["all_props"].update(scene_obj.get("key_props", []))
            g["all_characters"].update(scene_obj.get("characters_present", []))
            g["events"].append(scene_obj.get("core_event", ""))
            g["emotional_peaks"].append(scene_obj.get("emotional_peak", ""))

            # Fire batch when enough locations accumulated
            if len(unfired_locs) >= self.LOC_BATCH_SIZE:
                _fire_loc_batch()

        def _fire_loc_batch():
            nonlocal batch_idx
            batch_locs = unfired_locs[:self.LOC_BATCH_SIZE]
            del unfired_locs[:self.LOC_BATCH_SIZE]
            batch_groups = {}
            for loc_name in batch_locs:
                g = loc_groups[loc_name]
                batch_groups[loc_name] = {
                    "scene_ids": g["scene_ids"],
                    "time_variations": sorted(g["time_variations"]),
                    "all_props": sorted(g["all_props"]),
                    "all_characters": sorted(g["all_characters"]),
                    "events": g["events"],
                    "emotional_peaks": g["emotional_peaks"],
                }
                fired_locs.add(loc_name)

            idx = batch_idx
            batch_idx += 1
            logger.info(f"R29 progressive loc batch {idx+1}: {list(batch_groups.keys())}")
            future = self._loc_executor.submit(
                self._gen_location_batch, batch_groups, idx)
            self._loc_futures.append(future)

        logger.info("R29 dual-stream: scene stream starting")

        try:
            stream = ai_engine.stream(
                system=rendered["system"],
                messages=[{"role": "user", "content": rendered["user"]}],
                capability_tier=rendered["capability_tier"],
                temperature=rendered["temperature"],
                max_tokens=rendered["max_tokens"],
            )

            for chunk in stream:
                if response_total_chars < MAX_RESPONSE_BUFFER_CHARS:
                    response_chunks.append(chunk)
                    response_total_chars += len(chunk)
                chunk_count += 1

                if chunk_count % 100 == 0 and self._cancelled:
                    break

                result = parser.feed(chunk)

                for scene_obj in result["scenes"]:
                    scene_id_str = f"scene_{scene_count + 1:03d}"
                    scene_obj["scene_id"] = scene_id_str
                    if "order" not in scene_obj:
                        scene_obj["order"] = scene_count

                    db_scene_id = str(uuid4())
                    scene = Scene(
                        id=db_scene_id,
                        project_id=self.project_id,
                        heading=scene_obj.get("heading", ""),
                        location=scene_obj.get("location", ""),
                        time_of_day=scene_obj.get("time_of_day", ""),
                        description=scene_obj.get("description", ""),
                        action=scene_obj.get("action", ""),
                        dialogue=scene_obj.get("dialogue", []),
                        order=scene_obj.get("order", scene_count),
                        tension_score=_safe_float(scene_obj.get("tension_score", 0.0)),
                        characters_present=scene_obj.get("characters_present", []),
                        key_props=scene_obj.get("key_props", []),
                        dramatic_purpose=scene_obj.get("dramatic_purpose", ""),
                        core_event=scene_obj.get("core_event", ""),
                        key_dialogue=scene_obj.get("key_dialogue", ""),
                        emotional_peak=scene_obj.get("emotional_peak", ""),
                        estimated_duration_s=scene_obj.get("estimated_duration_s"),
                    )
                    db.add(scene)
                    if scene_count % SCENE_FLUSH_BATCH == 0:
                        db.flush()
                    scene_obj["_db_id"] = db_scene_id
                    scene_count += 1

                    # Progressive location grouping
                    _add_scene_to_groups(scene_obj)
                    # R29: share with variant pipeline
                    self._streaming_scenes.append(scene_obj)

                    self._emit({
                        "type": "scene_found",
                        "phase": "streaming",
                        "data": {
                            "scene_id": scene_id_str,
                            "location": scene_obj.get("location", ""),
                            "core_event": (scene_obj.get("core_event", ""))[:60],
                            "index": scene_count - 1,
                        },
                    })

        except Exception as e:
            logger.warning(f"R29 scene stream error: {e}")

        # Post-stream: recover from full response
        scenes_data = parser.found_scenes
        if response_chunks:
            full_response = "".join(response_chunks)
            try:
                parsed = extract_json_robust(full_response)
                if isinstance(parsed, dict):
                    parsed_scenes = parsed.get("scenes", [])
                    if len(parsed_scenes) > len(scenes_data):
                        logger.info(f"R29 scene recovery: {len(scenes_data)} -> {len(parsed_scenes)}")
                        scenes_data = parsed_scenes
                        for i, scene_obj in enumerate(scenes_data):
                            scene_id_str = f"scene_{i + 1:03d}"
                            scene_obj["scene_id"] = scene_id_str
                            if "order" not in scene_obj:
                                scene_obj["order"] = i
                            if "_db_id" not in scene_obj:
                                db_scene_id = str(uuid4())
                                scene = Scene(
                                    id=db_scene_id,
                                    project_id=self.project_id,
                                    heading=scene_obj.get("heading", ""),
                                    location=scene_obj.get("location", ""),
                                    time_of_day=scene_obj.get("time_of_day", ""),
                                    description=scene_obj.get("description", ""),
                                    action=scene_obj.get("action", ""),
                                    dialogue=scene_obj.get("dialogue", []),
                                    order=scene_obj.get("order", i),
                                    tension_score=_safe_float(scene_obj.get("tension_score", 0.0)),
                                    characters_present=scene_obj.get("characters_present", []),
                                    key_props=scene_obj.get("key_props", []),
                                    dramatic_purpose=scene_obj.get("dramatic_purpose", ""),
                                    core_event=scene_obj.get("core_event", ""),
                                    key_dialogue=scene_obj.get("key_dialogue", ""),
                                    emotional_peak=scene_obj.get("emotional_peak", ""),
                                    estimated_duration_s=scene_obj.get("estimated_duration_s"),
                                )
                                db.add(scene)
                                scene_obj["_db_id"] = db_scene_id
                            # Add recovered scenes to loc groups
                            _add_scene_to_groups(scene_obj)
                        db.flush()
            except Exception as e:
                logger.warning(f"R29 scene full-response parse failed: {e}")

        # Fire remaining unfired location batch
        if unfired_locs:
            _fire_loc_batch()

        db.flush()
        db.commit()

        # Signal: scenes done
        self._scenes_data = scenes_data
        self._scenes_done.set()

        logger.info(f"R29 scene stream done: {len(scenes_data)} scenes, "
                     f"{batch_idx} loc batches fired")
        return scenes_data

    def _gen_location_batch(self, batch_groups: dict, batch_idx: int) -> list[dict]:
        """R29: 生成一批位置卡 (线程版)."""
        import re
        from services.ai_engine import ai_engine
        from services.streaming_parser import extract_json_robust
        from services.prompt_templates import render_prompt

        snippets = []
        for loc_name in batch_groups:
            for m in re.finditer(re.escape(loc_name), self.full_text):
                start = max(0, m.start() - 150)
                end = min(len(self.full_text), m.end() + 150)
                snippets.append(f"[{loc_name}] ...{self.full_text[start:end]}...")
                if len(snippets) >= 10:
                    break
            if len(snippets) >= 10:
                break

        groups_json = json.dumps(
            {k: {kk: (sorted(vv) if isinstance(vv, set) else vv) for kk, vv in v.items()}
             for k, v in batch_groups.items()},
            ensure_ascii=False, indent=2,
        )
        rendered = render_prompt(
            "P_LOCATION_CARD",
            location_groups_json=groups_json,
            relevant_text_snippets="\n".join(snippets[:10]),
        )

        resp = ai_engine.call(
            system=rendered["system"],
            messages=[{"role": "user", "content": rendered["user"]}],
            capability_tier=rendered["capability_tier"],
            temperature=rendered["temperature"],
            max_tokens=rendered["max_tokens"],
            operation_type="location_card_batch",
        )

        try:
            cards = extract_json_robust(resp["content"])
            if not isinstance(cards, list):
                cards = [cards]
            logger.info(f"R29 loc batch {batch_idx+1}: {len(cards)} cards generated")
            return cards
        except Exception as e:
            logger.warning(f"R29 loc batch {batch_idx+1} parse failed: {e}")
            return []

    def _run_variants_early(self, db: Session):
        """R29: 变体仅等角色完成, 使用 streaming_scenes 快照."""
        if not self._chars_done.wait(timeout=600):
            logger.warning("R29 variants: timed out waiting for characters")
            return

        snap_scenes = list(self._streaming_scenes)
        logger.info(f"R29 variants early: {len(self._characters_data)} chars, "
                     f"{len(snap_scenes)} streaming scenes available")

        if self._characters_data and snap_scenes:
            self._run_character_variants(db, self._characters_data, snap_scenes)
        elif self._characters_data and not snap_scenes:
            # Edge case: char stream finished before any scenes arrived
            logger.info("R29 variants: no streaming scenes, waiting for scene stream")
            if not self._scenes_done.wait(timeout=600):
                logger.warning("R29 variants: timed out waiting for scenes")
                return
            if self._scenes_data:
                self._run_character_variants(db, self._characters_data, self._scenes_data)

    def _run_props_after_scenes(self, db: Session):
        """R29: 道具收集仅等场景完成."""
        if not self._scenes_done.wait(timeout=600):
            logger.warning("R29 props: timed out waiting for scenes")
            return
        if self._scenes_data:
            self._collect_and_save_props(db, self._scenes_data)

    def _run_dual_stream_extraction(self, db: Session) -> tuple[list[dict], list[dict]]:
        """R29: 双流分离提取 — 角色流 + 场景流并行, 变体提前启动, 渐进位置卡.

        Falls back to _run_streaming_extraction on failure.
        """
        # Initialize shared state
        self._chars_done = threading.Event()
        self._scenes_done = threading.Event()
        self._streaming_scenes = []  # thread-safe: list.append is atomic in CPython
        self._characters_data = []
        self._scenes_data = []
        self._loc_futures = []

        try:
            with ThreadPoolExecutor(max_workers=6) as executor:
                self._loc_executor = executor

                # Submit dual streams
                char_future = executor.submit(self._stream_characters, self.db_factory())
                scene_future = executor.submit(self._stream_scenes, self.db_factory())

                # Submit variants (waits for chars_done internally)
                variant_future = executor.submit(self._run_variants_early, self.db_factory())

                # Submit props (waits for scenes_done internally)
                props_future = executor.submit(self._run_props_after_scenes, self.db_factory())

                # Wait for dual streams to complete
                characters_data = char_future.result(timeout=900)
                scenes_data = scene_future.result(timeout=900)

                # Wait for loc batch futures
                all_location_cards = []
                for loc_future in self._loc_futures:
                    try:
                        cards = loc_future.result(timeout=300)
                        if isinstance(cards, list):
                            all_location_cards.extend(cards)
                    except Exception as e:
                        logger.warning(f"R29 loc batch failed: {e}")

                # R29-fix: 强制顺序覆盖 location_id
                for i, card in enumerate(all_location_cards):
                    card["location_id"] = f"loc_{i + 1:03d}"

                # Write location cards to main DB
                for i, card in enumerate(all_location_cards):
                    loc_name = card.get("name", f"unnamed_{i}")
                    location = Location(
                        id=str(uuid4()),
                        project_id=self.project_id,
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

                    self._emit({
                        "type": "location_card",
                        "phase": "enrichment",
                        "data": {
                            "name": loc_name,
                            "scene_count": card.get("scene_count", 0),
                            "index": i,
                            "total": len(all_location_cards),
                        },
                    })

                db.flush()

                # Wait for enrichment tasks
                try:
                    variant_future.result(timeout=600)
                except Exception as e:
                    logger.warning(f"R29 variants failed (non-fatal): {e}")
                try:
                    props_future.result(timeout=600)
                except Exception as e:
                    logger.warning(f"R29 props failed (non-fatal): {e}")

            logger.info(f"R29 dual-stream complete: {len(characters_data)} chars, "
                         f"{len(scenes_data)} scenes, {len(all_location_cards)} loc cards")
            return characters_data, scenes_data

        except Exception as e:
            logger.error(f"R29 dual-stream failed, falling back to single stream: {e}",
                          exc_info=True)
            # Ensure events are set so any waiting threads don't block
            self._chars_done.set()
            self._scenes_done.set()
            return self._run_streaming_extraction(db)

    # ─── Mode C Stage 1: Streaming combined extraction (fallback) ──

    def _run_streaming_extraction(self, db: Session) -> tuple[list[dict], list[dict]]:
        """Stage 1: Streaming combined extraction of characters + narrative scenes.

        Returns:
            (characters_data, scenes_data) — raw dicts from AI extraction.

        Implements 加固1 (retry), 加固4 (truncation), 加固5 (scene fallback), 加固6 (non-stream fallback).
        """
        from services.ai_engine import ai_engine
        from services.streaming_parser import (
            ProgressiveAssetParser, extract_json_robust,
            is_truncated, estimate_max_tokens,
        )
        from services.prompt_templates import render_prompt
        from services.novel_parser import smart_segment

        # Use smart_segment just for chapter hints (metadata)
        windows = smart_segment(self.full_text)
        all_hints = []
        for w in windows:
            all_hints.extend(w.get("chapter_hints", []))
        if all_hints:
            for i, hint in enumerate(all_hints):
                chapter = Chapter(
                    id=str(uuid4()),
                    project_id=self.project_id,
                    title=hint.get("title", f"章节{i + 1}"),
                    content="",
                    order=i,
                    word_count=0,
                )
                db.add(chapter)

        # Prepare prompt
        text_for_prompt = self.full_text[:80000]  # limit to 80K chars
        rendered = render_prompt("P_COMBINED_EXTRACT", text=text_for_prompt)
        adaptive_max_tokens = estimate_max_tokens(len(text_for_prompt))
        max_tokens = max(rendered["max_tokens"], adaptive_max_tokens)  # 加固4

        # Save full_text for retry
        task = db.query(ImportTask).filter(ImportTask.id == self.task_id).first()
        if task:
            task.full_text = self.full_text
            db.commit()

        characters_data = []
        scenes_data = []

        # 加固1: retry loop for streaming
        for attempt in range(MAX_STREAM_RETRIES):
            parser = ProgressiveAssetParser()
            response_chunks: list[str] = []
            response_total_chars = 0
            chunk_count = 0
            char_count = 0
            scene_count = 0

            try:
                logger.info(f"Streaming extraction attempt {attempt + 1}/{MAX_STREAM_RETRIES}")

                # Try streaming first
                try:
                    stream = ai_engine.stream(
                        system=rendered["system"],
                        messages=[{"role": "user", "content": rendered["user"]}],
                        capability_tier=rendered["capability_tier"],
                        temperature=rendered["temperature"],
                        max_tokens=max_tokens,
                    )

                    for chunk in stream:
                        # Buffer cap: stop accumulating after limit
                        if response_total_chars < MAX_RESPONSE_BUFFER_CHARS:
                            response_chunks.append(chunk)
                            response_total_chars += len(chunk)
                        chunk_count += 1

                        # Check cancel every 100 chunks
                        if chunk_count % 100 == 0 and self._cancelled:
                            return characters_data, scenes_data

                        result = parser.feed(chunk)

                        # Characters arrive → write DB + emit SSE
                        for char in result["characters"]:
                            name = char.get("name", f"unknown_{char_count}")
                            char_id = str(uuid4())
                            character = Character(
                                id=char_id,
                                project_id=self.project_id,
                                name=name,
                                aliases=char.get("aliases", []),
                                role=char.get("role", "supporting"),
                                description=char.get("description", ""),
                                personality=char.get("personality", ""),
                                arc=char.get("arc", ""),
                                relationships=char.get("relationships", []),
                                age_range=char.get("age_range", ""),
                                appearance=char.get("appearance", {}),
                                costume=char.get("costume", {}),
                                casting_tags=char.get("casting_tags", []),
                                visual_reference=char.get("visual_reference", ""),
                                visual_prompt_negative=char.get("visual_prompt_negative", ""),
                                desire=char.get("desire", ""),
                                flaw=char.get("flaw", ""),
                            )
                            db.add(character)
                            # Batch flush: every CHAR_FLUSH_BATCH characters
                            if char_count % CHAR_FLUSH_BATCH == 0:
                                db.flush()
                            char["_db_id"] = char_id
                            char_count += 1

                            self._emit({
                                "type": "character_found",
                                "phase": "streaming",
                                "data": {"name": name, "role": char.get("role", ""), "index": char_count - 1},
                            })

                        # Scenes arrive → write DB + emit SSE
                        for scene_obj in result["scenes"]:
                            scene_id_str = f"scene_{scene_count + 1:03d}"
                            scene_obj["scene_id"] = scene_id_str
                            if "order" not in scene_obj:
                                scene_obj["order"] = scene_count

                            db_scene_id = str(uuid4())
                            scene = Scene(
                                id=db_scene_id,
                                project_id=self.project_id,
                                heading=scene_obj.get("heading", ""),
                                location=scene_obj.get("location", ""),
                                time_of_day=scene_obj.get("time_of_day", ""),
                                description=scene_obj.get("description", ""),
                                action=scene_obj.get("action", ""),
                                dialogue=scene_obj.get("dialogue", []),
                                order=scene_obj.get("order", scene_count),
                                tension_score=_safe_float(scene_obj.get("tension_score", 0.0)),
                                characters_present=scene_obj.get("characters_present", []),
                                key_props=scene_obj.get("key_props", []),
                                dramatic_purpose=scene_obj.get("dramatic_purpose", ""),
                                core_event=scene_obj.get("core_event", ""),
                                key_dialogue=scene_obj.get("key_dialogue", ""),
                                emotional_peak=scene_obj.get("emotional_peak", ""),
                                estimated_duration_s=scene_obj.get("estimated_duration_s"),
                            )
                            db.add(scene)
                            # Batch flush: every SCENE_FLUSH_BATCH scenes
                            if scene_count % SCENE_FLUSH_BATCH == 0:
                                db.flush()
                            scene_obj["_db_id"] = db_scene_id
                            scene_count += 1

                            self._emit({
                                "type": "scene_found",
                                "phase": "streaming",
                                "data": {
                                    "scene_id": scene_id_str,
                                    "location": scene_obj.get("location", ""),
                                    "core_event": (scene_obj.get("core_event", ""))[:60],
                                    "index": scene_count - 1,
                                },
                            })

                except Exception as stream_err:
                    # 加固6: chunk_count==0 means streaming not supported → fallback
                    if chunk_count == 0:
                        logger.warning(f"Streaming returned 0 chunks, falling back to non-streaming: {stream_err}")
                        characters_data, scenes_data = self._run_non_streaming_fallback(
                            db, rendered, max_tokens)
                        return characters_data, scenes_data

                    # 加固1: partial streaming — check if chars complete
                    if parser.is_chars_complete():
                        logger.warning(f"Stream interrupted after chars complete, will recover scenes: {stream_err}")
                        characters_data = parser.found_chars
                        # Save checkpoint
                        if task:
                            task.stream_checkpoint = parser.get_checkpoint()
                            db.commit()
                        # Run scene fallback
                        scenes_data = self._run_scene_fallback(
                            db, [c.get("name", "") for c in characters_data])
                        return characters_data, scenes_data
                    else:
                        # Chars not complete → retry with backoff
                        if attempt < MAX_STREAM_RETRIES - 1:
                            wait = 10 * (attempt + 1)
                            logger.warning(f"Stream failed mid-chars, retrying in {wait}s: {stream_err}")
                            time.sleep(wait)
                            continue
                        else:
                            raise

                # 加固6: chunk_count==0 after loop (empty stream)
                if chunk_count == 0 or response_total_chars == 0:
                    logger.warning("Streaming returned empty content, falling back to non-streaming")
                    characters_data, scenes_data = self._run_non_streaming_fallback(
                        db, rendered, max_tokens)
                    return characters_data, scenes_data

                # Flush any remaining unflushed entities
                db.flush()

                # Streaming completed — collect results
                characters_data = parser.found_chars
                scenes_data = parser.found_scenes

                # Post-stream fallback: if parser didn't extract scenes, try full parse
                if not scenes_data:
                    logger.info("No scenes from streaming parser, trying full JSON parse")
                    full_response = "".join(response_chunks)
                    try:
                        parsed = extract_json_robust(full_response)
                        if isinstance(parsed, dict):
                            if not characters_data:
                                characters_data = parsed.get("characters", [])
                                for i, char in enumerate(characters_data):
                                    char_id = str(uuid4())
                                    character = Character(
                                        id=char_id,
                                        project_id=self.project_id,
                                        name=char.get("name", f"unknown_{i}"),
                                        aliases=char.get("aliases", []),
                                        role=char.get("role", "supporting"),
                                        description=char.get("description", ""),
                                        personality=char.get("personality", ""),
                                        arc=char.get("arc", ""),
                                        relationships=char.get("relationships", []),
                                        age_range=char.get("age_range", ""),
                                        appearance=char.get("appearance", {}),
                                        costume=char.get("costume", {}),
                                        casting_tags=char.get("casting_tags", []),
                                        visual_reference=char.get("visual_reference", ""),
                                        visual_prompt_negative=char.get("visual_prompt_negative", ""),
                                        desire=char.get("desire", ""),
                                        flaw=char.get("flaw", ""),
                                    )
                                    db.add(character)
                                    char["_db_id"] = char_id
                                db.flush()

                            scenes_data = parsed.get("scenes", [])
                            for i, scene_obj in enumerate(scenes_data):
                                scene_id_str = f"scene_{i + 1:03d}"
                                scene_obj["scene_id"] = scene_id_str
                                if "order" not in scene_obj:
                                    scene_obj["order"] = i
                                db_scene_id = str(uuid4())
                                scene = Scene(
                                    id=db_scene_id,
                                    project_id=self.project_id,
                                    heading=scene_obj.get("heading", ""),
                                    location=scene_obj.get("location", ""),
                                    time_of_day=scene_obj.get("time_of_day", ""),
                                    description=scene_obj.get("description", ""),
                                    action=scene_obj.get("action", ""),
                                    dialogue=scene_obj.get("dialogue", []),
                                    order=scene_obj.get("order", i),
                                    tension_score=_safe_float(scene_obj.get("tension_score", 0.0)),
                                    characters_present=scene_obj.get("characters_present", []),
                                    key_props=scene_obj.get("key_props", []),
                                    dramatic_purpose=scene_obj.get("dramatic_purpose", ""),
                                    core_event=scene_obj.get("core_event", ""),
                                    key_dialogue=scene_obj.get("key_dialogue", ""),
                                    emotional_peak=scene_obj.get("emotional_peak", ""),
                                    estimated_duration_s=scene_obj.get("estimated_duration_s"),
                                )
                                db.add(scene)
                                scene_obj["_db_id"] = db_scene_id
                            db.flush()
                    except Exception as e:
                        logger.warning(f"Full JSON parse also failed: {e}")

                # 加固4: truncation detection
                if not scenes_data and characters_data:
                    full_response_for_check = "".join(response_chunks) if not scenes_data else ""
                    if full_response_for_check and is_truncated(full_response_for_check):
                        logger.warning("Response appears truncated — running scene fallback")
                        scenes_data = self._run_scene_fallback(
                            db, [c.get("name", "") for c in characters_data])

                # 加固5: scenes==0 && chars>0 → fallback
                if len(scenes_data) == 0 and len(characters_data) > 0:
                    logger.warning("Got characters but zero scenes — running scene fallback")
                    scenes_data = self._run_scene_fallback(
                        db, [c.get("name", "") for c in characters_data])

                db.commit()
                logger.info(f"Streaming extraction complete: {len(characters_data)} chars, {len(scenes_data)} scenes")
                return characters_data, scenes_data

            except Exception as e:
                if attempt < MAX_STREAM_RETRIES - 1:
                    wait = 10 * (attempt + 1)
                    logger.warning(f"Streaming attempt {attempt + 1} failed, retrying in {wait}s: {e}")
                    time.sleep(wait)
                else:
                    raise

        # Should not reach here, but just in case
        raise RuntimeError("Streaming extraction failed after all retries")

    def _run_non_streaming_fallback(self, db: Session, rendered: dict,
                                     max_tokens: int) -> tuple[list[dict], list[dict]]:
        """加固6: Non-streaming fallback when streaming is unavailable.

        Uses ai_engine.call() + ProgressiveAssetParser for simulated progressive parse.
        """
        from services.ai_engine import ai_engine
        from services.streaming_parser import ProgressiveAssetParser, extract_json_robust

        logger.info("Running non-streaming fallback (加固6)")

        resp = ai_engine.call(
            system=rendered["system"],
            messages=[{"role": "user", "content": rendered["user"]}],
            capability_tier=rendered["capability_tier"],
            temperature=rendered["temperature"],
            max_tokens=max_tokens,
            operation_type="combined_extract_fallback",
        )
        raw = resp["content"]

        # Simulated progressive parse
        parser = ProgressiveAssetParser()
        char_count = 0
        scene_count = 0

        for ch in raw:
            result = parser.feed(ch)

            for char in result["characters"]:
                name = char.get("name", f"unknown_{char_count}")
                char_id = str(uuid4())
                character = Character(
                    id=char_id,
                    project_id=self.project_id,
                    name=name,
                    aliases=char.get("aliases", []),
                    role=char.get("role", "supporting"),
                    description=char.get("description", ""),
                    personality=char.get("personality", ""),
                    arc=char.get("arc", ""),
                    relationships=char.get("relationships", []),
                    age_range=char.get("age_range", ""),
                    appearance=char.get("appearance", {}),
                    costume=char.get("costume", {}),
                    casting_tags=char.get("casting_tags", []),
                    visual_reference=char.get("visual_reference", ""),
                    visual_prompt_negative=char.get("visual_prompt_negative", ""),
                    desire=char.get("desire", ""),
                    flaw=char.get("flaw", ""),
                )
                db.add(character)
                char["_db_id"] = char_id
                char_count += 1

                self._emit({
                    "type": "character_found",
                    "phase": "streaming",
                    "data": {"name": name, "role": char.get("role", ""), "index": char_count - 1},
                })

            for scene_obj in result["scenes"]:
                scene_id_str = f"scene_{scene_count + 1:03d}"
                scene_obj["scene_id"] = scene_id_str
                if "order" not in scene_obj:
                    scene_obj["order"] = scene_count

                db_scene_id = str(uuid4())
                scene = Scene(
                    id=db_scene_id,
                    project_id=self.project_id,
                    heading=scene_obj.get("heading", ""),
                    location=scene_obj.get("location", ""),
                    time_of_day=scene_obj.get("time_of_day", ""),
                    description=scene_obj.get("description", ""),
                    action=scene_obj.get("action", ""),
                    dialogue=scene_obj.get("dialogue", []),
                    order=scene_obj.get("order", scene_count),
                    tension_score=float(scene_obj.get("tension_score", 0.0)),
                    characters_present=scene_obj.get("characters_present", []),
                    key_props=scene_obj.get("key_props", []),
                    dramatic_purpose=scene_obj.get("dramatic_purpose", ""),
                    core_event=scene_obj.get("core_event", ""),
                    key_dialogue=scene_obj.get("key_dialogue", ""),
                    emotional_peak=scene_obj.get("emotional_peak", ""),
                    estimated_duration_s=scene_obj.get("estimated_duration_s"),
                )
                db.add(scene)
                scene_obj["_db_id"] = db_scene_id
                scene_count += 1

                self._emit({
                    "type": "scene_found",
                    "phase": "streaming",
                    "data": {
                        "scene_id": scene_id_str,
                        "location": scene_obj.get("location", ""),
                        "core_event": (scene_obj.get("core_event", ""))[:60],
                        "index": scene_count - 1,
                    },
                })

        characters_data = parser.found_chars
        scenes_data = parser.found_scenes

        # Fallback: full parse if parser didn't find things
        if not scenes_data:
            try:
                parsed = extract_json_robust(raw)
                if isinstance(parsed, dict):
                    if not characters_data:
                        characters_data = parsed.get("characters", [])
                        for i, char in enumerate(characters_data):
                            char_id = str(uuid4())
                            character = Character(
                                id=char_id,
                                project_id=self.project_id,
                                name=char.get("name", f"unknown_{i}"),
                                aliases=char.get("aliases", []),
                                role=char.get("role", "supporting"),
                                description=char.get("description", ""),
                                personality=char.get("personality", ""),
                                arc=char.get("arc", ""),
                                relationships=char.get("relationships", []),
                                age_range=char.get("age_range", ""),
                                appearance=char.get("appearance", {}),
                                costume=char.get("costume", {}),
                                casting_tags=char.get("casting_tags", []),
                                visual_reference=char.get("visual_reference", ""),
                                desire=char.get("desire", ""),
                                flaw=char.get("flaw", ""),
                            )
                            db.add(character)
                            char["_db_id"] = char_id
                        db.flush()

                    scenes_data = parsed.get("scenes", [])
                    for i, scene_obj in enumerate(scenes_data):
                        scene_id_str = f"scene_{i + 1:03d}"
                        scene_obj["scene_id"] = scene_id_str
                        if "order" not in scene_obj:
                            scene_obj["order"] = i
                        db_scene_id = str(uuid4())
                        scene = Scene(
                            id=db_scene_id,
                            project_id=self.project_id,
                            heading=scene_obj.get("heading", ""),
                            location=scene_obj.get("location", ""),
                            time_of_day=scene_obj.get("time_of_day", ""),
                            description=scene_obj.get("description", ""),
                            action=scene_obj.get("action", ""),
                            dialogue=scene_obj.get("dialogue", []),
                            order=scene_obj.get("order", i),
                            tension_score=float(scene_obj.get("tension_score", 0.0)),
                            characters_present=scene_obj.get("characters_present", []),
                            key_props=scene_obj.get("key_props", []),
                            dramatic_purpose=scene_obj.get("dramatic_purpose", ""),
                            core_event=scene_obj.get("core_event", ""),
                            key_dialogue=scene_obj.get("key_dialogue", ""),
                            emotional_peak=scene_obj.get("emotional_peak", ""),
                            estimated_duration_s=scene_obj.get("estimated_duration_s"),
                        )
                        db.add(scene)
                        scene_obj["_db_id"] = db_scene_id
                    db.flush()
            except Exception as e:
                logger.warning(f"Non-streaming full parse failed: {e}")

        # 加固5: scene fallback
        if len(scenes_data) == 0 and len(characters_data) > 0:
            scenes_data = self._run_scene_fallback(
                db, [c.get("name", "") for c in characters_data])

        db.commit()
        logger.info(f"Non-streaming fallback complete: {len(characters_data)} chars, {len(scenes_data)} scenes")
        return characters_data, scenes_data

    def _run_scene_fallback(self, db: Session, character_names: list[str]) -> list[dict]:
        """加固5: Standalone scene extraction when streaming got chars but 0 scenes.

        B2.1: Uses _scene_fallback_done flag to prevent double invocation.
        """
        if self._scene_fallback_done:
            logger.info("Scene fallback already executed — skipping duplicate call")
            return []
        self._scene_fallback_done = True

        from services.novel_parser import extract_scenes_standalone
        from services.ai_engine import ai_engine

        logger.info(f"Running scene fallback with {len(character_names)} known character names")
        self._emit({
            "type": "item_ready",
            "phase": "streaming",
            "sub": "scene_fallback",
            "data": {"reason": "scenes_missing", "char_count": len(character_names)},
        })

        scenes_data = extract_scenes_standalone(
            self.full_text, character_names, ai_engine_instance=ai_engine)

        # Write to DB
        for i, scene_obj in enumerate(scenes_data):
            scene_id_str = scene_obj.get("scene_id", f"scene_{i + 1:03d}")
            db_scene_id = str(uuid4())
            scene = Scene(
                id=db_scene_id,
                project_id=self.project_id,
                heading=scene_obj.get("heading", ""),
                location=scene_obj.get("location", ""),
                time_of_day=scene_obj.get("time_of_day", ""),
                description=scene_obj.get("description", ""),
                action=scene_obj.get("action", ""),
                dialogue=scene_obj.get("dialogue", []),
                order=scene_obj.get("order", i),
                tension_score=float(scene_obj.get("tension_score", 0.0)),
                characters_present=scene_obj.get("characters_present", []),
                key_props=scene_obj.get("key_props", []),
                dramatic_purpose=scene_obj.get("dramatic_purpose", ""),
                core_event=scene_obj.get("core_event", ""),
                key_dialogue=scene_obj.get("key_dialogue", ""),
                emotional_peak=scene_obj.get("emotional_peak", ""),
                estimated_duration_s=scene_obj.get("estimated_duration_s"),
            )
            db.add(scene)
            scene_obj["_db_id"] = db_scene_id

            self._emit({
                "type": "scene_found",
                "phase": "streaming",
                "data": {
                    "scene_id": scene_id_str,
                    "location": scene_obj.get("location", ""),
                    "core_event": (scene_obj.get("core_event", ""))[:60],
                    "index": i,
                    "source": "fallback",
                },
            })
        db.flush()

        logger.info(f"Scene fallback recovered {len(scenes_data)} scenes")
        return scenes_data

    # ─── Mode C Stage 2: Location cards ───────────────────────────

    def _run_location_cards(self, db: Session, scenes_data: list[dict]):
        """Stage 2A: Generate location visual asset cards."""
        from services.ai_engine import ai_engine
        from services.asset_enrichment import group_scenes_by_location, generate_location_cards

        groups = group_scenes_by_location(scenes_data)
        logger.info(f"Location grouping: {len(groups)} unique locations")

        if not groups:
            return

        cards = generate_location_cards(groups, self.full_text, ai_engine)

        for i, card in enumerate(cards):
            loc_name = card.get("name", f"unnamed_{i}")
            location = Location(
                id=str(uuid4()),
                project_id=self.project_id,
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

            self._emit({
                "type": "location_card",
                "phase": "locations",
                "data": {
                    "name": loc_name,
                    "scene_count": card.get("scene_count", 0),
                    "index": i,
                    "total": len(cards),
                },
            })

        db.flush()
        logger.info(f"Location cards written: {len(cards)}")

    # ─── Mode C Stage 2: Props collection + card generation ───────

    def _collect_and_save_props(self, db: Session, scenes_data: list[dict]):
        """Stage 2B+2C: Collect props, tier them, generate cards for major props."""
        from services.ai_engine import ai_engine
        from services.asset_enrichment import (
            collect_and_tier_props, generate_prop_cards, generate_minor_prop_visuals,
        )

        prop_data = collect_and_tier_props(scenes_data)
        logger.info(f"Props: {prop_data['total_unique']} unique "
                     f"(major: {prop_data['major_count']}, minor: {prop_data['minor_count']})")

        # Generate cards for major props
        major_cards = {}
        if prop_data["major"]:
            cards = generate_prop_cards(prop_data["major"], self.full_text, ai_engine)

            for i, card in enumerate(cards):
                prop_name = card.get("name", f"unnamed_{i}")
                major_info = prop_data["major"].get(prop_name, {})
                major_cards[prop_name] = card
                prop = Prop(
                    id=str(uuid4()),
                    project_id=self.project_id,
                    name=prop_name,
                    category=card.get("category", ""),
                    description=card.get("description", ""),
                    visual_reference=card.get("visual_reference", ""),
                    visual_prompt_negative=card.get("visual_prompt_negative", ""),
                    narrative_function=card.get("narrative_function", ""),
                    is_motif=card.get("is_motif", False),
                    is_major=True,
                    scenes_present=card.get("scenes_present", major_info.get("scenes", [])),
                    appearance_count=major_info.get("count", 0),
                    emotional_association=card.get("emotional_association", ""),
                )
                db.add(prop)

                self._emit({
                    "type": "prop_card",
                    "phase": "props",
                    "data": {
                        "name": prop_name,
                        "category": card.get("category", ""),
                        "is_motif": card.get("is_motif", False),
                        "index": i,
                        "total": len(cards),
                    },
                })

        # Generate visual prompts for minor props
        minor_visual_map = {}
        if prop_data.get("minor"):
            # Try to get era context from knowledge base
            era_context = ""
            try:
                kb = db.query(KnowledgeBase).filter(
                    KnowledgeBase.project_id == self.project_id
                ).first()
                if kb and kb.world_building:
                    era_context = kb.world_building.get("era", kb.world_building.get("setting", ""))
            except Exception:
                pass

            try:
                minor_visuals = generate_minor_prop_visuals(
                    prop_data["minor"], era_context, ai_engine)
                for mv in minor_visuals:
                    minor_visual_map[mv.get("name", "")] = mv
            except Exception as e:
                logger.warning(f"Minor prop visual generation failed (non-fatal): {e}")

        # Save minor props
        for prop_name, info in prop_data.get("minor", {}).items():
            mv = minor_visual_map.get(prop_name, {})
            prop = Prop(
                id=str(uuid4()),
                project_id=self.project_id,
                name=prop_name,
                is_major=False,
                visual_reference=mv.get("visual_reference", ""),
                visual_prompt_negative=mv.get("visual_prompt_negative", ""),
                scenes_present=info.get("scenes", []),
                appearance_count=info.get("count", 0),
            )
            db.add(prop)

        db.flush()

    # ─── Mode C Stage 3: Character variants ───────────────────────

    def _run_character_variants(self, db: Session,
                                 characters_data: list[dict],
                                 scenes_data: list[dict]):
        """Stage 3: Generate character variants for eligible characters."""
        from services.asset_enrichment import generate_character_variant
        from services.ai_engine import ai_engine

        # Filter eligible characters
        eligible_chars = []
        for char in characters_data:
            role = char.get("role", "")
            name = char.get("name", "")
            scene_count = sum(
                1 for s in scenes_data
                if name in s.get("characters_present", [])
            )
            if role in ("protagonist", "antagonist"):
                eligible_chars.append((char, scene_count))
            elif role == "supporting" and scene_count >= 5:
                eligible_chars.append((char, scene_count))

        if not eligible_chars:
            logger.info("No eligible characters for variant generation")
            return

        logger.info(f"Variant generation: {len(eligible_chars)} eligible characters")

        def _gen_variant_task(char_data, sc_count):
            """Thread task for single character variant generation."""
            name = char_data.get("name", "unnamed")
            char_scenes = [
                s for s in scenes_data
                if name in s.get("characters_present", [])
            ]
            return generate_character_variant(char_data, char_scenes, ai_engine)

        variant_count = 0
        with ThreadPoolExecutor(max_workers=MAX_VARIANT_CONCURRENCY) as executor:
            futures = {}
            for char_data, sc_count in eligible_chars:
                future = executor.submit(_gen_variant_task, char_data, sc_count)
                futures[future] = char_data

            for future in as_completed(futures):
                char_data = futures[future]
                char_name = char_data.get("name", "")
                char_db_id = char_data.get("_db_id")

                try:
                    variants = future.result()
                except Exception as e:
                    logger.warning(f"Variant generation failed for '{char_name}': {e}")
                    variants = []
                    # B2.5: emit SSE warning so user knows which character failed
                    self._emit({
                        "type": "warning",
                        "phase": "variants",
                        "data": {
                            "character": char_name,
                            "message": f"Variant generation failed: {str(e)[:100]}",
                        },
                    })

                for v in variants:
                    cv = CharacterVariant(
                        id=str(uuid4()),
                        project_id=self.project_id,
                        character_id=char_db_id,
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
                    db.add(cv)
                    variant_count += 1

                self._emit({
                    "type": "variant",
                    "phase": "variants",
                    "data": {
                        "character": char_name,
                        "variant_count": len(variants),
                    },
                })

        db.flush()
        logger.info(f"Character variants written: {variant_count}")

    # ─── Thread task: scene → shots + beats + merge ───────────────

    def _process_scene_task(self, scene_id: str, scene_json: dict,
                            char_profiles_json: str, style_guide_json: str):
        """Thread pool task: decompose scene to shots + generate beats + merge to groups."""
        from services.novel_parser import (
            decompose_scene_to_shots,
            generate_beats,
            merge_shots_to_groups,
        )

        thread_db = self.db_factory()
        try:
            # 1. Decompose scene to shots
            try:
                shot_data_list = self._call_with_retry(
                    decompose_scene_to_shots,
                    scene_json, char_profiles_json, style_guide_json, db=thread_db,
                )
            except Exception as e:
                logger.warning(f"Shot decomposition failed for '{scene_json.get('heading', '')}': {e}")
                shot_data_list = []

            for sd in shot_data_list:
                sd["_id"] = str(uuid4())

            # 2. Generate beats from scene text
            try:
                scene_text = f"{scene_json.get('heading', '')}\n{scene_json.get('action', '')}\n" + "\n".join(
                    f"{d.get('character', '')}: {d.get('line', '')}"
                    for d in (scene_json.get("dialogue") or [])
                )
                beat_data_list = self._call_with_retry(
                    generate_beats, scene_text, db=thread_db,
                )
            except Exception as e:
                logger.warning(f"Beat generation failed for '{scene_json.get('heading', '')}': {e}")
                beat_data_list = []

            # 3. Merge shots to groups
            group_data_list = []
            if shot_data_list:
                shots_json_for_merge = [
                    {
                        "shot_id": sd["_id"],
                        "shot_number": sd.get("shot_number", 0),
                        "goal": sd.get("goal", ""),
                        "composition": sd.get("composition", ""),
                        "camera_movement": sd.get("camera_movement", ""),
                        "framing": sd.get("framing", ""),
                        "duration_estimate": sd.get("duration_hint", sd.get("duration_estimate", "")),
                        "characters_in_frame": sd.get("characters", sd.get("characters_in_frame", [])),
                        "emotion_target": sd.get("emotion_target", ""),
                        "dramatic_intensity": sd.get("dramatic_intensity", 0.0),
                        "transition_in": sd.get("transition_in", ""),
                        "transition_out": sd.get("transition_out", ""),
                    }
                    for sd in shot_data_list
                ]
                try:
                    group_data_list = self._call_with_retry(
                        merge_shots_to_groups,
                        scene_json, shots_json_for_merge,
                        char_profiles_json, style_guide_json,
                        scene_id, db=thread_db,
                    )
                except Exception as e:
                    logger.warning(f"Shot merging failed for '{scene_json.get('heading', '')}': {e}")
                    group_data_list = []

            for gd in group_data_list:
                gd["_id"] = str(uuid4())

            return {
                "scene_id": scene_id,
                "shots": shot_data_list,
                "beats": beat_data_list,
                "groups": group_data_list,
            }
        except Exception as e:
            logger.error(f"Scene task failed for '{scene_json.get('heading', '')}': {e}", exc_info=True)
            return {
                "scene_id": scene_id,
                "shots": [],
                "beats": [],
                "groups": [],
            }
        finally:
            thread_db.close()

    # ─── Thread task: visual prompt generation ────────────────────

    def _generate_prompts_task(self, scene_id: str, shot_cards: list[dict],
                               char_profiles_json: str, style_guide_json: str):
        """Thread pool task: generate visual prompts for one scene's shot groups."""
        from services.novel_parser import generate_visual_prompts

        thread_db = self.db_factory()
        try:
            return self._call_with_retry(
                generate_visual_prompts,
                shot_cards, char_profiles_json, style_guide_json, db=thread_db,
            )
        except Exception as e:
            logger.warning(f"Visual prompt generation failed for scene {scene_id}: {e}")
            return []
        finally:
            thread_db.close()

    @classmethod
    def cancel_all(cls):
        """Cancel all active pipelines (called during graceful shutdown)."""
        with cls._active_lock:
            for pipeline in cls._active_pipelines:
                pipeline._cancelled = True
            logger.info(f"Cancelled {len(cls._active_pipelines)} active pipeline(s)")

    # ─── Main pipeline execution ──────────────────────────────────

    def run(self):
        """Execute the full pipeline. Called from the bounded thread pool."""
        from services.novel_parser import build_knowledge_base_v2

        # Register for graceful shutdown
        with self._active_lock:
            self._active_pipelines.append(self)

        db: Session = self.db_factory()
        try:
            task = db.query(ImportTask).filter(ImportTask.id == self.task_id).first()
            if not task:
                logger.error(f"ImportTask {self.task_id} not found")
                return
            task.status = "running"
            db.commit()

            # Determine resume point
            start_phase_idx = 0
            if task.current_phase in self.PHASES:
                start_phase_idx = self.PHASES.index(task.current_phase)

            characters_data = []
            scenes_data = []

            # ── Phase: streaming + enrichment — R29 dual-stream ─────────
            # In R29 mode, streaming and enrichment (locations, props, variants)
            # happen together via _run_dual_stream_extraction.
            if start_phase_idx <= 0:
                self._emit({"type": "phase_start", "phase": "streaming"})
                task.current_phase = "streaming"
                db.commit()

                try:
                    characters_data, scenes_data = self._run_dual_stream_extraction(db)
                except Exception as e:
                    logger.error(f"Streaming extraction failed: {e}", exc_info=True)
                    raise

                # B2.4: detect empty character list as serious issue
                if len(characters_data) == 0:
                    logger.error("CRITICAL: streaming extraction returned 0 characters")
                    self._emit({
                        "type": "warning",
                        "phase": "streaming",
                        "data": {"message": "No characters extracted from novel text"},
                    })

                task.progress = {
                    **(task.progress or {}),
                    "character_count": len(characters_data),
                    "scene_count": len(scenes_data),
                }
                db.commit()

                self._emit({
                    "type": "phase_done",
                    "phase": "streaming",
                    "data": {
                        "character_count": len(characters_data),
                        "scene_count": len(scenes_data),
                    },
                })

                # R29: enrichment phase (locations + props + variants) already
                # completed inside _run_dual_stream_extraction
                self._emit({"type": "phase_start", "phase": "enrichment"})
                task.current_phase = "enrichment"
                db.commit()
                self._emit({"type": "phase_done", "phase": "enrichment"})

            elif start_phase_idx <= 1:
                # Resume: load from DB
                char_records = (
                    db.query(Character)
                    .filter(Character.project_id == self.project_id)
                    .all()
                )
                characters_data = [
                    {
                        "name": c.name,
                        "aliases": c.aliases or [],
                        "role": c.role or "supporting",
                        "description": c.description or "",
                        "personality": c.personality or "",
                        "arc": c.arc or "",
                        "relationships": c.relationships or [],
                        "age_range": c.age_range or "",
                        "appearance": c.appearance or {},
                        "costume": c.costume or {},
                        "casting_tags": c.casting_tags or [],
                        "visual_reference": c.visual_reference or "",
                        "visual_prompt_negative": c.visual_prompt_negative or "",
                        "desire": c.desire or "",
                        "flaw": c.flaw or "",
                        "_db_id": c.id,
                    }
                    for c in char_records
                ]
                scene_records = (
                    db.query(Scene)
                    .filter(Scene.project_id == self.project_id)
                    .order_by(Scene.order)
                    .all()
                )
                scenes_data = [
                    {
                        "scene_id": f"scene_{i + 1:03d}",
                        "heading": s.heading or "",
                        "location": s.location or "",
                        "time_of_day": s.time_of_day or "",
                        "description": s.description or "",
                        "action": s.action or "",
                        "dialogue": s.dialogue or [],
                        "order": s.order,
                        "tension_score": s.tension_score or 0.0,
                        "characters_present": s.characters_present or [],
                        "key_props": s.key_props or [],
                        "dramatic_purpose": s.dramatic_purpose or "",
                        "core_event": s.core_event or "",
                        "key_dialogue": s.key_dialogue or "",
                        "emotional_peak": s.emotional_peak or "",
                        "estimated_duration_s": s.estimated_duration_s,
                        "_db_id": s.id,
                    }
                    for i, s in enumerate(scene_records)
                ]

            if self._cancelled:
                return

            # ── Phase: enrichment (resume only) ──────────────────────
            # When resuming from enrichment phase, run locations/props/variants
            # sequentially as fallback (dual-stream not available for resume)
            if start_phase_idx == 1:
                self._emit({"type": "phase_start", "phase": "enrichment"})
                task.current_phase = "enrichment"
                db.commit()

                try:
                    self._run_location_cards(db, scenes_data)
                except Exception as e:
                    logger.warning(f"Location cards failed (non-fatal): {e}")

                try:
                    self._collect_and_save_props(db, scenes_data)
                except Exception as e:
                    logger.warning(f"Props failed (non-fatal): {e}")

                try:
                    self._run_character_variants(db, characters_data, scenes_data)
                except Exception as e:
                    logger.warning(f"Variants failed (non-fatal): {e}")

                db.commit()
                self._emit({"type": "phase_done", "phase": "enrichment"})

            if self._cancelled:
                return

            # ── Phase: knowledge — Knowledge base (reuse existing) ────
            if start_phase_idx <= 2:
                self._emit({"type": "phase_start", "phase": "knowledge"})
                task.current_phase = "knowledge"
                db.commit()

                # Build synopsis from scenes
                scene_records_db = (
                    db.query(Scene)
                    .filter(Scene.project_id == self.project_id)
                    .order_by(Scene.order)
                    .all()
                )
                synopsis = "\n\n".join(
                    f"【{s.heading}】{(s.action or '')[:300]}"
                    for s in scene_records_db if s.heading
                )

                char_names = [c.get("name", "") for c in characters_data]
                loc_names = [
                    loc.name for loc in
                    db.query(Location).filter(Location.project_id == self.project_id).all()
                ]

                try:
                    kb_data = self._call_with_retry(
                        build_knowledge_base_v2,
                        synopsis, char_names, loc_names, db=db,
                    )
                except Exception as e:
                    logger.warning(f"Knowledge base build failed: {e}")
                    kb_data = {"world_building": {}, "style_guide": {}}

                existing_kb = (
                    db.query(KnowledgeBase)
                    .filter(KnowledgeBase.project_id == self.project_id)
                    .first()
                )
                if existing_kb:
                    existing_kb.world_building = kb_data.get("world_building", {})
                    existing_kb.style_guide = kb_data.get("style_guide", {})
                else:
                    kb = KnowledgeBase(
                        id=str(uuid4()),
                        project_id=self.project_id,
                        world_building=kb_data.get("world_building", {}),
                        style_guide=kb_data.get("style_guide", {}),
                    )
                    db.add(kb)

                task.synopsis = synopsis
                task.progress = {
                    **(task.progress or {}),
                    "knowledge_base": True,
                }
                db.commit()

                self._emit({"type": "phase_done", "phase": "knowledge"})

            if self._cancelled:
                return

            # Build character profiles list and style guide for later phases
            character_records = (
                db.query(Character)
                .filter(Character.project_id == self.project_id)
                .all()
            )
            char_profiles = [
                {
                    "name": c.name,
                    "role": c.role,
                    "appearance": c.appearance or {},
                    "costume": c.costume or {},
                    "visual_reference": c.visual_reference or "",
                }
                for c in character_records
            ]

            kb_record = (
                db.query(KnowledgeBase)
                .filter(KnowledgeBase.project_id == self.project_id)
                .first()
            )
            style_guide_json = json.dumps(
                kb_record.style_guide if kb_record else {},
                ensure_ascii=False,
            )

            scene_records_for_shots = (
                db.query(Scene)
                .filter(Scene.project_id == self.project_id)
                .order_by(Scene.order)
                .all()
            )

            # ── Phase: shots+merge (PARALLEL across scenes) — UNCHANGED ──
            if start_phase_idx <= 3:
                self._emit({
                    "type": "phase_start", "phase": "shots",
                    "total": len(scene_records_for_shots),
                })
                task.current_phase = "shots"
                db.commit()

                scene_results: dict[str, dict] = {}
                completed_scenes = 0

                with ThreadPoolExecutor(max_workers=MAX_SCENE_CONCURRENCY) as executor:
                    futures = {}
                    for scene in scene_records_for_shots:
                        scene_json = {
                            "heading": scene.heading,
                            "location": scene.location,
                            "time_of_day": scene.time_of_day,
                            "description": scene.description,
                            "action": scene.action,
                            "dialogue": scene.dialogue or [],
                            "characters_present": scene.characters_present or [],
                            "key_props": scene.key_props or [],
                            "dramatic_purpose": scene.dramatic_purpose or "",
                            "tension_score": scene.tension_score,
                        }

                        filtered_chars_json = self._filter_char_profiles(
                            char_profiles,
                            scene.characters_present or [],
                        )

                        future = executor.submit(
                            self._process_scene_task,
                            scene.id, scene_json, filtered_chars_json, style_guide_json,
                        )
                        futures[future] = scene

                    for future in as_completed(futures):
                        if self._cancelled:
                            executor.shutdown(wait=False, cancel_futures=True)
                            return

                        scene = futures[future]
                        # B2.2: wrap future.result() in try-except
                        try:
                            result = future.result()
                        except Exception as e:
                            logger.error(f"Scene task failed for '{scene.heading}': {e}", exc_info=True)
                            result = {"scene_id": scene.id, "shots": [], "beats": [], "groups": []}
                        scene_results[scene.id] = result
                        completed_scenes += 1

                        self._emit({
                            "type": "scene_progress",
                            "phase": "shots",
                            "index": completed_scenes - 1,
                            "total": len(scene_records_for_shots),
                            "shots": len(result.get("shots", [])),
                        })

                # Write all results to DB
                total_shot_order = 0
                total_beat_order = 0
                total_group_order = 0
                shot_count = 0
                beat_count = 0
                group_count = 0

                for scene in scene_records_for_shots:
                    result = scene_results.get(scene.id, {})

                    for shot_data in result.get("shots", []):
                        shot = Shot(
                            id=shot_data["_id"],
                            project_id=self.project_id,
                            scene_id=scene.id,
                            shot_number=shot_data.get("shot_number", 0),
                            goal=shot_data.get("goal", ""),
                            composition=shot_data.get("composition", ""),
                            camera_angle=shot_data.get("camera_angle", ""),
                            camera_movement=shot_data.get("camera_movement", ""),
                            framing=shot_data.get("framing", ""),
                            duration_estimate=shot_data.get("duration_hint", shot_data.get("duration_estimate", "")),
                            characters_in_frame=shot_data.get("characters", shot_data.get("characters_in_frame", [])),
                            emotion_target=shot_data.get("emotion_target", ""),
                            dramatic_intensity=_safe_float(shot_data.get("dramatic_intensity", 0.0)),
                            transition_in=shot_data.get("transition_in", ""),
                            transition_out=shot_data.get("transition_out", ""),
                            description=shot_data.get("description", ""),
                            order=total_shot_order,
                        )
                        db.add(shot)
                        total_shot_order += 1
                        shot_count += 1

                    for beat_data in result.get("beats", []):
                        beat = Beat(
                            id=str(uuid4()),
                            project_id=self.project_id,
                            title=beat_data.get("title", ""),
                            description=beat_data.get("description", ""),
                            beat_type=beat_data.get("beat_type", "event"),
                            emotional_value=_safe_float(beat_data.get("emotional_value", 0.0)),
                            order=total_beat_order,
                        )
                        db.add(beat)
                        total_beat_order += 1
                        beat_count += 1

                    for g_data in result.get("groups", []):
                        group = ShotGroup(
                            id=g_data["_id"],
                            project_id=self.project_id,
                            scene_id=scene.id,
                            shot_ids=g_data.get("shot_ids", []),
                            segment_number=g_data.get("segment_number", 0),
                            duration=g_data.get("target_duration", g_data.get("duration", "")),
                            transition_type=g_data.get("transition_type", ""),
                            emotional_beat=g_data.get("emotional_beat", ""),
                            continuity=g_data.get("continuity", ""),
                            vff_body=g_data.get("vff_body", ""),
                            merge_rationale=g_data.get("merge_rationale", ""),
                            style_metadata=g_data.get("style_metadata", {}),
                            order=total_group_order,
                        )
                        db.add(group)
                        total_group_order += 1
                        group_count += 1

                task.progress = {
                    **(task.progress or {}),
                    "shot_count": shot_count,
                    "beat_count": beat_count,
                    "shot_group_count": group_count,
                }
                db.commit()

                self._emit({
                    "type": "phase_done",
                    "phase": "shots",
                    "data": {"shot_count": shot_count, "beat_count": beat_count},
                })
                self._emit({
                    "type": "phase_start", "phase": "merging",
                    "total": len(scene_records_for_shots),
                })
                self._emit({
                    "type": "phase_done",
                    "phase": "merging",
                    "data": {"shot_group_count": group_count},
                })

            elif start_phase_idx == 4:
                # Resume from merging only
                self._run_merge_only(db, task, scene_records_for_shots, char_profiles, style_guide_json)

            if self._cancelled:
                return

            # ── Phase: prompts — Visual Prompt Generation (PARALLEL) — UNCHANGED ──
            if start_phase_idx <= 5:
                self._emit({
                    "type": "phase_start", "phase": "prompts",
                    "total": len(scene_records_for_shots),
                })
                task.current_phase = "prompts"
                db.commit()

                scene_group_map: dict[str, list] = {}
                all_groups = (
                    db.query(ShotGroup)
                    .filter(ShotGroup.project_id == self.project_id)
                    .order_by(ShotGroup.order)
                    .all()
                )
                for g in all_groups:
                    scene_group_map.setdefault(g.scene_id, []).append(g)

                prompt_count = 0
                completed_prompt_scenes = 0

                with ThreadPoolExecutor(max_workers=MAX_PROMPT_CONCURRENCY) as executor:
                    futures = {}
                    for scene in scene_records_for_shots:
                        groups = scene_group_map.get(scene.id, [])
                        if not groups:
                            continue

                        shot_cards = [
                            {
                                "shot_group_id": g.id,
                                "segment_number": g.segment_number,
                                "shot_ids": g.shot_ids,
                                "vff_body": g.vff_body,
                                "duration": g.duration,
                                "continuity": g.continuity,
                                "emotional_beat": g.emotional_beat,
                                "style_metadata": g.style_metadata or {},
                            }
                            for g in groups
                        ]

                        filtered_chars_json = self._filter_char_profiles(
                            char_profiles,
                            scene.characters_present or [],
                        )

                        future = executor.submit(
                            self._generate_prompts_task,
                            scene.id, shot_cards, filtered_chars_json, style_guide_json,
                        )
                        futures[future] = (scene, groups)

                    for future in as_completed(futures):
                        if self._cancelled:
                            executor.shutdown(wait=False, cancel_futures=True)
                            return

                        scene, groups = futures[future]
                        # B2.2: wrap future.result() in try-except
                        try:
                            prompt_results = future.result()
                        except Exception as e:
                            logger.warning(f"Visual prompt generation failed for scene {scene.id}: {e}")
                            prompt_results = []
                        completed_prompt_scenes += 1

                        for p_data in prompt_results:
                            shot_group_id = p_data.get("shot_group_id", p_data.get("shot_id", ""))
                            for g in groups:
                                if g.id == shot_group_id or str(g.segment_number) == str(p_data.get("segment_number", "")):
                                    g.visual_prompt_positive = p_data.get("prompt_text", p_data.get("visual_prompt_positive", ""))
                                    g.visual_prompt_negative = p_data.get("negative_prompt", p_data.get("visual_prompt_negative", ""))
                                    g.style_tags = p_data.get("style_tags", [])
                                    if p_data.get("style_params"):
                                        g.style_metadata = {**(g.style_metadata or {}), **p_data["style_params"]}
                                    prompt_count += 1
                                    break

                        db.flush()

                        self._emit({
                            "type": "scene_progress",
                            "phase": "prompts",
                            "index": completed_prompt_scenes - 1,
                            "total": len(scene_records_for_shots),
                        })

                task.progress = {
                    **(task.progress or {}),
                    "prompt_count": prompt_count,
                }
                db.commit()

                self._emit({
                    "type": "phase_done",
                    "phase": "prompts",
                    "data": {"prompt_count": prompt_count},
                })

            # ── Complete ─────────────────────────────────────────────
            from models.project import Project
            project = db.query(Project).filter(Project.id == self.project_id).first()
            if project:
                project.stage = "storyboard"

            task.status = "completed"
            task.current_phase = "prompts"
            db.commit()

            summary = task.progress or {}
            self._emit({
                "type": "pipeline_complete",
                "summary": summary,
            })

        except Exception as e:
            logger.error(f"Pipeline failed for task {self.task_id}: {e}", exc_info=True)
            try:
                task = db.query(ImportTask).filter(ImportTask.id == self.task_id).first()
                if task:
                    task.status = "failed"
                    task.error = str(e)
                    # Save checkpoint for potential resume
                    task.stream_checkpoint = {"failed_phase": task.current_phase}
                    db.commit()
            except Exception:
                pass
            self._emit({
                "type": "error",
                "message": str(e),
                "phase": task.current_phase if task else "unknown",
                "retryable": True,
            })
        finally:
            db.close()
            # Deregister from active pipelines
            with self._active_lock:
                if self in self._active_pipelines:
                    self._active_pipelines.remove(self)

    def _run_merge_only(self, db: Session, task, scene_records, char_profiles, style_guide_json):
        """Phase merging standalone: merge existing shots into groups (for resume)."""
        from services.novel_parser import merge_shots_to_groups

        self._emit({
            "type": "phase_start", "phase": "merging",
            "total": len(scene_records),
        })
        task.current_phase = "merging"
        db.commit()

        group_count = 0
        total_group_order = 0

        for s_idx, scene in enumerate(scene_records):
            scene_shots = (
                db.query(Shot)
                .filter(Shot.scene_id == scene.id)
                .order_by(Shot.order)
                .all()
            )
            if not scene_shots:
                continue

            scene_json = {
                "heading": scene.heading,
                "location": scene.location,
                "time_of_day": scene.time_of_day,
                "description": scene.description,
                "action": scene.action,
                "dialogue": scene.dialogue or [],
                "characters_present": scene.characters_present or [],
                "tension_score": scene.tension_score,
            }
            shots_json = [
                {
                    "shot_id": s.id,
                    "shot_number": s.shot_number,
                    "goal": s.goal,
                    "composition": s.composition,
                    "camera_movement": s.camera_movement,
                    "framing": s.framing,
                    "duration_estimate": s.duration_estimate,
                    "characters_in_frame": s.characters_in_frame or [],
                    "emotion_target": s.emotion_target,
                    "dramatic_intensity": s.dramatic_intensity,
                    "transition_in": s.transition_in,
                    "transition_out": s.transition_out,
                }
                for s in scene_shots
            ]

            filtered_chars_json = self._filter_char_profiles(
                char_profiles, scene.characters_present or [],
            )

            try:
                group_data_list = self._call_with_retry(
                    merge_shots_to_groups,
                    scene_json, shots_json,
                    filtered_chars_json, style_guide_json,
                    scene.id, db=db,
                )
            except Exception as e:
                logger.warning(f"Shot merging failed for scene '{scene.heading}': {e}")
                group_data_list = []

            for g_data in group_data_list:
                group = ShotGroup(
                    id=str(uuid4()),
                    project_id=self.project_id,
                    scene_id=scene.id,
                    shot_ids=g_data.get("shot_ids", []),
                    segment_number=g_data.get("segment_number", 0),
                    duration=g_data.get("target_duration", g_data.get("duration", "")),
                    transition_type=g_data.get("transition_type", ""),
                    emotional_beat=g_data.get("emotional_beat", ""),
                    continuity=g_data.get("continuity", ""),
                    vff_body=g_data.get("vff_body", ""),
                    merge_rationale=g_data.get("merge_rationale", ""),
                    style_metadata=g_data.get("style_metadata", {}),
                    order=total_group_order,
                )
                db.add(group)
                total_group_order += 1
                group_count += 1

            db.flush()

            self._emit({
                "type": "scene_progress",
                "phase": "merging",
                "index": s_idx,
                "total": len(scene_records),
            })

        task.progress = {
            **(task.progress or {}),
            "shot_group_count": group_count,
        }
        db.commit()

        self._emit({
            "type": "phase_done",
            "phase": "merging",
            "data": {"shot_group_count": group_count},
        })

    def cancel(self):
        """Signal the pipeline to stop at the next phase boundary."""
        self._cancelled = True
