"""Shot actions API — generate images/videos from Shot Cards, enter-board transition."""

import logging
from uuid import uuid4

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
