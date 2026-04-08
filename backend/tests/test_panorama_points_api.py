"""TDD tests for multi-viewpoint panorama API on Location model."""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi import FastAPI
from fastapi.testclient import TestClient
from models.base import Base
from models.project import Project
from models.location import Location

# Import get_db *and* router from same modules the app uses
import database as _db_mod
import api.knowledge as _know_mod

# ---------------------------------------------------------------------------
# Test DB engine — in-memory SQLite
# ---------------------------------------------------------------------------

_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(bind=_test_engine, autoflush=False)


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


def _setup():
    """Create tables, seed data, return TestClient."""
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)

    db = _TestSession()
    db.add(Project(id="proj-1", name="Test"))
    db.add(Location(id="loc-1", project_id="proj-1", name="Grand Hall"))
    db.commit()
    db.close()

    app = FastAPI()
    app.include_router(_know_mod.router, prefix="/api")
    # Override using the exact function object used by Depends()
    app.dependency_overrides[_db_mod.get_db] = _override_get_db
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_list_viewpoints_empty():
    client = _setup()
    resp = client.get("/api/projects/proj-1/locations/loc-1/viewpoints")
    assert resp.status_code == 200
    assert resp.json() == []


def test_add_viewpoint():
    client = _setup()
    resp = client.post(
        "/api/projects/proj-1/locations/loc-1/viewpoints",
        json={"label": "大厅中央", "yaw": 0, "pitch": 0, "fov": 75},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["label"] == "大厅中央"
    assert body["yaw"] == 0
    assert body["pitch"] == 0
    assert body["fov"] == 75
    assert "id" in body


def test_first_viewpoint_becomes_default():
    client = _setup()
    client.post(
        "/api/projects/proj-1/locations/loc-1/viewpoints",
        json={"label": "First"},
    )
    vps = client.get("/api/projects/proj-1/locations/loc-1/viewpoints").json()
    assert len(vps) == 1
    assert vps[0]["is_default"] is True


def test_list_returns_all():
    client = _setup()
    client.post("/api/projects/proj-1/locations/loc-1/viewpoints", json={"label": "A"})
    client.post("/api/projects/proj-1/locations/loc-1/viewpoints", json={"label": "B"})
    client.post("/api/projects/proj-1/locations/loc-1/viewpoints", json={"label": "C"})
    vps = client.get("/api/projects/proj-1/locations/loc-1/viewpoints").json()
    assert len(vps) == 3
    labels = {v["label"] for v in vps}
    assert labels == {"A", "B", "C"}


def test_update_viewpoint():
    client = _setup()
    created = client.post(
        "/api/projects/proj-1/locations/loc-1/viewpoints",
        json={"label": "Old Label", "yaw": 10, "pitch": 5, "fov": 60},
    ).json()
    vp_id = created["id"]

    resp = client.put(
        f"/api/projects/proj-1/locations/loc-1/viewpoints/{vp_id}",
        json={"label": "New Label", "yaw": 90, "fov": 40},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] == "New Label"
    assert body["yaw"] == 90
    assert body["pitch"] == 5
    assert body["fov"] == 40


def test_delete_viewpoint():
    client = _setup()
    created = client.post(
        "/api/projects/proj-1/locations/loc-1/viewpoints",
        json={"label": "ToDelete"},
    ).json()
    vp_id = created["id"]

    resp = client.delete(f"/api/projects/proj-1/locations/loc-1/viewpoints/{vp_id}")
    assert resp.status_code == 204

    vps = client.get("/api/projects/proj-1/locations/loc-1/viewpoints").json()
    assert len(vps) == 0


def test_switch_default():
    client = _setup()
    vp1 = client.post("/api/projects/proj-1/locations/loc-1/viewpoints", json={"label": "A"}).json()
    vp2 = client.post("/api/projects/proj-1/locations/loc-1/viewpoints", json={"label": "B"}).json()

    # First is default
    vps = client.get("/api/projects/proj-1/locations/loc-1/viewpoints").json()
    defaults = [v for v in vps if v["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == vp1["id"]

    # Set B as default
    client.put(
        f"/api/projects/proj-1/locations/loc-1/viewpoints/{vp2['id']}",
        json={"is_default": True},
    )
    vps = client.get("/api/projects/proj-1/locations/loc-1/viewpoints").json()
    defaults = [v for v in vps if v["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == vp2["id"]


def test_location_response_includes_viewpoints():
    client = _setup()
    client.post("/api/projects/proj-1/locations/loc-1/viewpoints", json={"label": "VP1"})
    client.post("/api/projects/proj-1/locations/loc-1/viewpoints", json={"label": "VP2"})

    resp = client.get("/api/projects/proj-1/locations/loc-1")
    assert resp.status_code == 200
    body = resp.json()
    assert "viewpoints" in body
    assert len(body["viewpoints"]) == 2


def test_viewpoint_with_position_and_correction():
    """Create and update viewpoint with camera position + correction strength."""
    client = _setup()
    resp = client.post(
        "/api/projects/proj-1/locations/loc-1/viewpoints",
        json={
            "label": "机位A", "yaw": 45, "pitch": -10, "fov": 60,
            "pos_x": 80.0, "pos_y": 0.0, "pos_z": -50.0,
            "correction_strength": 0.8,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["pos_x"] == 80.0
    assert body["pos_y"] == 0.0
    assert body["pos_z"] == -50.0
    assert body["correction_strength"] == 0.8

    # Update position + correction
    vp_id = body["id"]
    resp2 = client.put(
        f"/api/projects/proj-1/locations/loc-1/viewpoints/{vp_id}",
        json={"pos_x": -30.0, "correction_strength": 0.3},
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["pos_x"] == -30.0
    assert body2["pos_z"] == -50.0  # unchanged
    assert body2["correction_strength"] == 0.3


def test_viewpoint_defaults_for_new_fields():
    """New fields default to appropriate values when not provided."""
    client = _setup()
    resp = client.post(
        "/api/projects/proj-1/locations/loc-1/viewpoints",
        json={"label": "Basic"},
    )
    body = resp.json()
    assert body["pos_x"] == 0.0
    assert body["pos_y"] == 0.0
    assert body["pos_z"] == 0.0
    assert body["correction_strength"] == 0.5
