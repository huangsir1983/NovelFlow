"""Canvas API — CRUD + Agent + Node Execution endpoints for infinite canvas."""

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models.canvas_workflow import CanvasWorkflow, CanvasNodeExecution
from services.ai_engine import ai_engine
from services.prompt_templates import render_prompt

logger = logging.getLogger(__name__)

router = APIRouter(tags=["canvas"])


# ══════════════════════════════════════════════════════════════
# View Angle prompt helper (ported from taoge view_angle_service.py)
# ══════════════════════════════════════════════════════════════

_AZIMUTH_MAP = [
    (0, "front view"), (45, "front-right quarter view"),
    (90, "right side view"), (135, "back-right quarter view"),
    (180, "back view"), (-180, "back view"),
    (-135, "back-left quarter view"), (-90, "left side view"),
    (-45, "front-left quarter view"),
]
_ELEVATION_MAP = [
    (-30, "low-angle shot"), (0, "eye-level shot"),
    (30, "elevated shot"), (60, "high-angle shot"),
]
_DISTANCE_MAP = [(3.3, "close-up"), (6.6, "medium shot"), (10.0, "wide shot")]


def _angle_to_prompt(azimuth: float, elevation: float, distance: float) -> str:
    """Convert numeric angles to <sks> prompt string."""
    # Azimuth: circular nearest
    az_text = "front view"
    min_d = 999.0
    for angle, text in _AZIMUTH_MAP:
        diff = abs(azimuth - angle)
        if diff > 180:
            diff = 360 - diff
        if diff < min_d:
            min_d = diff
            az_text = text
    # Elevation: linear nearest
    el_text = "eye-level shot"
    min_d = 999.0
    for angle, text in _ELEVATION_MAP:
        if abs(elevation - angle) < min_d:
            min_d = abs(elevation - angle)
            el_text = text
    # Distance: threshold
    dist_text = "wide shot"
    for thr, text in _DISTANCE_MAP:
        if distance <= thr:
            dist_text = text
            break
    return f"<sks> {az_text} {el_text} {dist_text}"


# ══════════════════════════════════════════════════════════════
# Request / Response Models
# ══════════════════════════════════════════════════════════════

class CanvasWorkflowResponse(BaseModel):
    id: str
    project_id: str
    name: str
    status: str
    workflow_json: dict
    node_count: int
    version: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SaveCanvasRequest(BaseModel):
    workflow_json: dict = Field(default_factory=dict)
    name: Optional[str] = None


class AnalyzeStoryboardRequest(BaseModel):
    node_id: str
    content: dict
    assets: list = Field(default_factory=list)
    project_id: Optional[str] = None


class AssignModulesRequest(BaseModel):
    scenes: list  # [{sceneId, text, coreEvent, heading, location}]
    project_id: Optional[str] = None


class OptimizePromptRequest(BaseModel):
    type: str  # 'image' | 'video'
    current_prompt: str
    context: dict
    project_id: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    project_context: Optional[str] = ""
    project_id: Optional[str] = None


class ReviewCompositionRequest(BaseModel):
    image_base64: str
    storyboard_text: str
    module_type: str


class ExecuteNodeRequest(BaseModel):
    node_type: str
    content: dict
    project_id: Optional[str] = None


class BatchExecuteRequest(BaseModel):
    node_ids: list


class SaveCompositeLayersRequest(BaseModel):
    layers: list


class SyncFromProjectRequest(BaseModel):
    project_id: str


class SyncToProjectRequest(BaseModel):
    project_id: str
    results: list


# ══════════════════════════════════════════════════════════════
# 1. Canvas CRUD
# ══════════════════════════════════════════════════════════════

@router.get("/projects/{project_id}/canvas")
def get_canvas(project_id: str, db: Session = Depends(get_db)):
    """Get canvas workflow for a project."""
    workflow = db.query(CanvasWorkflow).filter(
        CanvasWorkflow.project_id == project_id
    ).order_by(CanvasWorkflow.created_at.desc()).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Canvas not found for this project")

    return CanvasWorkflowResponse(
        id=workflow.id,
        project_id=workflow.project_id,
        name=workflow.name,
        status=workflow.status,
        workflow_json=workflow.workflow_json or {},
        node_count=workflow.node_count,
        version=workflow.version,
        created_at=str(workflow.created_at) if workflow.created_at else None,
        updated_at=str(workflow.updated_at) if workflow.updated_at else None,
    )


@router.post("/projects/{project_id}/canvas")
def create_canvas(project_id: str, req: SaveCanvasRequest, db: Session = Depends(get_db)):
    """Create a new canvas workflow for a project."""
    workflow = CanvasWorkflow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=req.name or "默认画布",
        status="draft",
        workflow_json=req.workflow_json,
        node_count=len(req.workflow_json.get("nodes", [])),
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    return CanvasWorkflowResponse(
        id=workflow.id, project_id=workflow.project_id,
        name=workflow.name, status=workflow.status,
        workflow_json=workflow.workflow_json or {},
        node_count=workflow.node_count, version=workflow.version,
    )


@router.put("/projects/{project_id}/canvas")
def save_canvas(project_id: str, req: SaveCanvasRequest, db: Session = Depends(get_db)):
    """Save / update canvas workflow."""
    workflow = db.query(CanvasWorkflow).filter(
        CanvasWorkflow.project_id == project_id
    ).order_by(CanvasWorkflow.created_at.desc()).first()

    if not workflow:
        workflow = CanvasWorkflow(
            id=str(uuid.uuid4()), project_id=project_id,
            name=req.name or "默认画布", status="active",
            workflow_json=req.workflow_json,
            node_count=len(req.workflow_json.get("nodes", [])),
        )
        db.add(workflow)
    else:
        workflow.workflow_json = req.workflow_json
        workflow.node_count = len(req.workflow_json.get("nodes", []))
        workflow.version = (workflow.version or 1) + 1
        workflow.status = "active"
        if req.name:
            workflow.name = req.name

    db.commit()
    db.refresh(workflow)

    return CanvasWorkflowResponse(
        id=workflow.id, project_id=workflow.project_id,
        name=workflow.name, status=workflow.status,
        workflow_json=workflow.workflow_json or {},
        node_count=workflow.node_count, version=workflow.version,
    )


@router.delete("/projects/{project_id}/canvas")
def delete_canvas(project_id: str, db: Session = Depends(get_db)):
    """Delete canvas workflow."""
    workflow = db.query(CanvasWorkflow).filter(
        CanvasWorkflow.project_id == project_id
    ).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Canvas not found")
    db.delete(workflow)
    db.commit()
    return {"status": "deleted"}


# ══════════════════════════════════════════════════════════════
# 2. Agent Services — Real AI calls
# ══════════════════════════════════════════════════════════════

@router.post("/canvas/agent/analyze-storyboard")
def analyze_storyboard(req: AnalyzeStoryboardRequest, db: Session = Depends(get_db)):
    """Analyze a scene/storyboard node and generate image/video prompts."""
    scene_text = req.content.get("rawText", "") or req.content.get("coreEvent", "")
    if not scene_text:
        return {"node_id": req.node_id, "error": "No text to analyze"}

    # Build character info string
    char_info = "无角色信息"
    if req.assets:
        char_lines = []
        for a in req.assets:
            if a.get("type") == "character":
                tags = ", ".join(a.get("tags", []))
                char_lines.append(f"- {a.get('name', '未知')}: {a.get('description', '')}，外貌：{tags}")
        if char_lines:
            char_info = "\n".join(char_lines)

    try:
        prompt = render_prompt(
            "P_CANVAS_STORYBOARD_ANALYZE",
            scene_text=scene_text,
            location=req.content.get("location", "未指定"),
            time_of_day=req.content.get("timeOfDay", "日间"),
            emotion=req.content.get("emotion", "待分析"),
            character_info=char_info,
        )

        result = ai_engine.call(
            system=prompt["system"],
            messages=[{"role": "user", "content": prompt["user"]}],
            capability_tier=prompt["capability_tier"],
            temperature=prompt["temperature"],
            max_tokens=prompt["max_tokens"],
            db=db,
            project_id=req.project_id,
            operation_type="canvas_analyze_storyboard",
        )

        # Parse JSON response
        content = result["content"].strip()
        # Remove markdown code block markers if present
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

        parsed = json.loads(content)
        return {
            "node_id": req.node_id,
            "imagePrompt": parsed.get("imagePrompt", ""),
            "videoPrompt": parsed.get("videoPrompt", ""),
            "shotType": parsed.get("shotType", "medium"),
            "emotion": parsed.get("emotion", ""),
            "duration": parsed.get("duration", 5),
            "model": result.get("model", ""),
            "tokens": result.get("input_tokens", 0) + result.get("output_tokens", 0),
        }
    except json.JSONDecodeError:
        logger.warning("Failed to parse AI response as JSON for storyboard analysis")
        return {
            "node_id": req.node_id,
            "imagePrompt": result.get("content", "")[:500] if "result" in dir() else "",
            "videoPrompt": "",
            "shotType": "medium",
            "emotion": req.content.get("emotion", ""),
            "duration": 5,
            "error": "JSON parse failed, raw content returned as imagePrompt",
        }
    except Exception as e:
        logger.error(f"Storyboard analysis failed: {e}")
        return {"node_id": req.node_id, "error": str(e)}


@router.post("/canvas/agent/assign-modules")
def assign_modules(req: AssignModulesRequest, db: Session = Depends(get_db)):
    """Assign workflow module types to scene nodes using AI."""
    if not req.scenes:
        return []

    # Build scenes JSON for the prompt
    scenes_for_prompt = []
    for s in req.scenes:
        text = s.get("coreEvent") or s.get("text") or s.get("heading", "")
        scenes_for_prompt.append({
            "sceneId": s.get("sceneId", ""),
            "core_event": text[:300],
            "heading": s.get("heading", ""),
            "location": s.get("location", ""),
            "narrative_mode": s.get("narrativeMode", "mixed"),
            "emotion_beat": s.get("emotionBeat", ""),
            "dialogue_budget": s.get("dialogueBudget", "medium"),
            "emotional_peak": s.get("emotionalPeak", ""),
            "characters": s.get("characters", []),
        })

    try:
        prompt = render_prompt(
            "P_CANVAS_MODULE_ASSIGN",
            scenes_json=json.dumps(scenes_for_prompt, ensure_ascii=False),
        )

        result = ai_engine.call(
            system=prompt["system"],
            messages=[{"role": "user", "content": prompt["user"]}],
            capability_tier=prompt["capability_tier"],
            temperature=prompt["temperature"],
            max_tokens=prompt["max_tokens"],
            db=db,
            project_id=req.project_id,
            operation_type="canvas_assign_modules",
        )

        content = result["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

        parsed = json.loads(content)
        return parsed
    except json.JSONDecodeError:
        logger.warning("Failed to parse module assignment response")
        # Fallback: return all as dialogue
        return [{"sceneId": s.get("sceneId", ""), "moduleType": "dialogue", "confidence": 0.3}
                for s in req.scenes]
    except Exception as e:
        logger.error(f"Module assignment failed: {e}")
        return [{"sceneId": s.get("sceneId", ""), "moduleType": "dialogue", "confidence": 0.0, "error": str(e)}
                for s in req.scenes]


class RhythmAuditRequest(BaseModel):
    scenes: list  # [{sceneId, tension_score, emotion_beat, hook_type, cliffhanger, reversal_points, sweet_spot, heading}]
    project_id: Optional[str] = None


class ConsistencyCheckRequest(BaseModel):
    characters: list = Field(default_factory=list)
    scenes: list = Field(default_factory=list)
    props: list = Field(default_factory=list)
    locations: list = Field(default_factory=list)
    project_id: Optional[str] = None


@router.post("/canvas/agent/rhythm-audit")
def rhythm_audit(req: RhythmAuditRequest, db: Session = Depends(get_db)):
    """Analyze narrative rhythm across all scenes."""
    if not req.scenes:
        return {"overall_score": 0, "issues": [], "suggestions": []}

    scenes_data = json.dumps(req.scenes, ensure_ascii=False)

    try:
        prompt = render_prompt("P_CANVAS_RHYTHM_AUDIT", scenes_data=scenes_data)
        result = ai_engine.call(
            system=prompt["system"],
            messages=[{"role": "user", "content": prompt["user"]}],
            capability_tier=prompt["capability_tier"],
            temperature=prompt["temperature"],
            max_tokens=prompt["max_tokens"],
            db=db,
            project_id=req.project_id,
            operation_type="canvas_rhythm_audit",
        )

        content = result["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        return json.loads(content.strip())
    except json.JSONDecodeError:
        return {"overall_score": 0, "error": "JSON parse failed", "raw": result.get("content", "")[:500]}
    except Exception as e:
        logger.error(f"Rhythm audit failed: {e}")
        return {"overall_score": 0, "error": str(e)}


@router.post("/canvas/agent/consistency-check")
def consistency_check(req: ConsistencyCheckRequest, db: Session = Depends(get_db)):
    """Check consistency across characters, scenes, props, locations."""
    try:
        prompt = render_prompt(
            "P_CANVAS_CONSISTENCY_CHECK",
            characters_json=json.dumps(req.characters[:20], ensure_ascii=False),  # limit to avoid token overflow
            scenes_json=json.dumps(req.scenes[:30], ensure_ascii=False),
            props_json=json.dumps([p for p in req.props if p.get("is_motif") or p.get("is_major")][:15], ensure_ascii=False),
            locations_json=json.dumps(req.locations[:15], ensure_ascii=False),
        )

        result = ai_engine.call(
            system=prompt["system"],
            messages=[{"role": "user", "content": prompt["user"]}],
            capability_tier=prompt["capability_tier"],
            temperature=prompt["temperature"],
            max_tokens=prompt["max_tokens"],
            db=db,
            project_id=req.project_id,
            operation_type="canvas_consistency_check",
        )

        content = result["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        return json.loads(content.strip())
    except json.JSONDecodeError:
        return {"overall_score": 0, "error": "JSON parse failed", "raw": result.get("content", "")[:500]}
    except Exception as e:
        logger.error(f"Consistency check failed: {e}")
        return {"overall_score": 0, "error": str(e)}


class DialogueOptimizeRequest(BaseModel):
    scene_info: dict
    current_dialogue: list = Field(default_factory=list)
    character_profiles: list = Field(default_factory=list)
    dialogue_budget: str = "medium"
    dialogue_ratio: float = 0.3
    project_id: Optional[str] = None


class ProductionPrecheckRequest(BaseModel):
    scenes: list = Field(default_factory=list)
    characters: list = Field(default_factory=list)
    locations: list = Field(default_factory=list)
    shot_count: int = 0
    project_id: Optional[str] = None


@router.post("/canvas/agent/dialogue-optimize")
def dialogue_optimize(req: DialogueOptimizeRequest, db: Session = Depends(get_db)):
    """Optimize dialogue for a scene, respecting budget and character personality."""
    try:
        prompt = render_prompt(
            "P_CANVAS_DIALOGUE_OPTIMIZE",
            scene_info=json.dumps(req.scene_info, ensure_ascii=False),
            current_dialogue=json.dumps(req.current_dialogue, ensure_ascii=False),
            character_profiles=json.dumps(req.character_profiles[:10], ensure_ascii=False),
            dialogue_budget=req.dialogue_budget,
            dialogue_ratio=str(req.dialogue_ratio),
        )

        result = ai_engine.call(
            system=prompt["system"],
            messages=[{"role": "user", "content": prompt["user"]}],
            capability_tier=prompt["capability_tier"],
            temperature=prompt["temperature"],
            max_tokens=prompt["max_tokens"],
            db=db,
            project_id=req.project_id,
            operation_type="canvas_dialogue_optimize",
        )

        content = result["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        return json.loads(content.strip())
    except json.JSONDecodeError:
        return {"error": "JSON parse failed", "raw": result.get("content", "")[:500]}
    except Exception as e:
        logger.error(f"Dialogue optimize failed: {e}")
        return {"error": str(e)}


@router.post("/canvas/agent/production-precheck")
def production_precheck(req: ProductionPrecheckRequest, db: Session = Depends(get_db)):
    """Pre-flight check before batch image/video generation."""
    # Build readiness summary
    scenes_readiness = []
    for s in req.scenes:
        has_script = bool(s.get("generated_script_json"))
        has_shots = s.get("shot_count", 0) > 0 or has_script
        char_names = s.get("characters_present", [])
        scenes_readiness.append({
            "sceneId": s.get("id", ""),
            "heading": s.get("heading", ""),
            "has_script": has_script,
            "has_shots": has_shots,
            "character_count": len(char_names),
            "estimated_duration_s": s.get("estimated_duration_s"),
        })

    char_assets = []
    for c in req.characters[:20]:
        char_assets.append({
            "name": c.get("name", ""),
            "has_visual_ref": bool(c.get("visual_reference")),
            "has_appearance": bool(c.get("appearance")),
        })

    try:
        prompt = render_prompt(
            "P_CANVAS_PRODUCTION_PRECHECK",
            scene_count=str(len(req.scenes)),
            shot_count=str(req.shot_count),
            character_count=str(len(req.characters)),
            location_count=str(len(req.locations)),
            scenes_readiness=json.dumps(scenes_readiness, ensure_ascii=False),
            character_assets=json.dumps(char_assets, ensure_ascii=False),
        )

        result = ai_engine.call(
            system=prompt["system"],
            messages=[{"role": "user", "content": prompt["user"]}],
            capability_tier=prompt["capability_tier"],
            temperature=prompt["temperature"],
            max_tokens=prompt["max_tokens"],
            db=db,
            project_id=req.project_id,
            operation_type="canvas_production_precheck",
        )

        content = result["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        return json.loads(content.strip())
    except json.JSONDecodeError:
        return {"overall_status": "blocked", "error": "JSON parse failed", "raw": result.get("content", "")[:500]}
    except Exception as e:
        logger.error(f"Production precheck failed: {e}")
        return {"overall_status": "blocked", "error": str(e)}


@router.post("/canvas/agent/optimize-prompt")
def optimize_prompt(req: OptimizePromptRequest, db: Session = Depends(get_db)):
    """Optimize an existing prompt. Returns SSE stream."""
    operation = "优化AI图片提示词" if req.type == "image" else "优化AI视频提示词"

    try:
        prompt = render_prompt(
            "P12_REWRITE",
            text=req.current_prompt,
            operation=operation,
            context=json.dumps(req.context, ensure_ascii=False) if req.context else "",
        )

        def stream_gen():
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
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return StreamingResponse(stream_gen(), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"Prompt optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/canvas/agent/chat")
def canvas_chat(req: ChatRequest, db: Session = Depends(get_db)):
    """General AI chat for canvas assistant. Returns SSE stream."""
    try:
        prompt = render_prompt(
            "P_CANVAS_CHAT",
            project_context=req.project_context or "无额外上下文",
            user_message=req.message,
        )

        def stream_gen():
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
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return StreamingResponse(stream_gen(), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"Canvas chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/canvas/agent/review-composition")
def review_composition(req: ReviewCompositionRequest):
    """Review a generated image composition. (Phase 3 — requires image input)"""
    return {"score": 7.5, "pass": True, "suggestions": ["待实现：需要图片输入"]}


# ══════════════════════════════════════════════════════════════
# 3. Node Execution (stubs — Phase 3)
# ══════════════════════════════════════════════════════════════

_NODE_STORE_WF_ID = "node-execution-store"


def _ensure_node_store_workflow(db: Session) -> str:
    """Ensure a dedicated canvas_workflow row exists for node execution records."""
    existing = db.query(CanvasWorkflow).filter(CanvasWorkflow.id == _NODE_STORE_WF_ID).first()
    if existing:
        return _NODE_STORE_WF_ID
    # Need a valid project_id — grab the first project
    from models.project import Project
    project = db.query(Project).first()
    if not project:
        raise RuntimeError("No project exists — cannot create node store workflow")
    db.add(CanvasWorkflow(
        id=_NODE_STORE_WF_ID,
        project_id=project.id,
        name="Node Execution Store",
        status="active",
    ))
    db.commit()
    return _NODE_STORE_WF_ID


def _persist_node_result(
    db: Session, node_id: str, node_type: str, content: dict, result: dict
):
    """Upsert execution result into canvas_node_executions for later reload."""
    try:
        wf_id = _ensure_node_store_workflow(db)
        existing = db.query(CanvasNodeExecution).filter(
            CanvasNodeExecution.node_id == node_id
        ).first()
        if existing:
            existing.node_type = node_type
            existing.status = "done"
            existing.input_snapshot = content
            existing.output_snapshot = result.get("result", {})
            existing.error_message = None
        else:
            rec = CanvasNodeExecution(
                id=str(uuid.uuid4()),
                workflow_id=wf_id,
                node_id=node_id,
                node_type=node_type,
                status="done",
                input_snapshot=content,
                output_snapshot=result.get("result", {}),
            )
            db.add(rec)
        db.commit()
    except Exception as e:
        logger.warning("Failed to persist node result for %s: %s", node_id, e)
        db.rollback()


@router.post("/canvas/nodes/{node_id}/execute")
def execute_node(node_id: str, req: ExecuteNodeRequest, db: Session = Depends(get_db)):
    """
    Execute a single canvas node based on its type.
    Dispatches to the appropriate service (RunningHub, Gemini, stub, etc.).
    """
    execution_id = str(uuid.uuid4())
    node_type = req.node_type
    content = req.content


    # ── Stub nodes — passthrough input as output ──
    STUB_TYPES = {"lighting", "finalHD"}
    if node_type in STUB_TYPES:
        input_url = content.get("inputImageUrl", "")
        return {
            "execution_id": execution_id,
            "status": "success",
            "node_type": node_type,
            "result": {"outputImageUrl": input_url, "stub": True},
            "message": f"{node_type} is a stub — input passed through",
        }

    # ── SceneBG — panorama viewport screenshot (frontend-driven) ──
    if node_type == "sceneBG":
        screenshot_key = content.get("screenshotStorageKey", "")
        if screenshot_key:
            resp = {
                "execution_id": execution_id,
                "status": "success",
                "node_type": node_type,
                "result": {"outputStorageKey": screenshot_key},
            }
            _persist_node_result(db, node_id, node_type, content, resp)
            return resp
        return {
            "execution_id": execution_id,
            "status": "success",
            "node_type": node_type,
            "result": {"message": "SceneBG screenshot is generated on frontend via Three.js"},
        }

    # ── Pose3D — 3D mannequin pose screenshot (frontend-driven) ──
    if node_type == "pose3D":
        screenshot_key = content.get("screenshotStorageKey", "")
        if screenshot_key:
            resp = {
                "execution_id": execution_id,
                "status": "success",
                "node_type": node_type,
                "result": {"outputStorageKey": screenshot_key},
            }
            _persist_node_result(db, node_id, node_type, content, resp)
            return resp
        return {
            "execution_id": execution_id,
            "status": "success",
            "node_type": node_type,
            "result": {"message": "Pose3D screenshot is generated on frontend via Three.js"},
        }

    # ── CharacterProcess / PropProcess — asset selection (frontend-driven) ──
    if node_type in ("characterProcess", "propProcess"):
        return {
            "execution_id": execution_id,
            "status": "success",
            "node_type": node_type,
            "result": {"message": "Asset selection is done on frontend"},
        }

    # ── ViewAngle / PropAngle — RunningHub view-angle conversion ──
    if node_type in ("viewAngle", "propAngle"):
        from config import settings
        from services.runninghub_client import RunningHubClient, RunningHubError
        from services.storage_adapter import get_storage
        import tempfile

        if not settings.runninghub_api_key:
            raise HTTPException(status_code=503, detail="RunningHub API key not configured")

        source_key = content.get("inputStorageKey", "")
        target_angle = content.get("targetAngle", "")
        azimuth = content.get("azimuth")
        elevation = content.get("elevation")
        distance_val = content.get("distance")
        if not source_key:
            raise HTTPException(status_code=400, detail="inputStorageKey is required")

        storage = get_storage()
        try:
            source_data = storage.get_bytes(object_key=source_key)
        except Exception:
            raise HTTPException(status_code=404, detail=f"Source image not found: {source_key}")

        suffix = ".png" if source_key.endswith(".png") else ".jpg"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            tmp.write(source_data)
            tmp.flush()
            tmp.close()

            client = RunningHubClient(
                api_key=settings.runninghub_api_key,
                base_url=settings.runninghub_base_url,
            )
            download_url = client.upload_image(tmp.name)

            # Build prompt: prefer azimuth/elevation/distance if provided
            if azimuth is not None and elevation is not None and distance_val is not None:
                prompt = _angle_to_prompt(float(azimuth), float(elevation), float(distance_val))
            elif target_angle:
                prompt = target_angle if target_angle.startswith("<sks>") else f"<sks> {target_angle} view eye-level shot medium shot"
            else:
                prompt = "<sks> front view eye-level shot medium shot"
            node_info_list = [
                {"nodeId": "41", "fieldName": "image", "fieldValue": download_url},
                {"nodeId": "137", "fieldName": "text", "fieldValue": prompt},
            ]
            task_id = client.submit_task(
                app_id=settings.runninghub_app_id,
                node_info_list=node_info_list,
                instance_type=settings.runninghub_instance_type,
            )

            result = client.poll_until_done(task_id, poll_interval=3.0, timeout=300.0)
            results = result.get("results", [])
            if not results:
                raise HTTPException(status_code=502, detail="RunningHub returned no results")

            result_url = results[0] if isinstance(results[0], str) else results[0].get("url", "")
            result_data = client._get_binary(result_url)

            # Store result
            from uuid import uuid4 as u4
            ext = "png" if result_url.lower().endswith(".png") else "jpg"
            object_key = f"assets/images/{u4()}.{ext}"
            storage.put_bytes(object_key=object_key, data=result_data, content_type=f"image/{ext}")

            resp = {
                "execution_id": execution_id,
                "status": "success",
                "node_type": node_type,
                "result": {"outputStorageKey": object_key, "runninghubTaskId": task_id},
            }
            _persist_node_result(db, node_id, node_type, content, resp)
            return resp
        finally:
            import os
            os.unlink(tmp.name)

    # ── Expression — Gemini img2img ──
    if node_type == "expression":
        import base64
        from services.expression_service import generate_expression

        ref_base64 = content.get("referenceImageBase64", "")
        expr_prompt = content.get("expressionPrompt", "")

        # Helper: read image from storageKey or URL → base64
        def _resolve_image_base64(storage_key: str = "", image_url: str = "") -> str:
            b64 = ""
            if storage_key:
                try:
                    from services.storage_adapter import get_storage
                    storage = get_storage()
                    source_data = storage.get_bytes(object_key=storage_key)
                    b64 = base64.b64encode(source_data).decode("utf-8")
                except Exception as e:
                    logger.warning("Failed to read image from storage %s: %s", storage_key, e)
            if not b64 and image_url:
                try:
                    import httpx as _httpx
                    _client = _httpx.Client(timeout=30)
                    img_resp = _client.get(image_url)
                    img_resp.raise_for_status()
                    b64 = base64.b64encode(img_resp.content).decode("utf-8")
                except Exception as e:
                    logger.warning("Failed to download image from URL %s: %s", image_url, e)
            return b64

        # Resolve primary reference image (backward compatible)
        if not ref_base64:
            ref_base64 = _resolve_image_base64(
                content.get("inputStorageKey", ""),
                content.get("inputImageUrl", ""),
            )

        # Resolve extra reference images from referenceImages array
        extra_images: list[dict] = []
        ref_images_raw = content.get("referenceImages", [])
        if isinstance(ref_images_raw, list):
            for ref_item in ref_images_raw:
                idx = ref_item.get("index", 0)
                sk = ref_item.get("storageKey", "")
                url = ref_item.get("url", "")
                img_b64 = _resolve_image_base64(sk, url)
                if img_b64:
                    extra_images.append({"index": idx, "base64": img_b64})

        # If extra_images includes index 1, use it as primary ref_base64
        if extra_images and not ref_base64:
            for ei in extra_images:
                if ei["index"] == 1:
                    ref_base64 = ei["base64"]
                    break
            if not ref_base64:
                ref_base64 = extra_images[0]["base64"]

        # Remove primary from extra_images (avoid duplication)
        extra_images = [ei for ei in extra_images if ei.get("index", 0) != 1]

        logger.info(
            "Expression handler: ref_base64=%s, extra_images=%d, prompt=%s",
            bool(ref_base64), len(extra_images), expr_prompt[:80],
        )

        if not ref_base64 or not expr_prompt:
            raise HTTPException(status_code=400, detail="referenceImageBase64/inputStorageKey and expressionPrompt are required")

        try:
            result_b64 = generate_expression(
                reference_image_base64=ref_base64,
                expression_prompt=expr_prompt,
                extra_images=extra_images if extra_images else None,
                negative_prompt=content.get("negativePrompt"),
                character_name=content.get("characterName"),
                db=db,
            )
            # Save expression result as file so it can be reloaded
            from services.storage_adapter import get_storage as _get_storage
            from uuid import uuid4 as _u4
            _storage = _get_storage()
            _img_data = base64.b64decode(result_b64)
            _obj_key = f"assets/images/{_u4()}.png"
            _storage.put_bytes(object_key=_obj_key, data=_img_data, content_type="image/png")

            resp = {
                "execution_id": execution_id,
                "status": "success",
                "node_type": node_type,
                "result": {"outputImageBase64": result_b64, "outputStorageKey": _obj_key},
            }
            _persist_node_result(db, node_id, node_type, content, resp)
            return resp
        except Exception as e:
            import traceback
            logger.error("Expression generation failed: %s\n%s", e, traceback.format_exc())
            raise HTTPException(status_code=502, detail=str(e))

    # ── Matting — RunningHub background removal ──
    if node_type == "matting":
        from config import settings
        from services.runninghub_client import RunningHubClient
        from services.matting_service import run_matting
        from services.storage_adapter import get_storage
        import tempfile

        if not settings.runninghub_api_key:
            raise HTTPException(status_code=503, detail="RunningHub API key not configured")

        source_key = content.get("inputStorageKey", "")
        if not source_key:
            raise HTTPException(status_code=400, detail="inputStorageKey is required")

        storage = get_storage()
        try:
            source_data = storage.get_bytes(object_key=source_key)
        except Exception:
            raise HTTPException(status_code=404, detail=f"Source image not found: {source_key}")

        suffix = ".png" if source_key.endswith(".png") else ".jpg"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            tmp.write(source_data)
            tmp.flush()
            tmp.close()

            client = RunningHubClient(
                api_key=settings.runninghub_api_key,
                base_url=settings.runninghub_base_url,
            )
            result_bytes = run_matting(client, tmp.name, instance_type=settings.runninghub_instance_type)

            # Store result as PNG
            from uuid import uuid4 as u4
            object_key = f"assets/images/{u4()}.png"
            storage.put_bytes(object_key=object_key, data=result_bytes, content_type="image/png")

            resp = {
                "execution_id": execution_id,
                "status": "success",
                "node_type": node_type,
                "result": {"outputStorageKey": object_key},
            }
            _persist_node_result(db, node_id, node_type, content, resp)
            return resp
        finally:
            import os
            os.unlink(tmp.name)

    # ── HD Upscale — RunningHub image upscaling ──
    if node_type == "hdUpscale":
        from config import settings
        from services.runninghub_client import RunningHubClient
        from services.hd_upscale_service import run_hd_upscale
        from services.storage_adapter import get_storage
        import tempfile

        if not settings.runninghub_api_key:
            raise HTTPException(status_code=503, detail="RunningHub API key not configured")

        # Get source image from storage or URL
        source_data = None
        source_key = content.get("inputStorageKey", "")
        if source_key:
            try:
                storage = get_storage()
                source_data = storage.get_bytes(object_key=source_key)
            except Exception:
                logger.warning("HD Upscale: failed to read from storage key %s", source_key)

        if not source_data:
            input_url = content.get("inputImageUrl", "")
            if input_url:
                try:
                    import httpx as _httpx
                    _client = _httpx.Client(timeout=30)
                    img_resp = _client.get(input_url)
                    img_resp.raise_for_status()
                    source_data = img_resp.content
                except Exception as e:
                    logger.warning("HD Upscale: failed to download from URL %s: %s", input_url, e)

        if not source_data:
            raise HTTPException(status_code=400, detail="inputStorageKey or inputImageUrl is required")

        suffix = ".png" if (source_key or "").endswith(".png") else ".jpg"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            tmp.write(source_data)
            tmp.flush()
            tmp.close()

            client = RunningHubClient(
                api_key=settings.runninghub_api_key,
                base_url=settings.runninghub_base_url,
            )
            image_size = content.get("imageSize", "2K")
            result_bytes = run_hd_upscale(
                client, tmp.name,
                image_size=image_size,
                instance_type=settings.runninghub_instance_type,
            )

            # Store result
            storage = get_storage()
            from uuid import uuid4 as u4
            object_key = f"assets/images/{u4()}.png"
            storage.put_bytes(object_key=object_key, data=result_bytes, content_type="image/png")

            resp = {
                "execution_id": execution_id,
                "status": "success",
                "node_type": node_type,
                "result": {"outputStorageKey": object_key},
            }
            _persist_node_result(db, node_id, node_type, content, resp)
            return resp
        except Exception as e:
            import traceback
            logger.error("HD Upscale failed: %s\n%s", e, traceback.format_exc())
            raise HTTPException(status_code=502, detail=str(e))
        finally:
            import os
            os.unlink(tmp.name)

    # ── Composite — receive composite image from frontend editor ──
    if node_type == "composite":
        # Case 1: frontend sends outputStorageKey (already uploaded)
        output_storage_key = content.get("outputStorageKey", "")
        if output_storage_key:
            resp = {
                "execution_id": execution_id,
                "status": "success",
                "node_type": node_type,
                "result": {"outputStorageKey": output_storage_key},
            }
            _persist_node_result(db, node_id, node_type, content, resp)
            return resp

        # Case 2: frontend sends base64 image data
        image_base64 = content.get("compositeImageBase64", "")
        if not image_base64:
            return {
                "execution_id": execution_id,
                "status": "success",
                "node_type": node_type,
                "result": {"message": "Composite editing is done on frontend"},
            }

        from services.storage_adapter import get_storage
        from uuid import uuid4 as u4
        import base64 as b64

        storage = get_storage()
        img_data = b64.b64decode(image_base64)
        object_key = f"assets/images/{u4()}.png"
        storage.put_bytes(object_key=object_key, data=img_data, content_type="image/png")

        resp = {
            "execution_id": execution_id,
            "status": "success",
            "node_type": node_type,
            "result": {"outputStorageKey": object_key},
        }
        _persist_node_result(db, node_id, node_type, content, resp)
        return resp

    # ── BlendRefine — RunningHub image blending / fusion ──
    if node_type == "blendRefine":
        from config import settings
        from services.runninghub_client import RunningHubClient, RunningHubError
        from services.storage_adapter import get_storage
        import tempfile

        BLEND_APP_ID = "2027426419357261825"

        if not settings.runninghub_api_key:
            raise HTTPException(status_code=503, detail="RunningHub API key not configured")

        source_key = content.get("inputStorageKey", "")
        if not source_key:
            raise HTTPException(status_code=400, detail="inputStorageKey is required for blendRefine")

        storage = get_storage()
        try:
            source_data = storage.get_bytes(object_key=source_key)
        except Exception:
            raise HTTPException(status_code=404, detail=f"Source image not found: {source_key}")

        suffix = ".png" if source_key.endswith(".png") else ".jpg"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            tmp.write(source_data)
            tmp.flush()
            tmp.close()

            client = RunningHubClient(
                api_key=settings.runninghub_api_key,
                base_url=settings.runninghub_base_url,
            )
            download_url = client.upload_image(tmp.name)

            node_info_list = [
                {"nodeId": "41", "fieldName": "image", "fieldValue": download_url, "description": "图像输入"},
            ]
            task_id = client.submit_task(
                app_id=BLEND_APP_ID,
                node_info_list=node_info_list,
                instance_type=settings.runninghub_instance_type,
            )

            result = client.poll_until_done(task_id, poll_interval=3.0, timeout=300.0)
            results = result.get("results", [])
            if not results:
                raise HTTPException(status_code=502, detail="RunningHub blendRefine returned no results")

            result_url = results[0] if isinstance(results[0], str) else results[0].get("url", "")
            result_data = client._get_binary(result_url)

            from uuid import uuid4 as u4
            ext = "png" if result_url.lower().endswith(".png") else "jpg"
            object_key = f"assets/images/{u4()}.{ext}"
            storage.put_bytes(object_key=object_key, data=result_data, content_type=f"image/{ext}")

            resp = {
                "execution_id": execution_id,
                "status": "success",
                "node_type": node_type,
                "result": {"outputStorageKey": object_key, "runninghubTaskId": task_id},
            }
            _persist_node_result(db, node_id, node_type, content, resp)
            return resp
        except RunningHubError as e:
            raise HTTPException(status_code=502, detail=f"RunningHub blendRefine error: {e}")
        finally:
            import os
            os.unlink(tmp.name)

    # ── Unified ImageProcess — dispatches based on processType ──
    if node_type == "imageProcess":
        process_type = content.get("processType", "")
        if process_type in ("viewAngle", "propAngle"):
            # Re-dispatch to viewAngle handler
            req.node_type = "viewAngle"
            return execute_node(node_id, req, db)
        elif process_type == "expression":
            req.node_type = "expression"
            return execute_node(node_id, req, db)
        elif process_type == "matting":
            req.node_type = "matting"
            return execute_node(node_id, req, db)
        elif process_type == "hdUpscale":
            req.node_type = "hdUpscale"
            return execute_node(node_id, req, db)
        else:
            return {
                "execution_id": execution_id,
                "status": "error",
                "node_type": "imageProcess",
                "message": f"Unknown processType: {process_type}",
            }

    # ── Unknown node type ──
    return {
        "execution_id": execution_id,
        "status": "error",
        "node_type": node_type,
        "message": f"Unknown node type: {node_type}",
    }


@router.get("/canvas/node-results")
def get_node_results(db: Session = Depends(get_db)):
    """Return all persisted node execution results for canvas reload."""
    rows = db.query(CanvasNodeExecution).filter(
        CanvasNodeExecution.status == "done"
    ).all()
    result = {}
    for r in rows:
        result[r.node_id] = {
            "node_type": r.node_type,
            "input_snapshot": r.input_snapshot or {},
            "output_snapshot": r.output_snapshot or {},
        }
    return result


@router.post("/canvas/composite-layers/{node_id}")
def save_composite_layers(node_id: str, req: SaveCompositeLayersRequest, db: Session = Depends(get_db)):
    """Persist composite layer configuration (positions, sizes, rotations, etc.)."""
    try:
        wf_id = _ensure_node_store_workflow(db)
        existing = db.query(CanvasNodeExecution).filter(
            CanvasNodeExecution.node_id == node_id,
            CanvasNodeExecution.node_type == "compositeLayers",
        ).first()
        if existing:
            existing.output_snapshot = {"layers": req.layers}
            existing.status = "done"
        else:
            rec = CanvasNodeExecution(
                id=str(uuid.uuid4()),
                workflow_id=wf_id,
                node_id=node_id,
                node_type="compositeLayers",
                status="done",
                input_snapshot={},
                output_snapshot={"layers": req.layers},
            )
            db.add(rec)
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        db.rollback()
        logger.warning("Failed to save composite layers for %s: %s", node_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/canvas/composite-layers")
def get_composite_layers(db: Session = Depends(get_db)):
    """Return all saved composite layer configurations."""
    rows = db.query(CanvasNodeExecution).filter(
        CanvasNodeExecution.node_type == "compositeLayers",
        CanvasNodeExecution.status == "done",
    ).all()
    result = {}
    for r in rows:
        output = r.output_snapshot or {}
        layers = output.get("layers", [])
        if layers:
            result[r.node_id] = layers
    return result


@router.post("/canvas/batch-execute")
def batch_execute(req: BatchExecuteRequest):
    """Batch execute multiple canvas nodes."""
    return {"status": "queued", "node_count": len(req.node_ids)}


@router.get("/canvas/nodes/{node_id}/status")
def get_node_status(node_id: str):
    """Get execution status of a canvas node."""
    return {"node_id": node_id, "status": "idle"}


# ══════════════════════════════════════════════════════════════
# 4. Data Sync
# ══════════════════════════════════════════════════════════════

@router.post("/canvas/sync/from-project")
def sync_from_project(req: SyncFromProjectRequest):
    """Load project data into canvas format."""
    return {"status": "ok", "message": "Use frontend adapter for conversion"}


@router.post("/canvas/sync/to-project")
def sync_to_project(req: SyncToProjectRequest):
    """Write back canvas results to project."""
    return {"status": "ok", "updated_count": len(req.results)}


# ══════════════════════════════════════════════════════════════
# 5. AI Merge Analysis (分镜合并分析)
# ══════════════════════════════════════════════════════════════

class MergeAnalysisRequest(BaseModel):
    scene_id: str
    storyboard_nodes: list  # [{id, label, text, emotion, shotType, estimatedDuration}]
    project_id: Optional[str] = None


@router.post("/canvas/agent/merge-analysis")
def merge_analysis(req: MergeAnalysisRequest, db: Session = Depends(get_db)):
    """AI-powered storyboard merge analysis for video generation optimization."""
    if not req.storyboard_nodes:
        return {"decisions": [], "summary": "无分镜", "totalVideos": 0, "totalDuration": 0}

    try:
        prompt = render_prompt(
            "P_CANVAS_MERGE_ANALYSIS",
            scene_id=req.scene_id,
            storyboard_count=str(len(req.storyboard_nodes)),
            total_duration=str(sum(s.get("estimatedDuration", 5) for s in req.storyboard_nodes)),
            storyboards_json=json.dumps(req.storyboard_nodes, ensure_ascii=False),
        )

        result = ai_engine.call(
            system=prompt["system"],
            messages=[{"role": "user", "content": prompt["user"]}],
            capability_tier=prompt["capability_tier"],
            temperature=prompt["temperature"],
            max_tokens=prompt["max_tokens"],
            db=db,
            project_id=req.project_id,
            operation_type="canvas_merge_analysis",
        )

        content = result["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        return json.loads(content.strip())
    except json.JSONDecodeError:
        logger.warning("Failed to parse merge analysis response")
        # Fallback: each storyboard becomes one video
        return {
            "decisions": [
                {
                    "groupId": f"g{i+1}",
                    "shotNodeIds": [s["id"]],
                    "totalDuration": s.get("estimatedDuration", 5),
                    "videoCount": 1,
                    "reason": "默认独立成片",
                    "driftRisk": "low" if s.get("estimatedDuration", 5) <= 8 else "medium",
                    "recommendedProvider": "jimeng",
                }
                for i, s in enumerate(req.storyboard_nodes)
            ],
            "summary": f"{len(req.storyboard_nodes)} 个分镜独立成片",
            "totalVideos": len(req.storyboard_nodes),
            "totalDuration": sum(s.get("estimatedDuration", 5) for s in req.storyboard_nodes),
        }
    except Exception as e:
        logger.error(f"Merge analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
