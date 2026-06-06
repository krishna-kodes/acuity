# Epic 4 (T4): OpenAPI Docs — Route Summaries & Contract Audit

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `summary=` strings to all 15 FastAPI endpoints and verify every route name and HTTP method matches the CLAUDE.md API surface table.

**Architecture:** Two router files get `summary=` added to each decorator. A new test file audits the live `/openapi.json` to confirm all 15 routes are present with correct methods and that every `/api/v1/` route has a summary. No new files other than the test.

**Tech Stack:** Python 3.11, FastAPI 0.111, pytest, httpx

**Spec:** `docs/superpowers/specs/2026-06-06-epic4-openapi-docs-design.md`

---

## File map

```
backend/
├── app/
│   ├── routers/
│   │   ├── projects.py    ← add summary= to 10 decorators
│   │   └── factory.py     ← add summary= to 5 decorators
└── tests/
    └── test_openapi.py    ← create: 17 new tests
```

---

## Task 1: OpenAPI route summaries and contract audit (Issue #33)

**Branch:** `feat/epic4-task4-openapi`

**Files:**
- Modify: `backend/app/routers/projects.py`
- Modify: `backend/app/routers/factory.py`
- Create: `backend/tests/test_openapi.py`

---

- [ ] **Step 1: Branch from main**

```bash
cd /path/to/acuity
git checkout main && git pull origin main
git checkout -b feat/epic4-task4-openapi
```

---

- [ ] **Step 2: Write the failing tests first**

Create `backend/tests/test_openapi.py`:

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

- [ ] **Step 3: Run tests — verify they fail**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
python -m pytest tests/test_openapi.py -v 2>&1 | tail -20
```

Expected: `test_all_api_routes_have_summaries` FAILS — routes have no summaries yet. Route presence tests should PASS (routes exist).

---

- [ ] **Step 4: Add summaries to `backend/app/routers/projects.py`**

Replace the entire file with:

```python
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.clarification import ClarificationCreate, ClarificationResponse
from app.schemas.document import DocumentResponse
from app.schemas.metrics import MetricsResponse
from app.schemas.project import (
    EstimationResponse,
    ProjectCreate,
    ProjectResponse,
    TBDItem,
    TechStackResponse,
)
from app.schemas.proposal import ProposalResponse
from app.schemas.sync import SyncResponse, SyncStatus

router = APIRouter(tags=["projects"])


@router.post(
    "/projects",
    summary="Create a new project",
    response_model=ProjectResponse,
    status_code=201,
)
def create_project(
    body: ProjectCreate,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    # TODO(Epic 5 #35): persist to DB
    return ProjectResponse(
        id="stub-id",
        name=body.name,
        status="draft",
        current_phase=1,
        created_at="2026-01-01T00:00:00Z",
    )


@router.post(
    "/projects/{project_id}/documents",
    summary="Upload requirements document",
    response_model=DocumentResponse,
    status_code=201,
)
def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    # TODO(Epic 5 #38): run PII detection and store document
    return DocumentResponse(
        id="stub-doc-id",
        project_id=project_id,
        filename=file.filename or "unknown",
        status="uploaded",
        upload_ts="2026-01-01T00:00:00Z",
    )


@router.get(
    "/projects/{project_id}/tbds",
    summary="Get detected TBD items",
    response_model=list[TBDItem],
)
def get_tbds(
    project_id: str,
    db: Session = Depends(get_db),
) -> list[TBDItem]:
    # TODO(Epic 5 #37): retrieve TBDs from LangGraph state
    return []


@router.post(
    "/projects/{project_id}/clarifications",
    summary="Submit TBD clarification",
    response_model=ClarificationResponse,
    status_code=201,
)
def create_clarification(
    project_id: str,
    body: ClarificationCreate,
    db: Session = Depends(get_db),
) -> ClarificationResponse:
    # TODO(Epic 5 #40): persist clarification
    return ClarificationResponse(
        id="stub-clarification-id",
        tbd_id=body.tbd_id,
        action=body.action,
        answer=body.answer,
    )


@router.post(
    "/projects/{project_id}/proposal",
    summary="Generate proposal document",
    response_model=ProposalResponse,
    status_code=201,
)
def generate_proposal(
    project_id: str,
    db: Session = Depends(get_db),
) -> ProposalResponse:
    # TODO(Epic 5 #37): trigger LangGraph proposal generation node
    return ProposalResponse(
        id="stub-proposal-id",
        project_id=project_id,
        content_path="documents/stub-proposal.docx",
        created_at="2026-01-01T00:00:00Z",
    )


@router.get(
    "/projects/{project_id}/proposal",
    summary="Retrieve generated proposal",
    response_model=ProposalResponse,
)
def get_proposal(
    project_id: str,
    db: Session = Depends(get_db),
) -> ProposalResponse:
    # TODO(Epic 5 #40): retrieve from proposals table
    return ProposalResponse(
        id="stub-proposal-id",
        project_id=project_id,
        content_path="documents/stub-proposal.docx",
        created_at="2026-01-01T00:00:00Z",
    )


@router.post(
    "/projects/{project_id}/stack",
    summary="Run tech stack suggestion",
    response_model=TechStackResponse,
)
def suggest_stack(
    project_id: str,
    db: Session = Depends(get_db),
) -> TechStackResponse:
    # TODO(Epic 5 #37): run tech stack suggestion agent node
    return TechStackResponse(
        frontend=["Next.js"],
        backend=["FastAPI"],
        database=["SQLite"],
        infra=["Railway"],
        rationale="Stub rationale — populated by LangGraph in Epic 5.",
    )


@router.post(
    "/projects/{project_id}/estimate",
    summary="Run effort estimation",
    response_model=EstimationResponse,
)
def estimate_effort(
    project_id: str,
    db: Session = Depends(get_db),
) -> EstimationResponse:
    # TODO(Epic 5 #37): run effort estimation agent node
    return EstimationResponse(
        epics=[{"title": "Stub Epic", "estimated_points": 8, "confidence": 0.8}],
        total_points=8,
        total_weeks=2.0,
    )


@router.post(
    "/projects/{project_id}/sync",
    summary="Sync epics and tasks to GitHub",
    response_model=SyncResponse,
)
def sync_to_github(
    project_id: str,
    db: Session = Depends(get_db),
) -> SyncResponse:
    # TODO(Epic 5 #39): call GitHub MCP sync tools
    return SyncResponse(synced=0, skipped=0, failed=0, status=SyncStatus.pending)


@router.get(
    "/projects/{project_id}/metrics",
    summary="Retrieve project metrics",
    response_model=MetricsResponse,
)
def get_metrics(
    project_id: str,
    db: Session = Depends(get_db),
) -> MetricsResponse:
    # TODO(Epic 5 #40): aggregate from metrics + latency_logs tables
    return MetricsResponse(
        total_tokens=0,
        total_cost_usd=0.0,
        phase_latencies={},
        eval_pass_rate=0.0,
        github_sync_success_rate=0.0,
    )
```

---

- [ ] **Step 5: Add summaries to `backend/app/routers/factory.py`**

Replace the entire file with:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.sync import SeedResult

router = APIRouter(tags=["factory"])


@router.post("/factory/seed-employees", summary="Seed employee data", response_model=SeedResult)
def seed_employees(db: Session = Depends(get_db)) -> SeedResult:
    # TODO(Epic 5 #40): seed from Faker with FAKER_SEED
    return SeedResult(seeded=0, status="ok")


@router.post("/factory/seed-projects", summary="Seed historical projects", response_model=SeedResult)
def seed_projects(db: Session = Depends(get_db)) -> SeedResult:
    # TODO(Epic 5 #40): seed from Faker with FAKER_SEED
    return SeedResult(seeded=0, status="ok")


@router.post(
    "/factory/seed-technologies",
    summary="Seed approved technologies",
    response_model=SeedResult,
)
def seed_technologies(db: Session = Depends(get_db)) -> SeedResult:
    # TODO(Epic 5 #40): seed from Faker with FAKER_SEED
    return SeedResult(seeded=0, status="ok")


@router.post("/factory/seed-all", summary="Seed all tables", response_model=SeedResult)
def seed_all(db: Session = Depends(get_db)) -> SeedResult:
    # TODO(Epic 5 #40): seed all tables
    return SeedResult(seeded=0, status="ok")


@router.delete("/factory/reset-db", summary="Reset database")
def reset_db(db: Session = Depends(get_db)) -> dict:
    # TODO(Epic 5 #35): drop and recreate all tables
    return {"status": "reset"}
```

---

- [ ] **Step 6: Run all tests — verify 43 pass**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: **43 tests pass**
- 7 schema tests
- 1 health test
- 18 route smoke tests (from previous tasks)
- 15 parametrised OpenAPI route tests
- 1 `test_openapi_title`
- 1 `test_all_api_routes_have_summaries`

If any fail, check:
- Route presence failures → wrong path or HTTP method in router decorator
- Summary failures → `summary=` missing or misspelled in a decorator

---

- [ ] **Step 7: Run linter and type checker**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
ruff check .
mypy .
```

Expected: both pass clean. Fix any line-length issues by breaking decorator args onto separate lines (already done in Step 4).

---

- [ ] **Step 8: Commit and push**

```bash
cd /path/to/acuity
git add backend/
git commit -m "feat: [E4-T4] add OpenAPI summaries to all 15 endpoints + route audit tests

Closes #33"
git push -u origin feat/epic4-task4-openapi
```

---

- [ ] **Step 9: Open PR**

```bash
gh pr create \
  --repo krishna-kodes/acuity \
  --base main \
  --title "[E4-T4] OpenAPI summaries on all 15 endpoints" \
  --body "## Summary
Adds \`summary=\` strings to all 15 /api/v1/ endpoints so the Swagger UI at /docs is useful. Adds a route audit test suite that confirms every route from CLAUDE.md is present in the live OpenAPI spec with the correct HTTP method.

## Related issues
Closes #33

## Changes
- \`routers/projects.py\` — summary= on all 10 route decorators
- \`routers/factory.py\` — summary= on all 5 route decorators
- \`tests/test_openapi.py\` — 17 new tests (15 route audit + 2 named)

## Dependency check
- [x] The epic this work depends on is merged to \`main\` (Epic 1 Task 1 scaffold merged — routes exist)
- [x] I pulled latest \`main\` and rebased this branch before opening the PR
- [x] I checked for new issues opened by the other dev that could affect this work

## Testing
- [x] \`pytest tests/\` — 43 tests pass
- [x] \`ruff check .\` passes
- [x] \`mypy .\` passes
- [x] \`/docs\` shows all 15 endpoints with summaries visible"
```

---

- [ ] **Step 10: Merge and clean up**

```bash
gh pr merge --repo krishna-kodes/acuity --squash --delete-branch
git checkout main && git pull origin main
git branch -d feat/epic4-task4-openapi 2>/dev/null || true
git fetch --prune
```
