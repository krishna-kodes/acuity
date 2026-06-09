"""E6-T3: Route coverage tests for gaps not covered by test_e5t6.py or test_routes.py.

Covers:
- GET /projects (list all)
- GET /projects/{id}/export/proposal (FileResponse + disk I/O)
- GET /projects/{id}/metrics (shape + 404)
- 404 for missing project_id on key GET endpoints
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from app.models.enums import ProjectPhase, ProjectStatus
from app.models.project import Project, Proposal


# ---------------------------------------------------------------------------
# GET /projects — list all
# ---------------------------------------------------------------------------

def test_list_projects_returns_200(client):
    resp = client.get("/api/v1/projects")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_projects_includes_preseeded_project(client, project_id):
    resp = client.get("/api/v1/projects")
    ids = [p["id"] for p in resp.json()]
    assert project_id in ids


def test_list_projects_response_shape(client):
    resp = client.get("/api/v1/projects")
    p = resp.json()[0]
    for field in ("id", "name", "status", "current_phase", "created_at"):
        assert field in p, f"Missing field: {field}"


def test_list_projects_domain_field_present(client, db_session):
    proj = Project(
        name="Domain Test",
        domain="FinTech",
        phase=ProjectPhase.redaction,
        status=ProjectStatus.active,
    )
    db_session.add(proj)
    db_session.commit()

    resp = client.get("/api/v1/projects")
    match = next((x for x in resp.json() if x["name"] == "Domain Test"), None)
    assert match is not None
    assert match["domain"] == "FinTech"


def test_list_projects_domain_null_when_not_set(client):
    resp = client.get("/api/v1/projects")
    # conftest project has no domain
    item = next(x for x in resp.json() if x["name"] == "Test Project")
    assert item["domain"] is None


def test_list_projects_ordered_newest_first(client, db_session):
    p1 = Project(name="Older", phase=ProjectPhase.redaction, status=ProjectStatus.draft)
    p2 = Project(name="Newer", phase=ProjectPhase.redaction, status=ProjectStatus.draft)
    db_session.add(p1)
    db_session.add(p2)
    db_session.commit()

    resp = client.get("/api/v1/projects")
    names = [p["name"] for p in resp.json()]
    # Newer should appear before Older (ordered by created_at desc)
    assert names.index("Newer") < names.index("Older")


# ---------------------------------------------------------------------------
# GET /projects/{id}/export/proposal
# ---------------------------------------------------------------------------

def test_export_proposal_file_missing_on_disk_returns_404(client, project_id):
    # conftest proposal has content_path="documents/stub.docx" which doesn't exist
    resp = client.get(f"/api/v1/projects/{project_id}/export/proposal")
    assert resp.status_code == 404


def test_export_proposal_returns_file_with_attachment_header(client, project_id, db_session, tmp_path):
    from docx import Document as DocxDocument

    docx_path = str(tmp_path / "proposal.docx")
    DocxDocument().save(docx_path)

    db_session.query(Proposal).filter(
        Proposal.project_id == int(project_id)
    ).update({"content_path": docx_path})
    db_session.commit()

    resp = client.get(f"/api/v1/projects/{project_id}/export/proposal")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("content-disposition", "")


def test_export_proposal_content_type_is_docx(client, project_id, db_session, tmp_path):
    from docx import Document as DocxDocument

    docx_path = str(tmp_path / "proposal.docx")
    DocxDocument().save(docx_path)

    db_session.query(Proposal).filter(
        Proposal.project_id == int(project_id)
    ).update({"content_path": docx_path})
    db_session.commit()

    resp = client.get(f"/api/v1/projects/{project_id}/export/proposal")
    assert "wordprocessingml" in resp.headers.get("content-type", "")


def test_export_proposal_missing_project_returns_404(client):
    resp = client.get("/api/v1/projects/99999/export/proposal")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /projects/{id}/metrics
# ---------------------------------------------------------------------------

def test_metrics_returns_200(client, project_id):
    resp = client.get(f"/api/v1/projects/{project_id}/metrics")
    assert resp.status_code == 200


def test_metrics_response_shape(client, project_id):
    resp = client.get(f"/api/v1/projects/{project_id}/metrics")
    data = resp.json()
    for field in ("total_tokens", "total_cost_usd", "phase_latencies", "eval_pass_rate", "github_sync_success_rate"):
        assert field in data, f"Missing field: {field}"


def test_metrics_missing_project_returns_404(client):
    resp = client.get("/api/v1/projects/99999/metrics")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 404 for missing project on key GET endpoints
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "/api/v1/projects/99999/tbds",
    "/api/v1/projects/99999/proposal",
    "/api/v1/projects/99999/redaction-decisions",
    "/api/v1/projects/99999/metrics",
])
def test_missing_project_returns_404(client, path):
    resp = client.get(path)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /projects/{id}/export/estimate
# ---------------------------------------------------------------------------

def _seed_epic_and_task(db_session, project_id: str):
    """Helper: create one Epic + one Task for export tests."""
    import json
    from app.models.sync import Epic, Task
    from app.models.enums import SyncStatus

    epic = Epic(
        project_id=int(project_id),
        title="Auth Module",
        estimated_points=8,
        sync_status=SyncStatus.pending,
    )
    db_session.add(epic)
    db_session.flush()

    task = Task(
        epic_id=epic.id,
        title="Implement login",
        estimated_points=5,
        assignees=json.dumps(["alice"]),
        github_issue_url="https://github.com/org/repo/issues/1",
        sync_status=SyncStatus.pending,
    )
    db_session.add(task)
    db_session.commit()


def test_export_estimate_csv_returns_attachment(client, project_id, db_session):
    _seed_epic_and_task(db_session, project_id)
    resp = client.get(f"/api/v1/projects/{project_id}/export/estimate?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert "attachment" in resp.headers.get("content-disposition", "")
    body = resp.text
    assert "epic_title" in body
    assert "task_title" in body


def test_export_estimate_xlsx_returns_attachment(client, project_id, db_session):
    _seed_epic_and_task(db_session, project_id)
    resp = client.get(f"/api/v1/projects/{project_id}/export/estimate?format=xlsx")
    assert resp.status_code == 200
    assert "openxmlformats" in resp.headers.get("content-type", "")
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert len(resp.content) > 0


def test_export_estimate_phase_guard(client, project_id, db_session):
    from app.models.enums import ProjectPhase
    from app.models.project import Project
    db_session.query(Project).filter(
        Project.id == int(project_id)
    ).update({"phase": ProjectPhase.chat})
    db_session.commit()
    resp = client.get(f"/api/v1/projects/{project_id}/export/estimate?format=csv")
    assert resp.status_code == 409
    assert "Phase 5" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# POST /projects/{id}/modules/stream — SSE streaming
# ---------------------------------------------------------------------------

def test_extract_modules_stream_emits_sse_events(client, project_id, db_session):
    """Streaming endpoint emits started, one+ module events, and done."""
    from app.models.project import Proposal as _Proposal

    proposal = db_session.query(_Proposal).filter(_Proposal.project_id == int(project_id)).first()
    if not proposal:
        proposal = _Proposal(
            project_id=int(project_id),
            document_id=0,
            content_path="documents/stub.docx",
        )
        db_session.add(proposal)
    proposal.content_json = json.dumps({
        "sections": [{"heading": "Overview", "body": "Build an e-commerce platform."}]
    })
    db_session.commit()

    chunks = [
        MagicMock(content='{"modules": ['),
        MagicMock(content='{"id": "m-1", "title": "Auth Service", "label": "backend", "description": "Handles login."}'),
        MagicMock(content=', {"id": "m-2", "title": "Product UI", "label": "frontend", "description": "Product pages."}'),
        MagicMock(content="]}"),
    ]

    async def _astream(prompt):
        for c in chunks:
            yield c

    mock_llm = MagicMock()
    mock_llm.astream = _astream

    with patch("app.services.llm_factory.get_llm", return_value=mock_llm):
        resp = client.post(f"/api/v1/projects/{project_id}/modules/stream")

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = [
        json.loads(line[6:])
        for line in resp.text.splitlines()
        if line.startswith("data: ")
    ]

    assert events[0] == {"type": "status", "status": "started"}

    module_events = [e for e in events if e["type"] == "module"]
    assert len(module_events) == 2
    assert module_events[0]["module"]["title"] == "Auth Service"
    assert module_events[0]["module"]["label"] == "backend"
    assert module_events[1]["module"]["title"] == "Product UI"

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["count"] == 2
    assert len(done_events[0]["modules"]) == 2


def test_extract_modules_stream_empty_proposal(client, project_id, db_session):
    """Streaming endpoint emits started+done with no modules when proposal has no content."""
    from app.models.project import Proposal as _Proposal

    proposal = db_session.query(_Proposal).filter(_Proposal.project_id == int(project_id)).first()
    if not proposal:
        proposal = _Proposal(
            project_id=int(project_id),
            document_id=0,
            content_path="documents/stub.docx",
        )
        db_session.add(proposal)
    proposal.content_json = None
    db_session.commit()

    resp = client.post(f"/api/v1/projects/{project_id}/modules/stream")

    assert resp.status_code == 200
    events = [
        json.loads(line[6:])
        for line in resp.text.splitlines()
        if line.startswith("data: ")
    ]
    assert events[0] == {"type": "status", "status": "started"}
    assert events[-1]["type"] == "done"
    assert events[-1]["count"] == 0
