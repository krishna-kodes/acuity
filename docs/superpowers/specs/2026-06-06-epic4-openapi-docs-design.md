# Epic 4 (T4): OpenAPI Docs — Route Summaries & Contract Audit — Spec

**Goal:** Enrich all 15 FastAPI endpoints with `summary=` strings so the live `/docs` UI is useful, and verify every route name and HTTP method matches the CLAUDE.md API surface table.

**Issue:** #33

**Branch:** `feat/epic4-task4-openapi`

**Approach:** Summaries only (YAGNI). No descriptions, no error response docs — those belong in Epic 5 when real behaviour is implemented. The AC is "Frontend team confirms contract match" — summaries cover that.

---

## Changes

### `backend/app/routers/projects.py` — add `summary=` to all 10 decorators

| Route | Method | Summary |
|-------|--------|---------|
| `/projects` | POST | Create a new project |
| `/projects/{project_id}/documents` | POST | Upload requirements document |
| `/projects/{project_id}/tbds` | GET | Get detected TBD items |
| `/projects/{project_id}/clarifications` | POST | Submit TBD clarification |
| `/projects/{project_id}/proposal` | POST | Generate proposal document |
| `/projects/{project_id}/proposal` | GET | Retrieve generated proposal |
| `/projects/{project_id}/stack` | POST | Run tech stack suggestion |
| `/projects/{project_id}/estimate` | POST | Run effort estimation |
| `/projects/{project_id}/sync` | POST | Sync epics and tasks to GitHub |
| `/projects/{project_id}/metrics` | GET | Retrieve project metrics |

### `backend/app/routers/factory.py` — add `summary=` to all 5 decorators

| Route | Method | Summary |
|-------|--------|---------|
| `/factory/seed-employees` | POST | Seed employee data |
| `/factory/seed-projects` | POST | Seed historical projects |
| `/factory/seed-technologies` | POST | Seed approved technologies |
| `/factory/seed-all` | POST | Seed all tables |
| `/factory/reset-db` | DELETE | Reset database |

---

## Route Audit Test

### `backend/tests/test_openapi.py`

Verify all 15 paths and their HTTP methods appear in `/openapi.json`. Fails fast if any route is missing or misconfigured.

```python
import pytest

EXPECTED_ROUTES = [
    ("/api/v1/projects",                                "post"),
    ("/api/v1/projects/{project_id}/documents",         "post"),
    ("/api/v1/projects/{project_id}/tbds",              "get"),
    ("/api/v1/projects/{project_id}/clarifications",    "post"),
    ("/api/v1/projects/{project_id}/proposal",          "post"),
    ("/api/v1/projects/{project_id}/proposal",          "get"),
    ("/api/v1/projects/{project_id}/stack",             "post"),
    ("/api/v1/projects/{project_id}/estimate",          "post"),
    ("/api/v1/projects/{project_id}/sync",              "post"),
    ("/api/v1/projects/{project_id}/metrics",           "get"),
    ("/api/v1/factory/seed-employees",                  "post"),
    ("/api/v1/factory/seed-projects",                   "post"),
    ("/api/v1/factory/seed-technologies",               "post"),
    ("/api/v1/factory/seed-all",                        "post"),
    ("/api/v1/factory/reset-db",                        "delete"),
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
```

---

## Definition of done

- `ruff check .` and `mypy .` pass
- `pytest tests/` passes — 26 existing + 17 new (15 route audit + 2 named) = 43 tests
- `/docs` shows all 15 endpoints with summaries visible in the Swagger UI
- No route name mismatches vs CLAUDE.md API surface table
