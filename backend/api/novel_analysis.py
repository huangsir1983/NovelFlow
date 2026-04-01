"""Novel analysis API — AI-powered novel analysis and scene extraction.

Endpoints:
  POST /projects/{id}/analysis/stream       — streaming AI analysis
  GET  /projects/{id}/import/full-text      — get novel text + existing analysis
  POST /projects/{id}/analysis/start-scenes — start scenes-only pipeline
"""

import json
import logging
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, SessionLocal, commit_with_retry
from models.project import Project
from models.import_task import ImportTask
from services.ai_engine import ai_engine
from services.prompt_templates import render_prompt

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


# --- Schemas ---

class AnalysisRequest(BaseModel):
    adaptation_direction: str = "oscar_film"
    novel_text: str = ""


class FullTextResponse(BaseModel):
    full_text: str | None = None
    novel_analysis: str | None = None
    novel_analysis_json: dict | None = None


class StartScenesRequest(BaseModel):
    novel_text: str = ""


class StartScenesResponse(BaseModel):
    task_id: str
    status: str


# --- Routes ---

@router.post("/projects/{project_id}/analysis/stream")
def stream_analysis(
    project_id: str,
    data: AnalysisRequest,
    db: Session = Depends(get_db),
):
    """Stream AI analysis of the novel text.

    Novel text is sent directly from the frontend (browser memory).
    No DB read required — the text comes in the request body.
    """
    # Use novel_text from request body; fall back to DB if empty (backward compat)
    novel_text = data.novel_text.strip() if data.novel_text else ""

    if not novel_text:
        # Fallback: try reading from DB (legacy path)
        task = (
            db.query(ImportTask)
            .filter(ImportTask.project_id == project_id, ImportTask.full_text.isnot(None))
            .order_by(ImportTask.created_at.desc())
            .first()
        )
        if task and task.full_text:
            novel_text = task.full_text

    if not novel_text:
        raise HTTPException(status_code=400, detail="No novel text provided. Please upload a novel first.")

    prompt = render_prompt(
        "P_NOVEL_ANALYSIS",
        novel_text=novel_text[:150000],
        adaptation_direction=data.adaptation_direction,
    )

    def event_stream():
        full_response = []
        structured_data = None
        stream_db = SessionLocal()
        try:
            for chunk in ai_engine.stream(
                system=prompt["system"],
                messages=[{"role": "user", "content": prompt["user"]}],
                capability_tier=prompt["capability_tier"],
                temperature=prompt["temperature"],
                max_tokens=prompt["max_tokens"],
                db=stream_db,
            ):
                full_response.append(chunk)
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"

            # Save analysis result to DB
            final_text = "".join(full_response)
            if final_text.strip():
                try:
                    # Parse the structured JSON output
                    report_text = final_text  # fallback: keep raw text

                    # Strip markdown code block wrapper if present
                    cleaned = final_text.strip()
                    md_match = re.match(r'^```(?:json)?\s*\n?(.*?)\n?\s*```$', cleaned, re.DOTALL)
                    if md_match:
                        cleaned = md_match.group(1).strip()

                    try:
                        parsed = json.loads(cleaned)
                        if isinstance(parsed, dict) and "structured" in parsed and "report" in parsed:
                            structured_data = parsed["structured"]
                            # Build human-readable report from report sections
                            report = parsed["report"]
                            section_titles = {
                                "ip_value": "一、IP核心价值评估",
                                "character_system": "二、人物体系分析",
                                "world_and_scenes": "三、场景与世界观",
                                "pacing_and_adaptation": "四、叙事节奏与改编策略",
                                "market_positioning": "五、市场定位与受众",
                                "risk_assessment": "六、风险评估与建议",
                            }
                            report_parts = []
                            for key, title in section_titles.items():
                                content = report.get(key, "")
                                if content:
                                    report_parts.append(f"## {title}\n\n{content}")
                            if report_parts:
                                report_text = "\n\n".join(report_parts)
                            logger.info("Novel analysis JSON parsed successfully, structured keys: %s",
                                       list(structured_data.keys()) if structured_data else "none")
                    except (json.JSONDecodeError, KeyError, TypeError) as parse_err:
                        logger.warning(f"Novel analysis JSON parse failed, storing as raw text: {parse_err}")
                        # Keep report_text as raw final_text, structured_data stays None

                    save_db = SessionLocal()
                    task = (
                        save_db.query(ImportTask)
                        .filter(ImportTask.project_id == project_id)
                        .order_by(ImportTask.created_at.desc())
                        .first()
                    )
                    if task:
                        task.novel_analysis = report_text
                        task.novel_analysis_json = structured_data
                        if not task.full_text and novel_text:
                            task.full_text = novel_text
                    else:
                        # No ImportTask yet — create one to persist analysis
                        task = ImportTask(
                            id=str(uuid4()),
                            project_id=project_id,
                            status="done",
                            current_phase="analysis",
                            progress={},
                            full_text=novel_text,
                            novel_analysis=report_text,
                            novel_analysis_json=structured_data,
                        )
                        save_db.add(task)
                    commit_with_retry(save_db)
                    save_db.close()
                except Exception as save_err:
                    logger.error(f"Failed to save analysis: {save_err}")

            yield f"data: {json.dumps({'type': 'done', 'structured': structured_data}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Analysis stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            stream_db.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/projects/{project_id}/import/full-text", response_model=FullTextResponse)
def get_full_text(
    project_id: str,
    db: Session = Depends(get_db),
):
    """Get the novel full text and existing analysis."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task = (
        db.query(ImportTask)
        .filter(ImportTask.project_id == project_id)
        .order_by(ImportTask.created_at.desc())
        .first()
    )

    return FullTextResponse(
        full_text=task.full_text if task else None,
        novel_analysis=task.novel_analysis if task else None,
        novel_analysis_json=task.novel_analysis_json if task else None,
    )


@router.post("/projects/{project_id}/analysis/start-scenes", response_model=StartScenesResponse)
def start_scenes_extraction(
    project_id: str,
    data: StartScenesRequest,
    db: Session = Depends(get_db),
):
    """Start scenes-only extraction pipeline.

    Novel text comes from the frontend (browser memory).
    Falls back to DB if not provided.
    """
    # Use novel_text from request body; fall back to DB if empty
    novel_text = data.novel_text.strip() if data.novel_text else ""

    if not novel_text:
        existing_task = (
            db.query(ImportTask)
            .filter(ImportTask.project_id == project_id, ImportTask.full_text.isnot(None))
            .order_by(ImportTask.created_at.desc())
            .first()
        )
        if existing_task and existing_task.full_text:
            novel_text = existing_task.full_text

    if not novel_text:
        raise HTTPException(status_code=400, detail="No novel text provided. Please upload a novel first.")

    # Create new task for scenes-only pipeline
    # Carry over novel_analysis from the previous task so it survives reload
    prev_task = (
        db.query(ImportTask)
        .filter(ImportTask.project_id == project_id, ImportTask.novel_analysis.isnot(None))
        .order_by(ImportTask.created_at.desc())
        .first()
    )
    task_id = str(uuid4())
    task = ImportTask(
        id=task_id,
        project_id=project_id,
        status="pending",
        current_phase="streaming",
        progress={},
        full_text=novel_text,
        novel_analysis=prev_task.novel_analysis if prev_task else None,
        novel_analysis_json=prev_task.novel_analysis_json if prev_task else None,
    )
    db.add(task)

    # Mark project stage so page-load reconnection works
    project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        project.stage = "import"

    commit_with_retry(db)

    # Submit scenes-only pipeline using the import module's executor
    from api.import_novel import _submit_pipeline_with_mode
    import os
    _dbg = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_pipeline.log")
    with open(_dbg, "a", encoding="utf-8") as f:
        f.write(f"SUBMIT_CALL: task={task_id} project={project_id} text_len={len(novel_text)}\n")

    _submit_pipeline_with_mode(task_id, project_id, novel_text, mode="scenes_only")

    with open(_dbg, "a", encoding="utf-8") as f:
        f.write(f"SUBMIT_DONE: task={task_id}\n")

    return StartScenesResponse(task_id=task_id, status="pending")
