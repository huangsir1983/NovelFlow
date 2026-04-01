from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.preview_export import router, _reset_state_for_tests


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def setup_function():
    _reset_state_for_tests()


def test_capcut_export_and_mapping():
    client = build_client()

    exported = client.post(
        "/api/preview/export/projects/proj-preview/capcut-draft",
        json={"quality": "standard", "include_subtitles": True, "include_tts": True},
    )
    assert exported.status_code == 201
    payload = exported.json()
    assert payload["format"] == "capcut_draft"

    mapping = client.get(
        f"/api/preview/export/projects/proj-preview/versions/{payload['version_id']}/mapping",
    )
    assert mapping.status_code == 200
    assert mapping.json()["mapping_status"] == "ready"
