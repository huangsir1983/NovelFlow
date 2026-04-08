"""Knowledge base, Characters, Locations CRUD API + Story Bible aggregation."""

import json
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from database import get_db
from sqlalchemy.orm.attributes import flag_modified
from models.knowledge_base import KnowledgeBase
from models.character import Character
from models.location import Location
from models.project import Project
from models.beat import Beat
from models.import_task import ImportTask
from models.prop import Prop
from models.character_variant import CharacterVariant

router = APIRouter(tags=["knowledge"])


# ── Knowledge Base Schemas ────────────────────────────────────────

class KnowledgeBaseResponse(BaseModel):
    id: str
    project_id: str
    world_building: dict
    style_guide: dict
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class KnowledgeBaseUpdate(BaseModel):
    world_building: Optional[dict] = None
    style_guide: Optional[dict] = None


# ── Character Schemas ─────────────────────────────────────────────

class CharacterCreate(BaseModel):
    name: str
    aliases: list = []
    role: str = "supporting"
    description: str = ""
    personality: str = ""
    arc: str = ""
    relationships: list = []
    age_range: str = ""
    appearance: dict = {}
    costume: dict = {}
    casting_tags: list = []
    visual_reference: str = ""
    visual_prompt_negative: str = ""
    desire: str = ""
    flaw: str = ""


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    aliases: Optional[list] = None
    role: Optional[str] = None
    description: Optional[str] = None
    personality: Optional[str] = None
    arc: Optional[str] = None
    relationships: Optional[list] = None
    age_range: Optional[str] = None
    appearance: Optional[dict] = None
    costume: Optional[dict] = None
    casting_tags: Optional[list] = None
    visual_reference: Optional[str] = None
    visual_prompt_negative: Optional[str] = None
    desire: Optional[str] = None
    flaw: Optional[str] = None


class CharacterResponse(BaseModel):
    id: str
    project_id: str
    name: str
    aliases: list
    role: str
    description: str
    personality: str
    arc: str
    relationships: list
    age_range: str
    appearance: dict
    costume: dict
    casting_tags: list
    visual_reference: str
    visual_prompt_negative: str = ""
    desire: str
    flaw: str
    scene_presence: str = ""
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── Location Schemas ──────────────────────────────────────────────

class LocationCreate(BaseModel):
    name: str
    description: str = ""
    visual_description: str = ""
    mood: str = ""
    sensory: str = ""
    narrative_function: str = ""


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    visual_description: Optional[str] = None
    mood: Optional[str] = None
    sensory: Optional[str] = None
    narrative_function: Optional[str] = None


class LocationResponse(BaseModel):
    id: str
    project_id: str
    name: str
    description: str
    visual_description: str
    mood: str
    sensory: str
    narrative_function: str
    type: str = ""
    era_style: str = ""
    visual_reference: str = ""
    visual_prompt_negative: str = ""
    atmosphere: str = ""
    color_palette: list = []
    lighting: str = ""
    key_features: list = []
    narrative_scene_ids: list = []
    scene_count: int = 0
    time_variations: list = []
    emotional_range: str = ""
    viewpoints: list | None = []
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _coerce_nulls(cls, data: Any) -> Any:
        """DB columns that are NULL but schema expects list/str — coerce to defaults."""
        if hasattr(data, "__dict__"):
            # SQLAlchemy model instance
            import copy
            d = {c.name: getattr(data, c.name) for c in data.__table__.columns}
        elif isinstance(data, dict):
            d = data
        else:
            return data
        for field in ("viewpoints", "color_palette", "key_features", "narrative_scene_ids", "time_variations"):
            if d.get(field) is None:
                d[field] = []
        for field in ("description", "visual_description", "mood", "sensory", "narrative_function",
                       "type", "era_style", "visual_reference", "visual_prompt_negative",
                       "atmosphere", "lighting", "emotional_range"):
            if d.get(field) is None:
                d[field] = ""
        return d


# ── ViewPoint Schemas ────────────────────────────────────────────

class ViewPointCreate(BaseModel):
    label: str
    yaw: float = 0.0
    pitch: float = 0.0
    fov: float = 75.0
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0
    correction_strength: float = 0.5
    is_default: Optional[bool] = None


class ViewPointUpdate(BaseModel):
    label: Optional[str] = None
    yaw: Optional[float] = None
    pitch: Optional[float] = None
    fov: Optional[float] = None
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None
    pos_z: Optional[float] = None
    correction_strength: Optional[float] = None
    is_default: Optional[bool] = None


class ViewPointResponse(BaseModel):
    id: str
    label: str
    yaw: float
    pitch: float
    fov: float
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0
    correction_strength: float = 0.5
    is_default: bool


# ── Knowledge Base Routes ────────────────────────────────────────

@router.get("/projects/{project_id}/knowledge", response_model=KnowledgeBaseResponse)
def get_knowledge(project_id: str, db: Session = Depends(get_db)):
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.project_id == project_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb


@router.put("/projects/{project_id}/knowledge", response_model=KnowledgeBaseResponse)
def update_knowledge(project_id: str, data: KnowledgeBaseUpdate, db: Session = Depends(get_db)):
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.project_id == project_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    if data.world_building is not None:
        kb.world_building = data.world_building
    if data.style_guide is not None:
        kb.style_guide = data.style_guide

    db.commit()
    db.refresh(kb)
    return kb


# ── Character Routes ─────────────────────────────────────────────

@router.get("/projects/{project_id}/characters", response_model=list[CharacterResponse])
def list_characters(project_id: str, db: Session = Depends(get_db)):
    return db.query(Character).filter(Character.project_id == project_id).all()


@router.post("/projects/{project_id}/characters", response_model=CharacterResponse, status_code=201)
def create_character(project_id: str, data: CharacterCreate, db: Session = Depends(get_db)):
    character = Character(
        id=str(uuid4()),
        project_id=project_id,
        name=data.name,
        aliases=data.aliases,
        role=data.role,
        description=data.description,
        personality=data.personality,
        arc=data.arc,
        relationships=data.relationships,
        age_range=data.age_range,
        appearance=data.appearance,
        costume=data.costume,
        casting_tags=data.casting_tags,
        visual_reference=data.visual_reference,
        desire=data.desire,
        flaw=data.flaw,
    )
    db.add(character)
    db.commit()
    db.refresh(character)
    return character


@router.get("/projects/{project_id}/characters/{character_id}", response_model=CharacterResponse)
def get_character(project_id: str, character_id: str, db: Session = Depends(get_db)):
    character = db.query(Character).filter(Character.id == character_id, Character.project_id == project_id).first()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return character


@router.put("/projects/{project_id}/characters/{character_id}", response_model=CharacterResponse)
def update_character(project_id: str, character_id: str, data: CharacterUpdate, db: Session = Depends(get_db)):
    character = db.query(Character).filter(Character.id == character_id, Character.project_id == project_id).first()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    for field in ["name", "aliases", "role", "description", "personality", "arc", "relationships",
                   "age_range", "appearance", "costume", "casting_tags", "visual_reference",
                   "visual_prompt_negative", "desire", "flaw"]:
        value = getattr(data, field)
        if value is not None:
            setattr(character, field, value)

    db.commit()
    db.refresh(character)
    return character


@router.delete("/projects/{project_id}/characters/{character_id}", status_code=204)
def delete_character(project_id: str, character_id: str, db: Session = Depends(get_db)):
    character = db.query(Character).filter(Character.id == character_id, Character.project_id == project_id).first()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    db.delete(character)
    db.commit()
    return None


# ── Location Routes ──────────────────────────────────────────────

@router.get("/projects/{project_id}/locations", response_model=list[LocationResponse])
def list_locations(project_id: str, db: Session = Depends(get_db)):
    return db.query(Location).filter(Location.project_id == project_id).all()


@router.post("/projects/{project_id}/locations", response_model=LocationResponse, status_code=201)
def create_location(project_id: str, data: LocationCreate, db: Session = Depends(get_db)):
    location = Location(
        id=str(uuid4()),
        project_id=project_id,
        name=data.name,
        description=data.description,
        visual_description=data.visual_description,
        mood=data.mood,
        sensory=data.sensory,
        narrative_function=data.narrative_function,
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.get("/projects/{project_id}/locations/{location_id}", response_model=LocationResponse)
def get_location(project_id: str, location_id: str, db: Session = Depends(get_db)):
    location = db.query(Location).filter(Location.id == location_id, Location.project_id == project_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


@router.put("/projects/{project_id}/locations/{location_id}", response_model=LocationResponse)
def update_location(project_id: str, location_id: str, data: LocationUpdate, db: Session = Depends(get_db)):
    location = db.query(Location).filter(Location.id == location_id, Location.project_id == project_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    for field in ["name", "description", "visual_description", "mood", "sensory", "narrative_function"]:
        value = getattr(data, field)
        if value is not None:
            setattr(location, field, value)

    db.commit()
    db.refresh(location)
    return location


@router.delete("/projects/{project_id}/locations/{location_id}", status_code=204)
def delete_location(project_id: str, location_id: str, db: Session = Depends(get_db)):
    location = db.query(Location).filter(Location.id == location_id, Location.project_id == project_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    db.delete(location)
    db.commit()
    return None


# ── ViewPoint Routes (on Location) ──────────────────────────────

def _get_location_or_404(project_id: str, location_id: str, db: Session) -> Location:
    loc = db.query(Location).filter(Location.id == location_id, Location.project_id == project_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    return loc


@router.get(
    "/projects/{project_id}/locations/{location_id}/viewpoints",
    response_model=list[ViewPointResponse],
)
def list_viewpoints(project_id: str, location_id: str, db: Session = Depends(get_db)):
    loc = _get_location_or_404(project_id, location_id, db)
    return loc.viewpoints or []


@router.post(
    "/projects/{project_id}/locations/{location_id}/viewpoints",
    response_model=ViewPointResponse,
    status_code=201,
)
def add_viewpoint(project_id: str, location_id: str, data: ViewPointCreate, db: Session = Depends(get_db)):
    loc = _get_location_or_404(project_id, location_id, db)
    vps = list(loc.viewpoints or [])

    vp = {
        "id": f"vp-{uuid4().hex[:8]}",
        "label": data.label,
        "yaw": data.yaw,
        "pitch": data.pitch,
        "fov": data.fov,
        "pos_x": data.pos_x,
        "pos_y": data.pos_y,
        "pos_z": data.pos_z,
        "correction_strength": data.correction_strength,
        "is_default": data.is_default if data.is_default is not None else (len(vps) == 0),
    }

    # If this is set as default, unset others
    if vp["is_default"]:
        for v in vps:
            v["is_default"] = False

    vps.append(vp)
    loc.viewpoints = vps
    flag_modified(loc, "viewpoints")
    db.commit()
    db.refresh(loc)
    return vp


@router.put(
    "/projects/{project_id}/locations/{location_id}/viewpoints/{vp_id}",
    response_model=ViewPointResponse,
)
def update_viewpoint(
    project_id: str, location_id: str, vp_id: str,
    data: ViewPointUpdate, db: Session = Depends(get_db),
):
    loc = _get_location_or_404(project_id, location_id, db)
    vps = list(loc.viewpoints or [])
    target = None
    for v in vps:
        if v["id"] == vp_id:
            target = v
            break
    if target is None:
        raise HTTPException(status_code=404, detail="ViewPoint not found")

    if data.label is not None:
        target["label"] = data.label
    if data.yaw is not None:
        target["yaw"] = data.yaw
    if data.pitch is not None:
        target["pitch"] = data.pitch
    if data.fov is not None:
        target["fov"] = data.fov
    if data.pos_x is not None:
        target["pos_x"] = data.pos_x
    if data.pos_y is not None:
        target["pos_y"] = data.pos_y
    if data.pos_z is not None:
        target["pos_z"] = data.pos_z
    if data.correction_strength is not None:
        target["correction_strength"] = data.correction_strength
    if data.is_default is True:
        for v in vps:
            v["is_default"] = (v["id"] == vp_id)

    loc.viewpoints = vps
    flag_modified(loc, "viewpoints")
    db.commit()
    db.refresh(loc)
    return target


@router.put(
    "/projects/{project_id}/locations/{location_id}/viewpoints",
    response_model=list[ViewPointResponse],
)
def replace_viewpoints(
    project_id: str, location_id: str,
    data: list[ViewPointCreate],
    db: Session = Depends(get_db),
):
    """Batch replace all viewpoints for a location."""
    loc = _get_location_or_404(project_id, location_id, db)
    new_vps = []
    for i, vp_data in enumerate(data):
        new_vps.append({
            "id": vp_data.label and f"vp-{uuid4().hex[:8]}",
            "label": vp_data.label,
            "yaw": vp_data.yaw,
            "pitch": vp_data.pitch,
            "fov": vp_data.fov,
            "pos_x": vp_data.pos_x,
            "pos_y": vp_data.pos_y,
            "pos_z": vp_data.pos_z,
            "correction_strength": vp_data.correction_strength,
            "is_default": vp_data.is_default if vp_data.is_default is not None else (i == 0),
        })
    loc.viewpoints = new_vps
    flag_modified(loc, "viewpoints")
    db.commit()
    db.refresh(loc)
    return loc.viewpoints or []


@router.delete(
    "/projects/{project_id}/locations/{location_id}/viewpoints/{vp_id}",
    status_code=204,
)
def delete_viewpoint(
    project_id: str, location_id: str, vp_id: str,
    db: Session = Depends(get_db),
):
    loc = _get_location_or_404(project_id, location_id, db)
    vps = list(loc.viewpoints or [])
    new_vps = [v for v in vps if v["id"] != vp_id]
    if len(new_vps) == len(vps):
        raise HTTPException(status_code=404, detail="ViewPoint not found")
    loc.viewpoints = new_vps
    flag_modified(loc, "viewpoints")
    db.commit()
    return None


@router.delete("/projects/{project_id}/props/{prop_id}", status_code=204)
def delete_prop(project_id: str, prop_id: str, db: Session = Depends(get_db)):
    prop = db.query(Prop).filter(Prop.id == prop_id, Prop.project_id == project_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Prop not found")
    db.delete(prop)
    db.commit()
    return None


@router.delete("/projects/{project_id}/variants/{variant_id}", status_code=204)
def delete_variant(project_id: str, variant_id: str, db: Session = Depends(get_db)):
    variant = db.query(CharacterVariant).filter(CharacterVariant.id == variant_id, CharacterVariant.project_id == project_id).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    db.delete(variant)
    db.commit()
    return None


# ── Story Bible Aggregation ─────────────────────────────────────

class StoryBibleUpdateRequest(BaseModel):
    overrides: dict = {}


def _get_merged_story_bible(import_task, overrides: dict | None = None) -> dict:
    """Merge novel_analysis_json.structured with story_bible_overrides."""
    if not import_task or not import_task.novel_analysis_json:
        return {}
    analysis = import_task.novel_analysis_json
    structured = dict(analysis.get("structured", analysis))
    report = analysis.get("report", {})
    # Apply stored overrides
    stored_overrides = import_task.story_bible_overrides or {}
    for k, v in stored_overrides.items():
        structured[k] = v
    # Apply request overrides on top
    if overrides:
        for k, v in overrides.items():
            structured[k] = v
    return {
        "structured": structured,
        "report": report,
    }


@router.get("/projects/{project_id}/story-bible")
def get_story_bible(project_id: str, db: Session = Depends(get_db)):
    """Aggregated Story Bible view: characters + locations + world_building + style_guide + key beats + stats + novel analysis."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    characters = db.query(Character).filter(Character.project_id == project_id).all()
    locations = db.query(Location).filter(Location.project_id == project_id).all()
    beats = db.query(Beat).filter(Beat.project_id == project_id).order_by(Beat.order).all()

    kb = db.query(KnowledgeBase).filter(KnowledgeBase.project_id == project_id).first()
    world_building = kb.world_building if kb else {}
    style_guide = kb.style_guide if kb else {}

    # Load import task for novel_analysis_json
    import_task = (
        db.query(ImportTask)
        .filter(ImportTask.project_id == project_id)
        .order_by(ImportTask.created_at.desc())
        .first()
    )
    merged = _get_merged_story_bible(import_task)

    # Key beats: high emotional impact or hook potential
    key_beats = [
        {
            "id": b.id,
            "title": b.title,
            "beat_type": b.beat_type,
            "emotional_value": b.emotional_value,
            "order": b.order,
        }
        for b in beats
        if abs(b.emotional_value) >= 0.6
    ][:10]

    return {
        "project_id": project_id,
        "project_name": project.name,
        "characters": [
            {
                "id": c.id, "name": c.name, "aliases": c.aliases or [], "role": c.role,
                "description": c.description or "", "personality": c.personality or "",
                "arc": c.arc or "", "desire": c.desire or "", "flaw": c.flaw or "",
                "age_range": getattr(c, "age_range", "") or "",
                "appearance": getattr(c, "appearance", {}) or {},
                "costume": getattr(c, "costume", {}) or {},
                "visual_reference": getattr(c, "visual_reference", "") or "",
                "visual_prompt_negative": getattr(c, "visual_prompt_negative", "") or "",
            }
            for c in characters
        ],
        "locations": [
            {
                "id": l.id, "name": l.name, "description": l.description or "",
                "visual_description": l.visual_description or "",
                "mood": l.mood or "",
                "sensory": getattr(l, "sensory", "") or "",
                "narrative_function": getattr(l, "narrative_function", "") or "",
            }
            for l in locations
        ],
        "world_building": world_building,
        "style_guide": style_guide,
        "key_beats": key_beats,
        "novel_analysis": merged.get("structured", {}),
        "novel_analysis_report": merged.get("report", {}),
        "stats": {
            "character_count": len(characters),
            "location_count": len(locations),
            "beat_count": len(beats),
            "protagonist_count": sum(1 for c in characters if c.role == "protagonist"),
            "antagonist_count": sum(1 for c in characters if c.role == "antagonist"),
        },
    }


@router.put("/projects/{project_id}/story-bible")
def update_story_bible(project_id: str, data: StoryBibleUpdateRequest, db: Session = Depends(get_db)):
    """Update Story Bible overrides — merges into import_task.story_bible_overrides."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    import_task = (
        db.query(ImportTask)
        .filter(ImportTask.project_id == project_id)
        .order_by(ImportTask.created_at.desc())
        .first()
    )
    if not import_task:
        raise HTTPException(status_code=404, detail="No import task found for project")

    # Merge new overrides with existing
    existing = import_task.story_bible_overrides or {}
    existing.update(data.overrides)
    import_task.story_bible_overrides = existing
    db.commit()
    db.refresh(import_task)

    # Return merged story bible
    merged = _get_merged_story_bible(import_task)
    return {
        "status": "ok",
        "overrides": import_task.story_bible_overrides,
        "novel_analysis": merged.get("structured", {}),
        "novel_analysis_report": merged.get("report", {}),
    }
