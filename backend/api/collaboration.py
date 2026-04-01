"""Collaboration comments/share/clone API skeleton."""

from datetime import datetime, UTC, timedelta
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/collaboration", tags=["collaboration/share"])


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class CommentCreateRequest(BaseModel):
    project_id: str
    anchor_id: str
    body: str
    author: str
    stage: str = "board"


class CommentUpdateRequest(BaseModel):
    body: str | None = None
    resolved: bool | None = None


class CommentResponse(BaseModel):
    comment_id: str
    project_id: str
    anchor_id: str
    body: str
    author: str
    stage: str
    resolved: bool
    created_at: str
    updated_at: str


class ShareCreateRequest(BaseModel):
    project_id: str
    mode: str = "readonly"
    permission: str = "view"
    expires_in_days: int = 7


class ShareResponse(BaseModel):
    share_id: str
    project_id: str
    mode: str
    permission: str
    token: str
    expires_at: str
    created_at: str


class CloneCreateRequest(BaseModel):
    share_id: str
    target_project_name: str
    operator: str


class CloneResponse(BaseModel):
    clone_id: str
    share_id: str
    source_project_id: str
    cloned_project_id: str
    target_project_name: str
    operator: str
    created_at: str


_comments: dict[str, CommentResponse] = {}
_shares: dict[str, ShareResponse] = {}
_clones: dict[str, CloneResponse] = {}


def _reset_state_for_tests() -> None:
    _comments.clear()
    _shares.clear()
    _clones.clear()


@router.post("/comments", response_model=CommentResponse, status_code=201)
def create_comment(data: CommentCreateRequest):
    now = _now_iso()
    comment = CommentResponse(
        comment_id=str(uuid4()),
        project_id=data.project_id,
        anchor_id=data.anchor_id,
        body=data.body,
        author=data.author,
        stage=data.stage,
        resolved=False,
        created_at=now,
        updated_at=now,
    )
    _comments[comment.comment_id] = comment
    return comment


@router.get("/comments", response_model=list[CommentResponse])
def list_comments(project_id: str = Query(...), anchor_id: str | None = Query(default=None)):
    comments = [item for item in _comments.values() if item.project_id == project_id]
    if anchor_id is not None:
        comments = [item for item in comments if item.anchor_id == anchor_id]
    comments.sort(key=lambda item: item.created_at)
    return comments


@router.patch("/comments/{comment_id}", response_model=CommentResponse)
def update_comment(comment_id: str, data: CommentUpdateRequest):
    comment = _comments.get(comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    payload: dict[str, Any] = comment.model_dump()
    if data.body is not None:
        payload["body"] = data.body
    if data.resolved is not None:
        payload["resolved"] = data.resolved
    payload["updated_at"] = _now_iso()

    updated = CommentResponse(**payload)
    _comments[comment_id] = updated
    return updated


@router.post("/share/links", response_model=ShareResponse, status_code=201)
def create_share_link(data: ShareCreateRequest):
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=max(data.expires_in_days, 1))
    share = ShareResponse(
        share_id=str(uuid4()),
        project_id=data.project_id,
        mode=data.mode,
        permission=data.permission,
        token=str(uuid4()),
        expires_at=expires_at.isoformat(),
        created_at=now.isoformat(),
    )
    _shares[share.share_id] = share
    return share


@router.get("/share/links/{share_id}", response_model=ShareResponse)
def get_share_link(share_id: str):
    share = _shares.get(share_id)
    if share is None:
        raise HTTPException(status_code=404, detail="Share link not found")
    return share


@router.post("/share/clones", response_model=CloneResponse, status_code=201)
def create_clone(data: CloneCreateRequest):
    share = _shares.get(data.share_id)
    if share is None:
        raise HTTPException(status_code=404, detail="Share link not found")

    clone = CloneResponse(
        clone_id=str(uuid4()),
        share_id=data.share_id,
        source_project_id=share.project_id,
        cloned_project_id=str(uuid4()),
        target_project_name=data.target_project_name,
        operator=data.operator,
        created_at=_now_iso(),
    )
    _clones[clone.clone_id] = clone
    return clone
