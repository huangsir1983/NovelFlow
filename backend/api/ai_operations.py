"""AI operations API — streaming rewrite/expand/condense/dialogue optimization + beat generation."""

import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.project import Project
from models.chapter import Chapter
from models.beat import Beat

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ai"])


# --- Schemas ---

class AIOperateRequest(BaseModel):
    text: str
    operation: str  # rewrite|expand|condense|dialogue_optimize|visualize|tone_shift|continue_3way|scene_detail|subtext|dialogue_rhythm
    context: str = ""  # additional context
    tone: str = ""  # for tone_shift operation


class GenerateBeatsRequest(BaseModel):
    chapter_id: str


# --- Routes ---

@router.post("/projects/{project_id}/ai/operate")
def ai_operate(project_id: str, data: AIOperateRequest, db: Session = Depends(get_db)):
    """AI text operation with SSE streaming response."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    valid_ops = {
        "rewrite": "改写", "expand": "扩写", "condense": "缩写", "dialogue_optimize": "对话优化",
        "visualize": "视觉化", "tone_shift": "换语气", "continue_3way": "AI续写三方向",
        "scene_detail": "补充场景描写", "subtext": "补充潜台词", "dialogue_rhythm": "调整对白节奏",
    }
    if data.operation not in valid_ops:
        raise HTTPException(status_code=400, detail=f"Invalid operation. Allowed: {', '.join(valid_ops.keys())}")

    from services.ai_engine import ai_engine
    from services.prompt_templates import render_prompt

    # Map operations to prompt templates
    template_map = {
        "rewrite": "P12_REWRITE", "expand": "P12_REWRITE", "condense": "P12_REWRITE",
        "dialogue_optimize": "P12_REWRITE",
        "visualize": "P14_VISUALIZE", "tone_shift": "P15_TONE_SHIFT",
        "continue_3way": "P16_CONTINUE_3WAY", "scene_detail": "P17_SCENE_DETAIL",
        "subtext": "P18_SUBTEXT", "dialogue_rhythm": "P19_DIALOGUE_RHYTHM",
    }
    template_id = template_map[data.operation]

    # Build render kwargs
    render_kwargs = {
        "text": data.text,
        "context": data.context or "无额外上下文",
    }
    if data.operation in ("rewrite", "expand", "condense", "dialogue_optimize"):
        render_kwargs["operation"] = valid_ops[data.operation]
    if data.operation == "tone_shift":
        render_kwargs["tone"] = data.tone or "紧张/悬疑"

    prompt = render_prompt(template_id, **render_kwargs)

    def event_stream():
        try:
            for chunk in ai_engine.stream(
                system=prompt["system"],
                messages=[{"role": "user", "content": prompt["user"]}],
                capability_tier=prompt["capability_tier"],
                temperature=prompt["temperature"],
                max_tokens=prompt["max_tokens"],
                db=db,
            ):
                yield f"data: {json.dumps({'type': 'text', 'content': chunk}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"AI stream error: {e}")
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


@router.post("/projects/{project_id}/ai/generate-beats")
def generate_beats_from_chapter(
    project_id: str,
    data: GenerateBeatsRequest,
    db: Session = Depends(get_db),
):
    """Generate beats from a chapter using AI."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    chapter = db.query(Chapter).filter(
        Chapter.id == data.chapter_id,
        Chapter.project_id == project_id,
    ).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    from services.novel_parser import generate_beats

    beat_data_list = generate_beats(chapter.content, db=db)

    # Get current max order
    max_order = db.query(Beat).filter(Beat.project_id == project_id).count()

    created_beats = []
    for i, beat_data in enumerate(beat_data_list):
        beat = Beat(
            id=str(uuid4()),
            project_id=project_id,
            chapter_id=chapter.id,
            title=beat_data.get("title", ""),
            description=beat_data.get("description", ""),
            beat_type=beat_data.get("beat_type", "event"),
            emotional_value=float(beat_data.get("emotional_value", 0.0)),
            order=max_order + i,
        )
        db.add(beat)
        created_beats.append(beat)

    db.commit()

    return {
        "beat_count": len(created_beats),
        "beats": [
            {
                "id": b.id,
                "title": b.title,
                "description": b.description,
                "beat_type": b.beat_type,
                "emotional_value": b.emotional_value,
                "order": b.order,
            }
            for b in created_beats
        ],
    }
