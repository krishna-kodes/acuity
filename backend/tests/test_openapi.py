import pytest

EXPECTED_ROUTES = [
    ("/api/v1/projects", "post"),
    ("/api/v1/projects/{project_id}/documents", "post"),
    ("/api/v1/projects/{project_id}/tbds", "get"),
    ("/api/v1/projects/{project_id}/clarifications", "post"),
    ("/api/v1/projects/{project_id}/proposal", "post"),
    ("/api/v1/projects/{project_id}/proposal", "get"),
    ("/api/v1/projects/{project_id}/stack", "post"),
    ("/api/v1/projects/{project_id}/estimate", "post"),
    ("/api/v1/projects/{project_id}/sync", "post"),
    ("/api/v1/projects/{project_id}/metrics", "get"),
    ("/api/v1/factory/seed-employees", "post"),
    ("/api/v1/factory/seed-projects", "post"),
    ("/api/v1/factory/seed-technologies", "post"),
    ("/api/v1/factory/seed-all", "post"),
    ("/api/v1/factory/reset-db", "delete"),
]


@pytest.mark.parametrize("path,method", EXPECTED_ROUTES)
def test_route_present_in_openapi(client, path, method):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert path in paths, f"Missing path: {path}"
    assert method in paths[path], f"Missing method {method} on {path}"


def test_openapi_title(client):
    resp = client.get("/openapi.json")
    assert resp.json()["info"]["title"] == "Acuity API"


def test_all_api_routes_have_summaries(client):
    resp = client.get("/openapi.json")
    paths = resp.json()["paths"]
    api_paths = {k: v for k, v in paths.items() if k.startswith("/api/v1/")}
    for path, methods in api_paths.items():
        for method, spec in methods.items():
            assert "summary" in spec, f"Missing summary on {method.upper()} {path}"
