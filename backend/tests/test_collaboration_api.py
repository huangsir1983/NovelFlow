from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.collaboration import router, _reset_state_for_tests


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def setup_function():
    _reset_state_for_tests()


def test_comment_anchor_flow():
    client = build_client()

    created = client.post(
        "/api/collaboration/comments",
        json={
            "project_id": "proj-collab",
            "anchor_id": "shot-card:12",
            "body": "Need stronger close-up here.",
            "author": "alice",
            "stage": "board",
        },
    )
    assert created.status_code == 201
    comment_id = created.json()["comment_id"]

    listed = client.get("/api/collaboration/comments", params={"project_id": "proj-collab"})
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = client.patch(
        f"/api/collaboration/comments/{comment_id}",
        json={"resolved": True},
    )
    assert updated.status_code == 200
    assert updated.json()["resolved"] is True


def test_share_and_clone_flow():
    client = build_client()

    share = client.post(
        "/api/collaboration/share/links",
        json={"project_id": "proj-share", "mode": "clone", "permission": "clone"},
    )
    assert share.status_code == 201
    share_id = share.json()["share_id"]

    fetched = client.get(f"/api/collaboration/share/links/{share_id}")
    assert fetched.status_code == 200
    assert fetched.json()["project_id"] == "proj-share"

    cloned = client.post(
        "/api/collaboration/share/clones",
        json={
            "share_id": share_id,
            "target_project_name": "proj-share-copy",
            "operator": "bob",
        },
    )
    assert cloned.status_code == 201
    assert cloned.json()["source_project_id"] == "proj-share"
