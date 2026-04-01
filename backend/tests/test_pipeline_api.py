from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.pipeline import router, _reset_state_for_tests


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def setup_function():
    _reset_state_for_tests()


def test_pipeline_run_lifecycle():
    client = build_client()

    created = client.post(
        "/api/workflow/pipeline/runs",
        json={"project_id": "proj-alpha", "workflow_id": "shot-v1"},
    )
    assert created.status_code == 201
    run_id = created.json()["run_id"]

    node = client.post(
        f"/api/workflow/pipeline/runs/{run_id}/nodes/shot_generation",
        json={"input_payload": {"scene_count": 3}},
    )
    assert node.status_code == 200
    assert node.json()["status"] == "succeeded"

    run = client.get(f"/api/workflow/pipeline/runs/{run_id}")
    assert run.status_code == 200
    assert run.json()["status"] == "succeeded"
    assert run.json()["node_count"] == 1

    logs = client.get(f"/api/workflow/pipeline/runs/{run_id}/logs")
    assert logs.status_code == 200
    assert logs.json()["total"] >= 2


def test_pipeline_recovery_after_failure():
    client = build_client()

    created = client.post("/api/workflow/pipeline/runs", json={"project_id": "proj-beta"})
    run_id = created.json()["run_id"]

    failed = client.post(
        f"/api/workflow/pipeline/runs/{run_id}/nodes/render",
        json={"simulate_failure": True},
    )
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"

    recovered = client.post(
        f"/api/workflow/pipeline/runs/{run_id}/recover",
        json={"strategy": "resume_failed_nodes"},
    )
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "running"
