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


class BatchExecuteRequest(BaseModel):
    node_ids: list


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

@router.post("/canvas/nodes/{node_id}/execute")
def execute_node(node_id: str, req: ExecuteNodeRequest):
    """Execute a single canvas node."""
    return {"execution_id": str(uuid.uuid4()), "status": "pending", "message": "Phase 3"}


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
