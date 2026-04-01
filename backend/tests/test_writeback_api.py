from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.artifacts_writeback import router, _reset_state_for_tests


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def setup_function():
    _reset_state_for_tests()


def test_preview_confirm_and_list_versions():
    client = build_client()

    preview = client.post(
        "/api/artifacts/writeback/preview",
        json={
            "project_id": "proj-writeback",
            "artifact_id": "artifact-1",
            "target": "workbench.scene:scene-1",
            "content": "updated content",
        },
    )
    assert preview.status_code == 201
    preview_id = preview.json()["preview_id"]

    decision = client.post(
        "/api/artifacts/writeback/confirm",
        json={"preview_id": preview_id, "operator": "tester"},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "confirmed"
    assert decision.json()["version_id"] is not None

    versions = client.get("/api/artifacts/writeback/projects/proj-writeback/versions")
    assert versions.status_code == 200
    assert versions.json()["total"] == 1


def test_reject_writeback_preview():
    client = build_client()

    preview = client.post(
        "/api/artifacts/writeback/preview",
        json={
            "project_id": "proj-reject",
            "artifact_id": "artifact-2",
            "target": "board.shot:shot-9",
            "content": "pending changes",
        },
    )
    preview_id = preview.json()["preview_id"]

    rejected = client.post(
        "/api/artifacts/writeback/reject",
        json={"preview_id": preview_id, "operator": "reviewer"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
