"""Knowledge base, Characters, and Locations CRUD API."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.knowledge_base import KnowledgeBase
from models.character import Character
from models.location import Location

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


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    aliases: Optional[list] = None
    role: Optional[str] = None
    description: Optional[str] = None
    personality: Optional[str] = None
    arc: Optional[str] = None
    relationships: Optional[list] = None


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
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── Location Schemas ──────────────────────────────────────────────

class LocationCreate(BaseModel):
    name: str
    description: str = ""
    visual_description: str = ""
    mood: str = ""


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    visual_description: Optional[str] = None
    mood: Optional[str] = None


class LocationResponse(BaseModel):
    id: str
    project_id: str
    name: str
    description: str
    visual_description: str
    mood: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


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

    for field in ["name", "aliases", "role", "description", "personality", "arc", "relationships"]:
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

    for field in ["name", "description", "visual_description", "mood"]:
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
