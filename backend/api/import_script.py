"""Script import API endpoint."""

import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.project import Project
from models.beat import Beat
from models.scene import Scene
from models.character import Character
from models.location import Location
from models.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

router = APIRouter(tags=["import"])

ALLOWED_EXTENSIONS = {"txt", "md", "docx", "fountain", "fdx", "pdf"}


class ScriptImportResult(BaseModel):
    scene_count: int
    beat_count: int
    character_count: int
    location_count: int
    format_detected: str
    visual_readiness_score: float
    stage: str


@router.post("/projects/{project_id}/import/script", response_model=ScriptImportResult)
def import_script(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Import a script file: detect format -> parse -> reverse-extract beats -> build knowledge -> assess readiness."""

    # Validate project
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Edition gating: Canvas+ only
    if project.edition == "normal":
        raise HTTPException(status_code=403, detail="Script import requires Canvas edition or above")

    # Validate file
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported format: .{ext}")

    from config import settings
    file_bytes = file.file.read()
    if len(file_bytes) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large. Max: {settings.max_upload_size_mb}MB")

    # Read file content
    from services.novel_parser import read_file
    try:
        text = read_file(file_bytes, file.filename or "script.txt")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    if not text.strip():
        raise HTTPException(status_code=400, detail="File is empty")

    # Step 1: Detect format
    from services.script_parser import detect_format, parse_fountain, parse_fdx, parse_free_text, standardize

    format_info = detect_format(text, db=db)
    format_name = format_info["format"]

    # Step 2: Parse based on format
    if format_name == "fountain":
        raw_scenes = parse_fountain(text)
    elif format_name == "fdx":
        raw_scenes = parse_fdx(text)
    else:
        raw_scenes = parse_free_text(text, db=db)

    scenes_data = standardize(raw_scenes)

    if not scenes_data:
        raise HTTPException(status_code=400, detail="No scenes could be extracted from the script")

    # Step 3: Reverse extract beats
    from services.script_adapter import reverse_extract_beats, reverse_build_knowledge, assess_visual_readiness

    scenes_json = json.dumps(scenes_data, ensure_ascii=False)
    beat_data_list = reverse_extract_beats(scenes_json, db=db)

    # Step 4: Reverse build knowledge
    kb_data = reverse_build_knowledge(scenes_json, db=db)

    # Step 5: Assess visual readiness
    readiness = assess_visual_readiness(scenes_json, db=db)
    visual_readiness_score = readiness.get("overall_score", 0.0)

    # Save scenes
    for scene_data in scenes_data:
        scene = Scene(
            id=str(uuid4()),
            project_id=project_id,
            heading=scene_data.get("heading", ""),
            location=scene_data.get("location", ""),
            time_of_day=scene_data.get("time_of_day", ""),
            description=scene_data.get("description", ""),
            action=scene_data.get("action", ""),
            dialogue=scene_data.get("dialogue", []),
            order=scene_data.get("order", 0),
            tension_score=float(scene_data.get("tension_score", 0.0)),
        )
        db.add(scene)

    # Save beats
    for i, beat_data in enumerate(beat_data_list):
        beat = Beat(
            id=str(uuid4()),
            project_id=project_id,
            title=beat_data.get("title", ""),
            description=beat_data.get("description", ""),
            beat_type=beat_data.get("beat_type", "event"),
            emotional_value=float(beat_data.get("emotional_value", 0.0)),
            order=i,
        )
        db.add(beat)

    # Save characters from knowledge
    characters_data = kb_data.get("characters", [])
    for char_data in characters_data:
        character = Character(
            id=str(uuid4()),
            project_id=project_id,
            name=char_data.get("name", "Unknown"),
            aliases=char_data.get("aliases", []),
            role=char_data.get("role", "supporting"),
            description=char_data.get("description", ""),
            personality=char_data.get("personality", ""),
            arc=char_data.get("arc", ""),
            relationships=char_data.get("relationships", []),
        )
        db.add(character)

    # Save locations
    locations_data = kb_data.get("locations", [])
    for loc_data in locations_data:
        location = Location(
            id=str(uuid4()),
            project_id=project_id,
            name=loc_data.get("name", ""),
            description=loc_data.get("description", ""),
            visual_description=loc_data.get("visual_description", ""),
            mood=loc_data.get("mood", ""),
        )
        db.add(location)

    # Save knowledge base
    kb = KnowledgeBase(
        id=str(uuid4()),
        project_id=project_id,
        world_building=kb_data.get("world_building", {}),
        style_guide=kb_data.get("style_guide", {}),
    )
    db.add(kb)

    # Update project stage
    project.stage = "knowledge"
    db.commit()

    return ScriptImportResult(
        scene_count=len(scenes_data),
        beat_count=len(beat_data_list),
        character_count=len(characters_data),
        location_count=len(locations_data),
        format_detected=format_name,
        visual_readiness_score=visual_readiness_score,
        stage="knowledge",
    )
