"""Shot actions API — generation, storyboard readiness, and board transition."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.project import Project
from models.shot import Shot
from models.shot_group import ShotGroup
from models.scene import Scene
from models.beat import Beat

logger = logging.getLogger(__name__)

router = APIRouter(tags=["shots"])


class ShotGenerateRequest(BaseModel):
    gen_type: str = "image"  # image | video


class StoryboardAnimaticBuildRequest(BaseModel):
    shot_ids: list[str] = []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _parse_duration_ms(value: str | None) -> int:
    raw = _text(value).lower()
    digits = "".join(ch for ch in raw if ch.isdigit() or ch == ".")
    if not digits:
        return 4000
    numeric = float(digits)
    if "ms" in raw:
        return int(numeric)
    if "min" in raw:
        return int(numeric * 60_000)
    return int(numeric * 1000)


def _scene_generated_shots(scene: Scene) -> list[dict[str, Any]]:
    generated = scene.generated_script_json or {}
    beats = generated.get("beats") or []
    extracted: list[dict[str, Any]] = []
    for beat in beats:
        for shot in beat.get("shots") or []:
            extracted.append(shot)
    return extracted


def _build_scene_report(scene: Scene, shots_in_scene: list[Shot]) -> dict[str, Any]:
    generated_shots = _scene_generated_shots(scene)
    beat_total = len((scene.generated_script_json or {}).get("beats") or [])
    covered_beats = sum(
        1 for beat in ((scene.generated_script_json or {}).get("beats") or []) if (beat.get("shots") or [])
    )
    shot_total = len(shots_in_scene) if shots_in_scene else len(generated_shots)
    checklist = [
        {
            "id": "shot_coverage",
            "label": "Shot coverage",
            "status": "pass" if shot_total > 0 else "fail",
            "detail": f"Scene has {shot_total} storyboard shots." if shot_total > 0 else "Scene has no usable storyboard shots.",
            "hardGate": True,
        },
        {
            "id": "beat_coverage",
            "label": "Beat coverage",
            "status": "pass" if beat_total == 0 and shot_total > 0 else "warn" if beat_total == 0 else "pass" if covered_beats == beat_total else "fail",
            "detail": "No beat map was found, but explicit shot data is already available." if beat_total == 0 and shot_total > 0 else "No structured beat map was found." if beat_total == 0 else f"{covered_beats}/{beat_total} beats are covered by shots.",
            "hardGate": beat_total > 0,
        },
        {
            "id": "narrative_goal",
            "label": "Narrative goal",
            "status": "pass" if _text(scene.core_event) or _text(scene.dramatic_purpose) else "fail",
            "detail": "Scene goal is explicit." if _text(scene.core_event) or _text(scene.dramatic_purpose) else "Scene is missing a core event or dramatic purpose.",
            "hardGate": True,
        },
        {
            "id": "time_place",
            "label": "Time and place",
            "status": "pass" if _text(scene.location) and _text(scene.time_of_day) else "warn" if _text(scene.location) or _text(scene.time_of_day) else "fail",
            "detail": "Scene location and time are available." if _text(scene.location) and _text(scene.time_of_day) else "Scene is missing part of the location/time context.",
            "hardGate": False,
        },
        {
            "id": "characters",
            "label": "Character presence",
            "status": "pass" if (scene.characters_present or []) else "warn",
            "detail": "Scene has explicit characters." if (scene.characters_present or []) else "Scene does not yet list clear characters.",
            "hardGate": False,
        },
        {
            "id": "visual_basis",
            "label": "Visual basis",
            "status": "pass" if _text(scene.visual_reference) or _text(scene.description) or _text(scene.action) else "warn",
            "detail": "Scene has visual basis." if _text(scene.visual_reference) or _text(scene.description) or _text(scene.action) else "Scene is thin on visual basis.",
            "hardGate": False,
        },
    ]
    hard_fails = [item["detail"] for item in checklist if item["hardGate"] and item["status"] == "fail"]
    soft_issues = [item["detail"] for item in checklist if not item["hardGate"] and item["status"] != "pass"]
    status = "blocked" if hard_fails else "patchable" if soft_issues else "ready"
    return {
        "sceneId": scene.id,
        "heading": scene.heading,
        "order": scene.order,
        "status": status,
        "totalShotCount": shot_total,
        "readyShotIds": [],
        "patchableShotIds": [],
        "blockedShotIds": [],
        "beatCoverage": {"total": beat_total, "covered": covered_beats},
        "checklist": checklist,
        "blockedReasons": hard_fails,
        "patchableReasons": soft_issues,
    }


def _build_shot_check(scene: Scene, shot: Shot | None, fallback: dict[str, Any] | None) -> dict[str, Any]:
    subject = ", ".join(shot.characters_in_frame) if shot and shot.characters_in_frame else _text((fallback or {}).get("subject"))
    action = _text(shot.description if shot else (fallback or {}).get("action"))
    framing = _text(shot.framing if shot else (fallback or {}).get("shot_type"))
    angle = _text(shot.camera_angle if shot else (fallback or {}).get("angle"))
    move = _text(shot.camera_movement if shot else (fallback or {}).get("camera_move")) or "static"
    duration_ms = _parse_duration_ms(shot.duration_estimate if shot else None) if shot else 4000
    scene_context = _text(scene.heading) or _text(scene.location)
    continuity_status = "ready" if (shot and shot.characters_in_frame and scene.location) else "partial" if (shot and shot.characters_in_frame) or _text(scene.location) else "missing"
    prompt_complete_count = sum(
        1 for flag in [_text(action), _text(scene.visual_reference) or _text(scene.description), _text(move)] if flag
    )
    prompt_completeness = "complete" if prompt_complete_count >= 3 else "partial" if prompt_complete_count >= 2 else "insufficient"

    checklist = [
        {"id": "subject", "label": "Subject", "status": "pass" if _text(subject) else "fail", "detail": "Shot has a subject." if _text(subject) else "Shot is missing a subject.", "hardGate": True},
        {"id": "action", "label": "Action", "status": "pass" if _text(action) else "fail", "detail": "Shot action is explicit." if _text(action) else "Shot is missing action.", "hardGate": True},
        {"id": "framing", "label": "Framing / shot type", "status": "pass" if _text(framing) else "fail", "detail": "Shot framing is defined." if _text(framing) else "Shot is missing framing.", "hardGate": True},
        {"id": "camera_angle", "label": "Camera angle", "status": "pass" if _text(angle) else "fail", "detail": "Camera angle is defined." if _text(angle) else "Shot is missing camera angle.", "hardGate": True},
        {"id": "camera_move", "label": "Camera move", "status": "pass" if move != "static" else "warn", "detail": "Camera move is explicit." if move != "static" else "Camera move falls back to static.", "hardGate": False},
        {"id": "duration", "label": "Duration", "status": "pass" if duration_ms > 0 else "fail", "detail": f"Shot duration is {duration_ms}ms." if duration_ms > 0 else "Shot has no usable duration.", "hardGate": True},
        {"id": "scene_context", "label": "Scene context", "status": "pass" if _text(scene_context) else "fail", "detail": "Scene context is available." if _text(scene_context) else "Shot is missing scene context.", "hardGate": True},
        {"id": "continuity_anchors", "label": "Continuity anchors", "status": "pass" if continuity_status == "ready" else "warn" if continuity_status == "partial" else "fail", "detail": "Continuity anchors are ready." if continuity_status == "ready" else "Continuity anchors are partial." if continuity_status == "partial" else "Continuity anchors are missing.", "hardGate": False},
    ]
    hard_fails = [item["detail"] for item in checklist if item["hardGate"] and item["status"] == "fail"]
    soft_issues = [item["detail"] for item in checklist if not item["hardGate"] and item["status"] != "pass"]
    status = "blocked" if hard_fails else "fallback_only" if soft_issues else "ready"
    shot_id = shot.id if shot else f"{scene.id}:generated:{len((_scene_generated_shots(scene) or []))}"
    return {
        "shotId": shot_id,
        "sceneId": scene.id,
        "shotNumber": shot.shot_number if shot else 1,
        "status": status,
        "promptCompleteness": prompt_completeness,
        "continuityAnchorStatus": continuity_status,
        "checklist": checklist,
        "blockedReasons": hard_fails,
        "fallbackReasons": soft_issues,
    }


def _build_video_mode_decision(scene: Scene, shot_check: dict[str, Any], shot: Shot | None) -> dict[str, Any]:
    available_modes: list[str] = []
    blocked_modes: dict[str, str] = {}
    has_characters = bool((shot.characters_in_frame if shot else []) or (scene.characters_present or []))
    has_scene_anchor = bool(_text(scene.location))
    has_visual_prompt = bool(_text(shot.visual_prompt) if shot else _text(scene.visual_reference))
    text_allowed = shot_check["status"] != "blocked" and shot_check["promptCompleteness"] != "insufficient"
    image_allowed = shot_check["status"] == "ready" and has_visual_prompt and has_characters
    scene_character_allowed = shot_check["status"] != "blocked" and has_characters and has_scene_anchor

    if image_allowed:
        available_modes.append("image_to_video")
    else:
        blocked_modes["image_to_video"] = "Image-to-video needs a ready shot, strong prompt, and character anchor."
    if scene_character_allowed:
        available_modes.append("scene_character_to_video")
    else:
        blocked_modes["scene_character_to_video"] = "Scene-character mode needs both scene and character anchors."
    if text_allowed:
        available_modes.append("text_to_video")
    else:
        blocked_modes["text_to_video"] = "Text-to-video requires enough story text."

    recommended_mode = (
        "image_to_video"
        if "image_to_video" in available_modes
        else "scene_character_to_video"
        if "scene_character_to_video" in available_modes
        else "text_to_video"
        if "text_to_video" in available_modes
        else None
    )
    rationale = (
        "Image-to-video is recommended because the shot is structurally ready and has stronger control."
        if recommended_mode == "image_to_video"
        else "Scene-character mode is recommended because both scene and character anchors are available."
        if recommended_mode == "scene_character_to_video"
        else "Text-to-video is the only safe fallback path right now and carries higher consistency risk."
        if recommended_mode == "text_to_video"
        else "No video mode is currently available."
    )
    return {
        "recommendedMode": recommended_mode,
        "selectedMode": recommended_mode,
        "availableModes": available_modes,
        "blockedModes": blocked_modes,
        "defaultVideoModePolicy": "auto_recommend_override",
        "rationale": rationale,
    }


@router.post("/projects/{project_id}/shots/{shot_id}/generate")
def generate_from_shot(
    project_id: str,
    shot_id: str,
    data: ShotGenerateRequest,
    db: Session = Depends(get_db),
):
    """Trigger image/video generation from a Shot Card's visual prompt."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    shot = db.query(Shot).filter(Shot.id == shot_id, Shot.project_id == project_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    # Get visual prompt — prefer shot_group prompt, fallback to shot prompt
    prompt = shot.visual_prompt or ""
    if not prompt:
        group = db.query(ShotGroup).filter(
            ShotGroup.project_id == project_id,
            ShotGroup.scene_id == shot.scene_id,
        ).first()
        if group:
            prompt = group.visual_prompt_positive or ""

    if not prompt:
        raise HTTPException(status_code=400, detail="No visual prompt available for this shot")

    from services.ai_engine import ai_engine

    try:
        if data.gen_type == "video":
            result = ai_engine.generate_video(prompt=prompt, db=db)
            candidate = {
                "type": "video",
                "url": result.get("video_url", ""),
                "model": result.get("model", ""),
                "provider": result.get("provider", ""),
            }
        else:
            result = ai_engine.generate_image(prompt=prompt, db=db)
            import base64
            img_b64 = base64.b64encode(result["image_data"]).decode() if result.get("image_data") else ""
            candidate = {
                "type": "image",
                "data_b64": img_b64[:100] + "..." if len(img_b64) > 100 else img_b64,  # truncated for response
                "mime_type": result.get("mime_type", "image/png"),
                "model": result.get("model", ""),
                "provider": result.get("provider", ""),
            }

        # Append to shot candidates
        candidates = shot.candidates or []
        candidates.append(candidate)
        shot.candidates = candidates
        db.commit()

        return {"status": "ok", "candidate": candidate, "total_candidates": len(candidates)}

    except Exception as e:
        logger.error(f"Shot generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/storyboard-video-readiness")
def storyboard_video_readiness(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.order.asc()).all()
    shots = db.query(Shot).filter(Shot.project_id == project_id).order_by(Shot.scene_id.asc(), Shot.order.asc()).all()
    shots_by_scene: dict[str, list[Shot]] = {}
    for shot in shots:
        shots_by_scene.setdefault(shot.scene_id, []).append(shot)

    scene_reports: list[dict[str, Any]] = []
    shot_checks: list[dict[str, Any]] = []
    for scene in scenes:
        scene_shots = shots_by_scene.get(scene.id, [])
        report = _build_scene_report(scene, scene_shots)
        scene_reports.append(report)

        if scene_shots:
            for shot in scene_shots:
                check = _build_shot_check(scene, shot, None)
                if check["status"] == "blocked":
                    report["blockedShotIds"].append(check["shotId"])
                elif check["status"] == "fallback_only":
                    report["patchableShotIds"].append(check["shotId"])
                else:
                    report["readyShotIds"].append(check["shotId"])
                shot_checks.append(check)
        else:
            for fallback in _scene_generated_shots(scene):
                check = _build_shot_check(scene, None, fallback)
                if check["status"] == "blocked":
                    report["blockedShotIds"].append(check["shotId"])
                elif check["status"] == "fallback_only":
                    report["patchableShotIds"].append(check["shotId"])
                else:
                    report["readyShotIds"].append(check["shotId"])
                shot_checks.append(check)

    return {
        "project_id": project_id,
        "scene_reports": scene_reports,
        "shot_checks": shot_checks,
    }


@router.post("/projects/{project_id}/shots/{shot_id}/video-mode-decision")
def shot_video_mode_decision(project_id: str, shot_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    shot = db.query(Shot).filter(Shot.project_id == project_id, Shot.id == shot_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    scene = db.query(Scene).filter(Scene.project_id == project_id, Scene.id == shot.scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    shot_check = _build_shot_check(scene, shot, None)
    return _build_video_mode_decision(scene, shot_check, shot)


@router.post("/projects/{project_id}/animatic/storyboard-build")
def build_storyboard_animatic(
    project_id: str,
    payload: StoryboardAnimaticBuildRequest,
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    query = db.query(Shot).filter(Shot.project_id == project_id).order_by(Shot.scene_id.asc(), Shot.order.asc())
    if payload.shot_ids:
        query = query.filter(Shot.id.in_(payload.shot_ids))
    shots = query.all()

    clips = []
    for shot in shots:
        scene = db.query(Scene).filter(Scene.project_id == project_id, Scene.id == shot.scene_id).first()
        shot_check = _build_shot_check(scene, shot, None) if scene else None
        decision = _build_video_mode_decision(scene, shot_check, shot) if scene and shot_check else None
        clips.append(
            {
                "shotId": shot.id,
                "sourceType": "image",
                "artifactId": f"storyboard:{shot.id}",
                "durationMs": _parse_duration_ms(shot.duration_estimate),
                "transitionHint": shot.transition_out or shot.transition_in or "cut",
                "cameraMove": shot.camera_movement or "static",
                "sourceNodeId": "storyboard_animatic_checkpoint",
                "sourceModuleId": None,
                "sourceArtifactVersion": 1,
                "heat": "watch" if shot_check and shot_check["status"] == "fallback_only" else "stable",
                "issueSummary": shot_check["fallbackReasons"][0] if shot_check and shot_check["fallbackReasons"] else None,
                "label": shot.goal or f"Shot {shot.shot_number}",
                "phase": "storyboard",
                "mode": decision["recommendedMode"] if decision else None,
                "riskTag": "high_consistency_risk" if decision and decision["recommendedMode"] == "text_to_video" else "standard",
            }
        )

    return {
        "id": f"animatic:storyboard:{project_id}",
        "projectId": project_id,
        "clipCount": len(clips),
        "clips": clips,
    }


@router.post("/projects/{project_id}/enter-board")
def enter_board(project_id: str, db: Session = Depends(get_db)):
    """Check readiness and transition project from workbench to board phase."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check sufficiency
    beat_count = db.query(Beat).filter(Beat.project_id == project_id).count()
    scene_count = db.query(Scene).filter(Scene.project_id == project_id).count()
    shot_count = db.query(Shot).filter(Shot.project_id == project_id).count()

    issues = []
    if beat_count < 3:
        issues.append(f"节拍数量不足（当前 {beat_count}，建议至少 3 个）")
    if scene_count < 1:
        issues.append(f"场景数量不足（当前 {scene_count}，需要至少 1 个）")

    if issues:
        return {
            "ready": False,
            "issues": issues,
            "stats": {"beats": beat_count, "scenes": scene_count, "shots": shot_count},
        }

    # Transition to board phase
    project.current_phase = "board"
    if project.stage in ("import", "knowledge", "beat_sheet", "script"):
        project.stage = "storyboard"
    db.commit()

    return {
        "ready": True,
        "current_phase": project.current_phase,
        "stage": project.stage,
        "stats": {"beats": beat_count, "scenes": scene_count, "shots": shot_count},
    }
