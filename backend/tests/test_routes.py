import io
from unittest.mock import MagicMock, patch

import pytest

ENDPOINTS = [
    ("POST", "/api/v1/projects", {"name": "Test Project"}),
    ("GET", "/api/v1/projects/stub-id/tbds", None),
    ("POST", "/api/v1/projects/stub-id/clarifications", {"tbd_id": "t1", "action": "TBD"}),
    ("POST", "/api/v1/projects/stub-id/proposal", None),
    ("GET", "/api/v1/projects/stub-id/proposal", None),
    ("POST", "/api/v1/projects/stub-id/stack", None),
    ("POST", "/api/v1/projects/stub-id/estimate", None),
    ("POST", "/api/v1/projects/stub-id/sync", None),
    ("GET", "/api/v1/projects/stub-id/metrics", None),
    ("POST", "/api/v1/factory/seed-employees", None),
    ("POST", "/api/v1/factory/seed-projects", None),
    ("POST", "/api/v1/factory/seed-technologies", None),
    ("POST", "/api/v1/factory/seed-all", None),
    ("DELETE", "/api/v1/factory/reset-db", None),
]


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_endpoint_returns_2xx(client, method, path, body):
    kwargs = {"json": body} if body is not None else {}
    resp = getattr(client, method.lower())(path, **kwargs)
    assert resp.status_code < 300, f"{method} {path} → {resp.status_code}: {resp.text}"


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


def test_create_project_returns_name(client):
    resp = client.post("/api/v1/projects", json={"name": "My Project"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "My Project"


def test_sync_response_has_status(client):
    resp = client.post("/api/v1/projects/stub-id/sync")
    assert "status" in resp.json()


def test_factory_reset_returns_status(client):
    resp = client.delete("/api/v1/factory/reset-db")
    assert resp.json()["status"] == "reset"
