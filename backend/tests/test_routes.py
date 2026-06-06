import io

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
    data = io.BytesIO(b"fake pdf content")
    resp = client.post(
        "/api/v1/projects/stub-id/documents",
        files={"file": ("test.pdf", data, "application/pdf")},
    )
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
