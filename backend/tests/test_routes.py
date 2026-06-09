import io
from unittest.mock import MagicMock, patch

import pytest

SIMPLE_ENDPOINTS = [
    ("POST", "/api/v1/factory/seed-employees", None),
    ("POST", "/api/v1/factory/seed-projects", None),
    ("POST", "/api/v1/factory/seed-technologies", None),
    ("POST", "/api/v1/factory/seed-all", None),
    ("DELETE", "/api/v1/factory/reset-db", None),
]

PROJECT_ENDPOINTS = [
    ("GET", "tbds", None),
    ("POST", "clarifications", {"tbd_id": "t1", "action": "TBD"}),
    ("POST", "proposal", None),
    ("GET", "proposal", None),
    ("POST", "stack", None),
    ("POST", "estimate", None),
    ("POST", "sync", None),
    ("GET", "metrics", None),
]


@pytest.mark.parametrize("method,path,body", SIMPLE_ENDPOINTS)
def test_simple_endpoint_returns_2xx(client, method, path, body):
    kwargs = {"json": body} if body is not None else {}
    resp = getattr(client, method.lower())(path, **kwargs)
    assert resp.status_code < 300, f"{method} {path} → {resp.status_code}: {resp.text}"


@pytest.mark.parametrize("sub,body", [(s, b) for _, s, b in PROJECT_ENDPOINTS])
def test_project_endpoint_returns_2xx(client, project_id, sub, body):
    method = "post" if sub in {"clarifications", "proposal", "stack", "estimate", "sync"} else "get"
    path = f"/api/v1/projects/{project_id}/{sub}"
    kwargs = {"json": body} if body is not None else {}
    resp = getattr(client, method)(path, **kwargs)
    assert resp.status_code < 300, f"{method.upper()} {path} → {resp.status_code}: {resp.text}"


def test_create_project(client):
    resp = client.post("/api/v1/projects", json={"name": "My Project"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Project"
    assert "id" in data
    assert data["current_phase"] == 1


def test_upload_document(client):
    mock_db = MagicMock()
    mock_doc = MagicMock()
    mock_doc.id = 1
    mock_doc.filename = "test.pdf"
    mock_doc.status = MagicMock()
    mock_doc.status.value = "uploaded"
    mock_doc.upload_ts = "2026-01-01T00:00:00"
    mock_db.refresh.side_effect = lambda obj: None

    from app.database import get_db
    from app.main import app

    def mock_get_db():
        return mock_db

    app.dependency_overrides[get_db] = mock_get_db

    data = io.BytesIO(b"fake pdf content")
    with patch("app.routers.projects.Document") as MockDocument, \
         patch("app.routers.projects.ingest_document"):
        MockDocument.return_value = mock_doc
        resp = client.post(
            "/api/v1/projects/1/documents",
            files={"file": ("test.pdf", data, "application/pdf")},
        )

    app.dependency_overrides[get_db] = lambda: None
    assert resp.status_code < 300


def test_sync_response_has_status(client, project_id):
    resp = client.post(f"/api/v1/projects/{project_id}/sync")
    assert "status" in resp.json()


def test_factory_reset_returns_status(client):
    resp = client.delete("/api/v1/factory/reset-db")
    assert resp.json()["status"] == "reset"


import json as _json


def test_get_stack_returns_204_when_not_generated(client, project_id, db_session):
    from app.models.project import Project
    project = db_session.query(Project).first()
    project.tech_stack = None
    db_session.commit()
    resp = client.get(f"/api/v1/projects/{project_id}/stack")
    assert resp.status_code == 204


def test_get_stack_returns_200_with_cached_data(client, project_id, db_session):
    from app.models.project import Project
    project = db_session.query(Project).first()
    project.tech_stack = {
        "frontend": ["Next.js"],
        "backend": ["FastAPI"],
        "database": ["SQLite"],
        "infra": ["Railway"],
        "rationale": "solid defaults",
    }
    db_session.commit()
    resp = client.get(f"/api/v1/projects/{project_id}/stack")
    assert resp.status_code == 200
    data = resp.json()
    assert data["frontend"] == ["Next.js"]
    assert data["rationale"] == "solid defaults"
