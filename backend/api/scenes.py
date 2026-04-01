"""Scenes CRUD API."""

import json
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.scene import Scene
from models.character import Character
from models.import_task import ImportTask
from services.prompt_templates import render_prompt
from services.ai_engine import AIEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scenes"])

ai_engine = AIEngine()


# --- Schemas ---

class SceneCreate(BaseModel):
    beat_id: Optional[str] = None
    heading: str = ""
    location: str = ""
    time_of_day: str = ""
    description: str = ""
    action: str = ""
    dialogue: list = []
    order: int = 0
    tension_score: float = 0.0


class SceneUpdate(BaseModel):
    beat_id: Optional[str] = None
    heading: Optional[str] = None
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    description: Optional[str] = None
    action: Optional[str] = None
    dialogue: Optional[list] = None
    order: Optional[int] = None
    tension_score: Optional[float] = None
    edited_source_text: Optional[str] = None
    characters_present: Optional[list] = None
    core_event: Optional[str] = None
    dramatic_purpose: Optional[str] = None
    hook_type: Optional[str] = None
    cliffhanger: Optional[str] = None
    emotion_beat: Optional[str] = None
    narrative_mode: Optional[str] = None
    dialogue_budget: Optional[str] = None


class SceneResponse(BaseModel):
    id: str
    project_id: str
    beat_id: Optional[str]
    heading: str
    location: str
    time_of_day: str
    description: str
    action: str
    dialogue: list
    order: int
    tension_score: float
    characters_present: list = []
    key_props: list = []
    dramatic_purpose: str = ""
    window_index: Optional[int] = None
    core_event: str = ""
    key_dialogue: str = ""
    emotional_peak: str = ""
    estimated_duration_s: Optional[int] = None
    visual_reference: str = ""
    visual_prompt_negative: str = ""
    source_text_start: str = ""
    source_text_end: str = ""
    generated_script: Optional[str] = None
    edited_source_text: Optional[str] = None
    # 短剧增强字段
    narrative_mode: str = "mixed"
    hook_type: str = ""
    cliffhanger: str = ""
    reversal_points: list = []
    sweet_spot: str = ""
    emotion_beat: str = ""
    dialogue_budget: str = "medium"
    generated_script_json: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Routes ---

@router.get("/projects/{project_id}/scenes", response_model=list[SceneResponse])
def list_scenes(project_id: str, db: Session = Depends(get_db)):
    """List all scenes for a project."""
    return db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.order).all()


@router.post("/projects/{project_id}/scenes", response_model=SceneResponse, status_code=201)
def create_scene(project_id: str, data: SceneCreate, db: Session = Depends(get_db)):
    """Create a new scene."""
    scene = Scene(
        id=str(uuid4()),
        project_id=project_id,
        beat_id=data.beat_id,
        heading=data.heading,
        location=data.location,
        time_of_day=data.time_of_day,
        description=data.description,
        action=data.action,
        dialogue=data.dialogue,
        order=data.order,
        tension_score=data.tension_score,
    )
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return scene


# --- Batch Script Generation (must be before {scene_id} routes) ---

class GenerateAllScriptsRequest(BaseModel):
    user_direction: Optional[str] = None     # 全局导演指令
    skip_completed: bool = True              # 跳过已有剧本的场景


# 模块级批量取消标志
_batch_cancel_flags: dict[str, bool] = {}


@router.post("/projects/{project_id}/scenes/generate-all-scripts")
def generate_all_scripts(
    project_id: str,
    data: GenerateAllScriptsRequest,
    db: Session = Depends(get_db),
):
    """Batch generate scripts for all scenes in order via SSE streaming.

    Scenes are processed sequentially so each scene can use the previous
    scene's generated script as cross-scene context.
    """
    # 1. Load all scenes ordered
    all_scenes = (
        db.query(Scene)
        .filter(Scene.project_id == project_id)
        .order_by(Scene.order)
        .all()
    )
    if not all_scenes:
        raise HTTPException(status_code=404, detail="No scenes found for project")

    # 2. Load novel full text
    import_task = (
        db.query(ImportTask)
        .filter(ImportTask.project_id == project_id)
        .order_by(ImportTask.created_at.desc())
        .first()
    )
    full_text = import_task.full_text if import_task else ""

    # 3. Build director baseline
    director_baseline_str = "（无导演基准）"
    if import_task and import_task.novel_analysis_json:
        analysis = import_task.novel_analysis_json
        structured = analysis.get("structured", analysis)
        # Apply story bible overrides
        overrides = import_task.story_bible_overrides or {}
        for key, value in overrides.items():
            structured[key] = value
        baseline = {
            "genre_type": structured.get("genre_type", ""),
            "era": structured.get("era", ""),
            "themes": structured.get("themes", []),
            "pacing_type": structured.get("pacing_type", ""),
        }
        vb = structured.get("visual_baseline", {})
        if vb:
            baseline["art_style"] = vb.get("art_style", "")
            baseline["color_system"] = vb.get("color_system", "")
            baseline["lighting_baseline"] = vb.get("lighting_baseline", "")
        sdp = structured.get("short_drama_params", {})
        if sdp:
            baseline["short_drama_params"] = sdp
        director_baseline_str = json.dumps(baseline, ensure_ascii=False, indent=2)

    batch_id = str(uuid4())
    _batch_cancel_flags[batch_id] = False
    user_direction = data.user_direction.strip() if data.user_direction else "无特别要求"

    def batch_event_stream():
        total = len(all_scenes)
        completed = 0
        failed = 0
        skipped = 0
        # 内存中缓存刚生成的 script_json，供下一场景使用
        prev_script_json_cache: Optional[dict] = None

        yield f"data: {json.dumps({'type': 'batch_start', 'total': total, 'batch_id': batch_id}, ensure_ascii=False)}\n\n"

        try:
            for idx, scene in enumerate(all_scenes):
                # 检查取消标志
                if _batch_cancel_flags.get(batch_id, False):
                    yield f"data: {json.dumps({'type': 'batch_complete', 'completed': completed, 'failed': failed, 'skipped': skipped, 'cancelled': True}, ensure_ascii=False)}\n\n"
                    return

                prev_scene = all_scenes[idx - 1] if idx > 0 else None
                next_scene = all_scenes[idx + 1] if idx < len(all_scenes) - 1 else None

                # skip_completed 检查
                if data.skip_completed and scene.generated_script_json:
                    skipped += 1
                    # 缓存已有剧本供下一场景使用
                    prev_script_json_cache = scene.generated_script_json
                    yield f"data: {json.dumps({'type': 'scene_skipped', 'scene_id': scene.id, 'index': idx, 'heading': scene.heading or ''}, ensure_ascii=False)}\n\n"
                    continue

                yield f"data: {json.dumps({'type': 'scene_start', 'scene_id': scene.id, 'index': idx, 'heading': scene.heading or ''}, ensure_ascii=False)}\n\n"

                try:
                    # Build source texts
                    source_text = _get_scene_source_text(scene, full_text) if full_text else "（无原文）"
                    prev_source_text = (
                        _get_scene_source_text(prev_scene, full_text)
                        if prev_scene and full_text
                        else "【开场镜头 — 无前序场景】"
                    )
                    next_source_text = (
                        _get_scene_source_text(next_scene, full_text)
                        if next_scene and full_text
                        else "【尾声 — 无后续场景】"
                    )

                    # Build character profiles
                    character_profiles_str = "（无角色档案）"
                    if scene.characters_present:
                        chars = (
                            db.query(Character)
                            .filter(
                                Character.project_id == project_id,
                                Character.name.in_(scene.characters_present),
                            )
                            .all()
                        )
                        if chars:
                            profiles = []
                            for c in chars:
                                profiles.append({
                                    "name": c.name,
                                    "role": c.role or "",
                                    "personality": c.personality or "",
                                    "appearance": c.appearance or {},
                                    "costume": c.costume or {},
                                    "desire": c.desire or "",
                                    "flaw": c.flaw or "",
                                    "relationships": c.relationships or [],
                                })
                            character_profiles_str = json.dumps(profiles, ensure_ascii=False, indent=2)

                    # Build scene_json
                    scene_json_data = {
                        "heading": scene.heading or "",
                        "location": scene.location or "",
                        "time_of_day": scene.time_of_day or "",
                        "description": scene.description or "",
                        "action": scene.action or "",
                        "dialogue": scene.dialogue or [],
                        "characters_present": scene.characters_present or [],
                        "key_props": scene.key_props or [],
                        "dramatic_purpose": scene.dramatic_purpose or "",
                        "core_event": scene.core_event or "",
                        "key_dialogue": scene.key_dialogue or "",
                        "emotional_peak": scene.emotional_peak or "",
                        "tension_score": scene.tension_score or 0,
                        "estimated_duration_s": scene.estimated_duration_s,
                        "visual_reference": scene.visual_reference or "",
                        "visual_prompt_negative": scene.visual_prompt_negative or "",
                        "narrative_mode": scene.narrative_mode or "mixed",
                        "hook_type": scene.hook_type or "",
                        "cliffhanger": scene.cliffhanger or "",
                        "reversal_points": scene.reversal_points or [],
                        "sweet_spot": scene.sweet_spot or "",
                        "emotion_beat": scene.emotion_beat or "",
                        "dialogue_budget": scene.dialogue_budget or "medium",
                    }
                    scene_json_str = json.dumps(scene_json_data, ensure_ascii=False, indent=2)

                    # Build cross-scene context (batch mode: use cached prev script)
                    prev_script_context, next_scene_context = _build_cross_scene_context(
                        prev_scene, next_scene,
                        prev_script_json_override=prev_script_json_cache,
                    )

                    # Render prompt
                    prompt = render_prompt(
                        "P_SCRIPT_GENERATE",
                        scene_json=scene_json_str,
                        source_text=source_text,
                        prev_source_text=prev_source_text,
                        next_source_text=next_source_text,
                        prev_script_context=prev_script_context,
                        next_scene_context=next_scene_context,
                        character_profiles=character_profiles_str,
                        director_baseline=director_baseline_str,
                        user_direction=user_direction,
                    )

                    # Stream generation
                    full_text_parts: list[str] = []
                    for chunk in ai_engine.stream(
                        system=prompt["system"],
                        messages=[{"role": "user", "content": prompt["user"]}],
                        capability_tier=prompt["capability_tier"],
                        temperature=prompt["temperature"],
                        max_tokens=prompt["max_tokens"],
                        db=db,
                    ):
                        full_text_parts.append(chunk)
                        yield f"data: {json.dumps({'type': 'text', 'scene_id': scene.id, 'content': chunk}, ensure_ascii=False)}\n\n"

                    # Parse and save
                    final_script = "".join(full_text_parts)
                    script_json = None
                    try:
                        clean_text = final_script.strip()
                        if clean_text.startswith("```"):
                            first_newline = clean_text.index("\n")
                            clean_text = clean_text[first_newline + 1:]
                        if clean_text.endswith("```"):
                            clean_text = clean_text[:-3].strip()
                        script_json = json.loads(clean_text)
                    except (json.JSONDecodeError, ValueError):
                        logger.warning(f"Batch: Script not valid JSON for scene {scene.id}")

                    if script_json:
                        scene.generated_script_json = script_json
                        summary_parts = []
                        for beat in script_json.get("beats", []):
                            summary_parts.append(f"[{beat.get('timestamp', '')}] {beat.get('type', '')}")
                            for shot in beat.get("shots", []):
                                if shot.get("action"):
                                    summary_parts.append(f"  {shot['action']}")
                                dlg = shot.get("dialogue")
                                if dlg and isinstance(dlg, dict) and dlg.get("line"):
                                    summary_parts.append(f"  {dlg.get('character', '???')}: {dlg['line']}")
                        scene.generated_script = "\n".join(summary_parts) if summary_parts else final_script
                    else:
                        scene.generated_script = final_script
                    db.commit()

                    # 缓存当前场景的 script_json 供下一场景使用
                    prev_script_json_cache = script_json

                    completed += 1
                    yield f"data: {json.dumps({'type': 'scene_complete', 'scene_id': scene.id, 'index': idx, 'has_json': script_json is not None}, ensure_ascii=False)}\n\n"

                except Exception as e:
                    logger.error(f"Batch script generation error for scene {scene.id}: {e}")
                    failed += 1
                    prev_script_json_cache = None  # 失败时清除缓存
                    yield f"data: {json.dumps({'type': 'scene_error', 'scene_id': scene.id, 'index': idx, 'message': str(e)}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'batch_complete', 'completed': completed, 'failed': failed, 'skipped': skipped, 'cancelled': False}, ensure_ascii=False)}\n\n"

        finally:
            _batch_cancel_flags.pop(batch_id, None)

    return StreamingResponse(
        batch_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/projects/{project_id}/scenes/cancel-batch/{batch_id}")
def cancel_batch(project_id: str, batch_id: str):
    """Cancel an in-progress batch script generation."""
    if batch_id not in _batch_cancel_flags:
        raise HTTPException(status_code=404, detail="Batch not found or already completed")
    _batch_cancel_flags[batch_id] = True
    return {"status": "cancelling", "batch_id": batch_id}


@router.get("/projects/{project_id}/scenes/{scene_id}", response_model=SceneResponse)
def get_scene(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    """Get a single scene."""
    scene = db.query(Scene).filter(Scene.id == scene_id, Scene.project_id == project_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    return scene


@router.put("/projects/{project_id}/scenes/{scene_id}", response_model=SceneResponse)
def update_scene(project_id: str, scene_id: str, data: SceneUpdate, db: Session = Depends(get_db)):
    """Update a scene."""
    scene = db.query(Scene).filter(Scene.id == scene_id, Scene.project_id == project_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    for field in ["beat_id", "heading", "location", "time_of_day", "description", "action", "dialogue", "order", "tension_score",
                   "edited_source_text", "characters_present", "core_event", "dramatic_purpose",
                   "hook_type", "cliffhanger", "emotion_beat", "narrative_mode", "dialogue_budget"]:
        value = getattr(data, field)
        if value is not None:
            setattr(scene, field, value)

    db.commit()
    db.refresh(scene)
    return scene


@router.delete("/projects/{project_id}/scenes/{scene_id}", status_code=204)
def delete_scene(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    """Delete a scene."""
    scene = db.query(Scene).filter(Scene.id == scene_id, Scene.project_id == project_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    db.delete(scene)
    db.commit()
    return None


# --- Script Generation ---

class GenerateScriptRequest(BaseModel):
    user_direction: Optional[str] = None


def _get_scene_source_text(scene: Scene, full_text: str) -> str:
    """Extract source text for a scene from the novel full text.
    Prioritizes user-edited source text if available.
    """
    if scene.edited_source_text:
        return scene.edited_source_text
    if not full_text or not scene.source_text_start or not scene.source_text_end:
        return "（无原文片段）"
    start_idx = full_text.find(scene.source_text_start)
    if start_idx == -1:
        return "（无法定位原文片段）"
    end_idx = full_text.find(scene.source_text_end, start_idx)
    if end_idx == -1:
        return full_text[start_idx:start_idx + 2000]
    return full_text[start_idx:end_idx + len(scene.source_text_end)]


def _build_cross_scene_context(prev_scene, next_scene, prev_script_json_override=None):
    """构建跨场景上下文，用于剧本生成时的情绪/视觉/对白衔接。

    返回 (prev_script_context_str, next_scene_context_str)
    """
    # ── prev_script_context ──
    prev_script_json = prev_script_json_override
    if prev_script_json is None and prev_scene is not None:
        prev_script_json = getattr(prev_scene, "generated_script_json", None)

    if prev_scene is None:
        prev_script_context = "【开场 — 无前序场景】"
    elif prev_script_json and isinstance(prev_script_json, dict):
        # 有已生成剧本 JSON：提取 scene_summary + 最后 2 个 beats
        parts = []
        summary = prev_script_json.get("scene_summary")
        if summary:
            parts.append(f"scene_summary: {json.dumps(summary, ensure_ascii=False)}")
        beats = prev_script_json.get("beats", [])
        tail_beats = beats[-2:] if len(beats) >= 2 else beats
        for b in tail_beats:
            beat_info = {
                "beat_id": b.get("beat_id", ""),
                "type": b.get("type", ""),
                "timestamp": b.get("timestamp", ""),
            }
            # 提取最后一个 shot 的关键信息
            shots = b.get("shots", [])
            if shots:
                last_shot = shots[-1]
                beat_info["last_shot_action"] = last_shot.get("action", "")
                beat_info["last_shot_music"] = last_shot.get("music", "")
                beat_info["last_shot_sfx"] = last_shot.get("sfx", "")
                dlg = last_shot.get("dialogue")
                if dlg and isinstance(dlg, dict):
                    beat_info["last_shot_dialogue"] = dlg.get("line", "")
            parts.append(json.dumps(beat_info, ensure_ascii=False))
        prev_script_context = "\n".join(parts)
    else:
        # 无剧本 JSON，退化为结构化元数据
        meta = {
            "heading": getattr(prev_scene, "heading", ""),
            "emotion_beat": getattr(prev_scene, "emotion_beat", ""),
            "cliffhanger": getattr(prev_scene, "cliffhanger", ""),
            "core_event": getattr(prev_scene, "core_event", ""),
            "tension_score": getattr(prev_scene, "tension_score", 0),
        }
        prev_script_context = json.dumps(meta, ensure_ascii=False)

    # ── next_scene_context ──
    if next_scene is None:
        next_scene_context = "【尾声 — 无后续场景】"
    else:
        meta = {
            "heading": getattr(next_scene, "heading", ""),
            "core_event": getattr(next_scene, "core_event", ""),
            "emotion_beat": getattr(next_scene, "emotion_beat", ""),
            "characters_present": getattr(next_scene, "characters_present", []) or [],
            "cliffhanger": getattr(next_scene, "cliffhanger", ""),
            "tension_score": getattr(next_scene, "tension_score", 0),
            "hook_type": getattr(next_scene, "hook_type", ""),
            "narrative_mode": getattr(next_scene, "narrative_mode", "mixed"),
        }
        # 若有已生成剧本，附加首个 beat 信息
        next_script_json = getattr(next_scene, "generated_script_json", None)
        if next_script_json and isinstance(next_script_json, dict):
            beats = next_script_json.get("beats", [])
            if beats:
                first_beat = beats[0]
                meta["first_beat_type"] = first_beat.get("type", "")
                shots = first_beat.get("shots", [])
                if shots:
                    meta["first_shot_action"] = shots[0].get("action", "")
        next_scene_context = json.dumps(meta, ensure_ascii=False)

    return prev_script_context, next_scene_context


@router.post("/projects/{project_id}/scenes/{scene_id}/generate-script")
def generate_script(
    project_id: str,
    scene_id: str,
    data: GenerateScriptRequest,
    db: Session = Depends(get_db),
):
    """Generate a script for a single scene via SSE streaming."""
    # 1. Load current scene
    scene = db.query(Scene).filter(
        Scene.id == scene_id, Scene.project_id == project_id
    ).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    # 2. Load all scenes ordered, find prev/next
    all_scenes = (
        db.query(Scene)
        .filter(Scene.project_id == project_id)
        .order_by(Scene.order)
        .all()
    )
    scene_idx = next((i for i, s in enumerate(all_scenes) if s.id == scene_id), 0)
    prev_scene = all_scenes[scene_idx - 1] if scene_idx > 0 else None
    next_scene = all_scenes[scene_idx + 1] if scene_idx < len(all_scenes) - 1 else None

    # 3. Get novel full text from ImportTask
    import_task = (
        db.query(ImportTask)
        .filter(ImportTask.project_id == project_id)
        .order_by(ImportTask.created_at.desc())
        .first()
    )
    full_text = import_task.full_text if import_task else ""

    # Extract source texts
    source_text = _get_scene_source_text(scene, full_text) if full_text else "（无原文）"
    prev_source_text = (
        _get_scene_source_text(prev_scene, full_text)
        if prev_scene and full_text
        else "【开场镜头 — 无前序场景】"
    )
    next_source_text = (
        _get_scene_source_text(next_scene, full_text)
        if next_scene and full_text
        else "【尾声 — 无后续场景】"
    )

    # 4. Build character profiles for characters_present
    character_profiles_str = "（无角色档案）"
    if scene.characters_present:
        chars = (
            db.query(Character)
            .filter(
                Character.project_id == project_id,
                Character.name.in_(scene.characters_present),
            )
            .all()
        )
        if chars:
            profiles = []
            for c in chars:
                profile = {
                    "name": c.name,
                    "role": c.role or "",
                    "personality": c.personality or "",
                    "appearance": c.appearance or {},
                    "costume": c.costume or {},
                    "desire": c.desire or "",
                    "flaw": c.flaw or "",
                    "relationships": c.relationships or [],
                }
                profiles.append(profile)
            character_profiles_str = json.dumps(profiles, ensure_ascii=False, indent=2)

    # 5. Build director baseline from novel_analysis_json
    director_baseline_str = "（无导演基准）"
    if import_task and import_task.novel_analysis_json:
        analysis = import_task.novel_analysis_json
        structured = analysis.get("structured", analysis)
        # Apply story bible overrides
        overrides = import_task.story_bible_overrides or {}
        for key, value in overrides.items():
            structured[key] = value
        baseline = {
            "genre_type": structured.get("genre_type", ""),
            "era": structured.get("era", ""),
            "themes": structured.get("themes", []),
            "pacing_type": structured.get("pacing_type", ""),
        }
        vb = structured.get("visual_baseline", {})
        if vb:
            baseline["art_style"] = vb.get("art_style", "")
            baseline["color_system"] = vb.get("color_system", "")
            baseline["lighting_baseline"] = vb.get("lighting_baseline", "")
        # 注入短剧参数
        sdp = structured.get("short_drama_params", {})
        if sdp:
            baseline["short_drama_params"] = sdp
        director_baseline_str = json.dumps(baseline, ensure_ascii=False, indent=2)

    # 6. Build scene_json
    scene_json_data = {
        "heading": scene.heading or "",
        "location": scene.location or "",
        "time_of_day": scene.time_of_day or "",
        "description": scene.description or "",
        "action": scene.action or "",
        "dialogue": scene.dialogue or [],
        "characters_present": scene.characters_present or [],
        "key_props": scene.key_props or [],
        "dramatic_purpose": scene.dramatic_purpose or "",
        "core_event": scene.core_event or "",
        "key_dialogue": scene.key_dialogue or "",
        "emotional_peak": scene.emotional_peak or "",
        "tension_score": scene.tension_score or 0,
        "estimated_duration_s": scene.estimated_duration_s,
        "visual_reference": scene.visual_reference or "",
        "visual_prompt_negative": scene.visual_prompt_negative or "",
        # 短剧增强字段
        "narrative_mode": scene.narrative_mode or "mixed",
        "hook_type": scene.hook_type or "",
        "cliffhanger": scene.cliffhanger or "",
        "reversal_points": scene.reversal_points or [],
        "sweet_spot": scene.sweet_spot or "",
        "emotion_beat": scene.emotion_beat or "",
        "dialogue_budget": scene.dialogue_budget or "medium",
    }
    scene_json_str = json.dumps(scene_json_data, ensure_ascii=False, indent=2)

    # 7. Build cross-scene context
    prev_script_context, next_scene_context = _build_cross_scene_context(prev_scene, next_scene)

    # 8. Render prompt
    user_direction = data.user_direction.strip() if data.user_direction else "无特别要求"
    prompt = render_prompt(
        "P_SCRIPT_GENERATE",
        scene_json=scene_json_str,
        source_text=source_text,
        prev_source_text=prev_source_text,
        next_source_text=next_source_text,
        prev_script_context=prev_script_context,
        next_scene_context=next_scene_context,
        character_profiles=character_profiles_str,
        director_baseline=director_baseline_str,
        user_direction=user_direction,
    )

    # 9. Stream response
    def event_stream():
        full_text_parts: list[str] = []
        try:
            for chunk in ai_engine.stream(
                system=prompt["system"],
                messages=[{"role": "user", "content": prompt["user"]}],
                capability_tier=prompt["capability_tier"],
                temperature=prompt["temperature"],
                max_tokens=prompt["max_tokens"],
                db=db,
            ):
                full_text_parts.append(chunk)
                yield f"data: {json.dumps({'type': 'text', 'content': chunk}, ensure_ascii=False)}\n\n"

            # Save to DB
            final_script = "".join(full_text_parts)
            # 尝试解析为结构化JSON
            script_json = None
            try:
                # 去除可能的markdown代码块标记
                clean_text = final_script.strip()
                if clean_text.startswith("```"):
                    first_newline = clean_text.index("\n")
                    clean_text = clean_text[first_newline + 1:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3].strip()
                script_json = json.loads(clean_text)
            except (json.JSONDecodeError, ValueError):
                logger.warning(f"Script output is not valid JSON for scene {scene_id}, storing as text only")

            if script_json:
                scene.generated_script_json = script_json
                # 生成纯文本摘要用于向后兼容
                summary_parts = []
                for beat in script_json.get("beats", []):
                    summary_parts.append(f"[{beat.get('timestamp', '')}] {beat.get('type', '')}")
                    for shot in beat.get("shots", []):
                        if shot.get("action"):
                            summary_parts.append(f"  {shot['action']}")
                        dlg = shot.get("dialogue")
                        if dlg and isinstance(dlg, dict) and dlg.get("line"):
                            summary_parts.append(f"  {dlg.get('character', '???')}: {dlg['line']}")
                scene.generated_script = "\n".join(summary_parts) if summary_parts else final_script
            else:
                scene.generated_script = final_script
            db.commit()

            # 返回done事件，附带解析后的JSON（如果有）
            done_payload = {"type": "done"}
            if script_json:
                done_payload["script_json"] = script_json
            yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Script generation stream error for scene {scene_id}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
