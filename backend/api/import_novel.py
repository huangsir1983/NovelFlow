"""Novel import API endpoint."""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.project import Project
from models.chapter import Chapter
from models.beat import Beat
from models.scene import Scene
from models.character import Character
from models.location import Location
from models.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

router = APIRouter(tags=["import"])

ALLOWED_EXTENSIONS = {"txt", "md", "docx", "epub", "pdf"}


class ImportResult(BaseModel):
    chapter_count: int
    character_count: int
    beat_count: int
    scene_count: int
    location_count: int
    stage: str


@router.post("/projects/{project_id}/import/novel", response_model=ImportResult)
def import_novel(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Import a novel file: parse -> split chapters -> extract characters -> generate beats -> extract scenes."""

    # Validate project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate file extension
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file format: .{ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Validate file size
    file_bytes = file.file.read()
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_size:
        raise HTTPException(status_code=400, detail=f"File too large. Max: {settings.max_upload_size_mb}MB")

    # Import pipeline
    from services.novel_parser import (
        read_file,
        split_chapters,
        extract_characters,
        generate_beats,
        extract_scenes,
        build_knowledge_base,
    )

    # Step 1: Read file
    try:
        full_text = read_file(file_bytes, file.filename or "upload.txt")
    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    if not full_text.strip():
        raise HTTPException(status_code=400, detail="File is empty")

    # Step 2: Split chapters
    chapter_data_list = split_chapters(full_text, db=db)

    # Save chapters
    chapter_records = []
    for ch_data in chapter_data_list:
        chapter = Chapter(
            id=str(uuid4()),
            project_id=project_id,
            title=ch_data.get("title", ""),
            content=ch_data.get("content", ""),
            order=ch_data.get("order", 0),
            word_count=len(ch_data.get("content", "")),
        )
        db.add(chapter)
        chapter_records.append(chapter)
    db.flush()

    # Step 3: Extract characters (from full text)
    character_data_list = extract_characters(full_text, db=db)

    for char_data in character_data_list:
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
    db.flush()

    # Step 4: Generate beats and extract scenes per chapter
    total_beat_order = 0
    total_scene_order = 0
    beat_count = 0
    scene_count = 0

    for chapter in chapter_records:
        if not chapter.content.strip():
            continue

        # Generate beats for this chapter
        beat_data_list = generate_beats(chapter.content, db=db)
        for beat_data in beat_data_list:
            beat = Beat(
                id=str(uuid4()),
                project_id=project_id,
                chapter_id=chapter.id,
                title=beat_data.get("title", ""),
                description=beat_data.get("description", ""),
                beat_type=beat_data.get("beat_type", "event"),
                emotional_value=float(beat_data.get("emotional_value", 0.0)),
                order=total_beat_order,
            )
            db.add(beat)
            total_beat_order += 1
            beat_count += 1

        # Extract scenes for this chapter
        scene_data_list = extract_scenes(chapter.content, db=db)
        for scene_data in scene_data_list:
            scene = Scene(
                id=str(uuid4()),
                project_id=project_id,
                heading=scene_data.get("heading", ""),
                location=scene_data.get("location", ""),
                time_of_day=scene_data.get("time_of_day", ""),
                description=scene_data.get("description", ""),
                action=scene_data.get("action", ""),
                dialogue=scene_data.get("dialogue", []),
                order=total_scene_order,
                tension_score=float(scene_data.get("tension_score", 0.0)),
            )
            db.add(scene)
            total_scene_order += 1
            scene_count += 1

    db.flush()

    # Step 5: Build knowledge base
    kb_data = build_knowledge_base(full_text, db=db)
    kb = KnowledgeBase(
        id=str(uuid4()),
        project_id=project_id,
        world_building=kb_data.get("world_building", {}),
        style_guide=kb_data.get("style_guide", {}),
    )
    db.add(kb)

    # Save locations from knowledge base
    location_count = 0
    for loc_data in kb_data.get("locations", []):
        location = Location(
            id=str(uuid4()),
            project_id=project_id,
            name=loc_data.get("name", ""),
            description=loc_data.get("description", ""),
            visual_description=loc_data.get("visual_description", ""),
            mood=loc_data.get("mood", ""),
        )
        db.add(location)
        location_count += 1

    # Update project stage
    project.stage = "knowledge"
    db.commit()

    return ImportResult(
        chapter_count=len(chapter_records),
        character_count=len(character_data_list),
        beat_count=beat_count,
        scene_count=scene_count,
        location_count=location_count,
        stage="knowledge",
    )
