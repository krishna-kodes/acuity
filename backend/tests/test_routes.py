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


def test_stack_stream_returns_event_stream_cached(client, project_id, db_session):
    from app.models.enums import ProjectPhase
    from app.models.project import Project
    project = db_session.query(Project).first()
    project.tech_stack = {
        "frontend": ["Next.js"],
        "backend": ["FastAPI"],
        "database": ["SQLite"],
        "infra": ["Railway"],
        "rationale": "cached rationale",
    }
    project.phase = ProjectPhase.estimation
    db_session.commit()

    resp = client.post(f"/api/v1/projects/{project_id}/stack/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    lines = [l for l in resp.text.split("\n") if l.startswith("data: ")]
    events = [_json.loads(l[6:]) for l in lines]
    types = [e["type"] for e in events]
    assert "status" in types
    assert "category" in types
    assert "rationale" in types
    assert "done" in types

    category_events = [e for e in events if e["type"] == "category"]
    keys = {e["key"] for e in category_events}
    assert keys == {"frontend", "backend", "database", "infra"}

    done_event = next(e for e in events if e["type"] == "done")
    assert done_event["stack"]["frontend"] == ["Next.js"]


def test_stack_stream_returns_409_when_modules_not_done(client, project_id, db_session):
    from app.models.enums import ProjectPhase
    from app.models.project import Project
    project = db_session.query(Project).first()
    project.phase = ProjectPhase.chat
    db_session.commit()

    resp = client.post(f"/api/v1/projects/{project_id}/stack/stream")
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /projects/{id}/estimate/stream
# ---------------------------------------------------------------------------

def test_estimate_stream_returns_409_when_team_not_done(client, project_id, db_session):
    from app.models.enums import ProjectPhase
    from app.models.project import Project
    project = db_session.query(Project).first()
    project.phase = ProjectPhase.chat
    db_session.commit()
    resp = client.post(f"/api/v1/projects/{project_id}/estimate/stream")
    assert resp.status_code == 409


def test_estimate_stream_replays_cached_events(client, project_id, db_session):
    import json as _json

    from app.models.enums import ProjectPhase
    from app.models.project import Project
    project = db_session.query(Project).first()
    project.phase = ProjectPhase.estimation
    project.effort_estimates = {
        "total_weeks": 8,
        "total_points": 32,
        "confidence": 0.9,
        "breakdown": {"Backend API": 32},
        "reasoning": "test reasoning",
    }
    db_session.commit()
    resp = client.post(f"/api/v1/projects/{project_id}/estimate/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    lines = [l for l in resp.text.split("\n") if l.startswith("data: ")]
    events = [_json.loads(l[6:]) for l in lines]
    types = [e["type"] for e in events]
    assert "status" in types
    assert "epic" in types
    assert "summary" in types
    assert "done" in types
    epic_events = [e for e in events if e["type"] == "epic"]
    assert epic_events[0]["title"] == "Backend API"
    assert epic_events[0]["estimated_points"] == 32
    done_event = next(e for e in events if e["type"] == "done")
    assert done_event["total_points"] == 32
    assert done_event["total_weeks"] == 8.0


def test_estimate_stream_live_emits_epic_events(client, project_id, db_session):
    import json as _json
    from unittest.mock import MagicMock, patch

    from app.models.enums import ProjectPhase
    from app.models.project import Project
    project = db_session.query(Project).first()
    project.phase = ProjectPhase.team
    project.effort_estimates = None
    project.team_suggestion = {"members": ["dev1", "dev2", "dev3"]}
    db_session.commit()
    chunks = [
        MagicMock(content='{"total_weeks": 6, "total_points": 24, "confidence": 0.8, "breakdown": ['),
        MagicMock(content='{"phase": "Auth Service", "points": 12},'),
        MagicMock(content='{"phase": "API Gateway", "points": 12}'),
        MagicMock(content='], "reasoning": "Based on similar projects."}'),
    ]
    async def _astream(prompt):
        for c in chunks:
            yield c
    mock_llm = MagicMock()
    mock_llm.astream = _astream
    with patch("app.services.llm_factory.get_llm", return_value=mock_llm):
        resp = client.post(f"/api/v1/projects/{project_id}/estimate/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    lines = [l for l in resp.text.split("\n") if l.startswith("data: ")]
    events = [_json.loads(l[6:]) for l in lines]
    epic_events = [e for e in events if e["type"] == "epic"]
    assert len(epic_events) == 2
    assert epic_events[0]["title"] == "Auth Service"
    assert epic_events[0]["estimated_points"] == 12
    assert epic_events[1]["title"] == "API Gateway"
    done_event = next(e for e in events if e["type"] == "done")
    assert done_event["total_points"] == 24
    assert done_event["total_weeks"] == 6.0


# ---------------------------------------------------------------------------
# POST /projects/{id}/epics/stream
# ---------------------------------------------------------------------------

def test_epics_stream_returns_409_when_estimation_not_done(client, project_id, db_session):
    from app.models.enums import ProjectPhase
    from app.models.project import Project
    project = db_session.query(Project).first()
    project.phase = ProjectPhase.chat
    db_session.commit()
    resp = client.post(f"/api/v1/projects/{project_id}/epics/stream")
    assert resp.status_code == 409


def test_epics_stream_replays_cached_events(client, project_id, db_session):
    import json as _json

    from app.models.enums import ProjectPhase
    from app.models.project import Project
    from app.models.sync import Epic, Task

    project = db_session.query(Project).first()
    project.phase = ProjectPhase.epics

    epic = Epic(project_id=project.id, title="Auth Epic", description="Auth system", sync_status="pending")
    db_session.add(epic)
    db_session.flush()
    task = Task(
        epic_id=epic.id,
        title="Login page",
        description="",
        estimated_points=3,
        labels='["frontend"]',
        sync_status="pending",
    )
    db_session.add(task)
    db_session.commit()

    resp = client.post(f"/api/v1/projects/{project_id}/epics/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    lines = [l for l in resp.text.split("\n") if l.startswith("data: ")]
    events = [_json.loads(l[6:]) for l in lines]
    types = [e["type"] for e in events]
    assert "status" in types
    assert "epic" in types
    assert "done" in types

    epic_events = [e for e in events if e["type"] == "epic"]
    assert epic_events[0]["title"] == "Auth Epic"
    assert epic_events[0]["tasks"][0]["title"] == "Login page"
    assert epic_events[0]["tasks"][0]["story_points"] == 3

    done_event = next(e for e in events if e["type"] == "done")
    assert done_event["count"] == 1


def test_epics_stream_live_emits_epic_events(client, project_id, db_session):
    import json as _json
    from unittest.mock import MagicMock, patch

    from app.models.enums import ProjectPhase
    from app.models.project import Project

    project = db_session.query(Project).first()
    project.phase = ProjectPhase.estimation
    project.effort_estimates = {"total_points": 24, "total_weeks": 6}
    db_session.commit()

    chunks = [
        MagicMock(content='[{"title": "Auth Epic", "description": "Handle authentication", "due_date": "2026-07-15", '),
        MagicMock(content='"tasks": [{"title": "Login", "description": "Login page", "story_points": 3, "labels": ["frontend"]}]},'),
        MagicMock(content='{"title": "API Epic", "description": "REST API layer", "due_date": "2026-08-01", '),
        MagicMock(content='"tasks": [{"title": "CRUD routes", "description": "Endpoints", "story_points": 5, "labels": ["backend"]}]}]'),
    ]

    async def _astream(prompt):
        for c in chunks:
            yield c

    mock_llm = MagicMock()
    mock_llm.astream = _astream
    with patch("app.services.llm_factory.get_llm", return_value=mock_llm):
        resp = client.post(f"/api/v1/projects/{project_id}/epics/stream")

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    lines = [l for l in resp.text.split("\n") if l.startswith("data: ")]
    events = [_json.loads(l[6:]) for l in lines]
    epic_events = [e for e in events if e["type"] == "epic"]
    assert len(epic_events) == 2
    assert epic_events[0]["title"] == "Auth Epic"
    assert epic_events[0]["tasks"][0]["title"] == "Login"
    assert epic_events[1]["title"] == "API Epic"

    done_event = next(e for e in events if e["type"] == "done")
    assert done_event["count"] == 2

    from app.models.sync import Epic as EpicModel
    db_epics = db_session.query(EpicModel).filter(EpicModel.project_id == project.id).all()
    assert len(db_epics) == 2
    assert db_epics[0].title == "Auth Epic"
