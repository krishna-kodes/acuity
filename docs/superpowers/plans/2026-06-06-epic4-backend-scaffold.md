# Epic 4 (T1–T3): Backend Scaffold & Stub Endpoints — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the FastAPI backend with a full layered structure, formalise the API contract as typed Pydantic schemas, and implement stub responses on all 15 endpoints so the frontend can integrate immediately.

**Architecture:** Three sequential tasks each producing one PR to `main`. Task 1 creates all Pydantic schemas and empty router shells (issue #30). Task 2 wires the FastAPI app, config, and database session (issue #31). Task 3 fills in stub return values and makes all smoke tests pass (issue #32).

**Tech Stack:** Python 3.11, FastAPI 0.111, Uvicorn, SQLAlchemy 2, pydantic-settings, pytest, httpx, ruff, mypy

**Spec:** `docs/superpowers/specs/2026-06-06-epic4-backend-scaffold-design.md`

---

## File map

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # Task 2
│   ├── config.py                # Task 2
│   ├── database.py              # Task 2
│   ├── routers/
│   │   ├── __init__.py          # Task 1
│   │   ├── projects.py          # Task 1 (shells) → Task 3 (stubs)
│   │   └── factory.py           # Task 1 (shells) → Task 3 (stubs)
│   ├── schemas/
│   │   ├── __init__.py          # Task 1
│   │   ├── project.py           # Task 1
│   │   ├── document.py          # Task 1
│   │   ├── clarification.py     # Task 1
│   │   ├── proposal.py          # Task 1
│   │   ├── sync.py              # Task 1
│   │   └── metrics.py           # Task 1
│   ├── models/
│   │   ├── __init__.py          # Task 1
│   │   └── base.py              # Task 1
│   └── services/
│       └── __init__.py          # Task 1
├── tests/
│   ├── __init__.py              # Task 2
│   ├── conftest.py              # Task 2
│   └── test_routes.py           # Task 3
├── requirements.txt             # Task 2
├── requirements-dev.txt         # Task 2
├── ruff.toml                    # Task 2
└── mypy.ini                     # Task 2
```

---

## Task 1: API contracts — schemas + router shells (Issue #30)

**Branch:** `feat/epic4-task1-api-contracts`

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/project.py`
- Create: `backend/app/schemas/document.py`
- Create: `backend/app/schemas/clarification.py`
- Create: `backend/app/schemas/proposal.py`
- Create: `backend/app/schemas/sync.py`
- Create: `backend/app/schemas/metrics.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/projects.py`
- Create: `backend/app/routers/factory.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/base.py`
- Create: `backend/app/services/__init__.py`

---

- [ ] **Step 1: Branch from main**

```bash
cd /path/to/acuity
git checkout main && git pull origin main
git checkout -b feat/epic4-task1-api-contracts
```

---

- [ ] **Step 2: Write the failing import test**

Create `backend/tests/__init__.py` (empty) and `backend/tests/test_schemas.py`:

```python
# backend/tests/test_schemas.py
from app.schemas.project import (
    ProjectCreate, ProjectResponse, TBDItem,
    TechStackResponse, EstimationResponse,
)
from app.schemas.document import DocumentResponse
from app.schemas.clarification import ClarificationCreate, ClarificationResponse
from app.schemas.proposal import ProposalResponse
from app.schemas.sync import SyncStatus, SyncResponse
from app.schemas.metrics import MetricsResponse


def test_project_create_fields():
    p = ProjectCreate(name="My Project")
    assert p.name == "My Project"


def test_project_response_fields():
    p = ProjectResponse(
        id="abc", name="Test", status="draft",
        current_phase=1, created_at="2026-01-01T00:00:00Z"
    )
    assert p.current_phase == 1


def test_tbd_item_fields():
    t = TBDItem(id="t1", question="What is the SLA?", level=2, resolved=False)
    assert t.level == 2


def test_sync_status_values():
    assert SyncStatus.pending == "pending"
    assert SyncStatus.synced == "synced"
    assert SyncStatus.skipped == "skipped"
    assert SyncStatus.failed == "failed"


def test_clarification_create_optional_answer():
    c = ClarificationCreate(tbd_id="t1", action="TBD")
    assert c.answer is None


def test_tech_stack_response_fields():
    ts = TechStackResponse(
        frontend=["Next.js"], backend=["FastAPI"],
        database=["SQLite"], infra=["Railway"], rationale="Best fit"
    )
    assert "Next.js" in ts.frontend


def test_estimation_response_fields():
    e = EstimationResponse(
        epics=[{"title": "E1", "estimated_points": 8, "confidence": 0.8}],
        total_points=8, total_weeks=2.0
    )
    assert e.total_points == 8
```

- [ ] **Step 3: Run test — verify it fails**

```bash
cd backend
python -m pytest tests/test_schemas.py -v
```

Expected: `ModuleNotFoundError: No module named 'app'`

---

- [ ] **Step 4: Create empty package files**

```bash
touch backend/app/__init__.py
touch backend/app/schemas/__init__.py
touch backend/app/routers/__init__.py
touch backend/app/models/__init__.py
touch backend/app/services/__init__.py
```

---

- [ ] **Step 5: Create `backend/app/schemas/project.py`**

```python
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str


class ProjectResponse(BaseModel):
    id: str
    name: str
    status: str
    current_phase: int
    created_at: str


class TBDItem(BaseModel):
    id: str
    question: str
    level: int
    resolved: bool


class TechStackResponse(BaseModel):
    frontend: list[str]
    backend: list[str]
    database: list[str]
    infra: list[str]
    rationale: str


class EstimationResponse(BaseModel):
    epics: list[dict]
    total_points: int
    total_weeks: float
```

---

- [ ] **Step 6: Create `backend/app/schemas/document.py`**

```python
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    status: str
    upload_ts: str
```

---

- [ ] **Step 7: Create `backend/app/schemas/clarification.py`**

```python
from pydantic import BaseModel


class ClarificationCreate(BaseModel):
    tbd_id: str
    action: str
    answer: str | None = None


class ClarificationResponse(BaseModel):
    id: str
    tbd_id: str
    action: str
    answer: str | None
```

---

- [ ] **Step 8: Create `backend/app/schemas/proposal.py`**

```python
from pydantic import BaseModel


class ProposalResponse(BaseModel):
    id: str
    project_id: str
    content_path: str
    created_at: str
```

---

- [ ] **Step 9: Create `backend/app/schemas/sync.py`**

```python
from enum import Enum
from pydantic import BaseModel


class SyncStatus(str, Enum):
    pending = "pending"
    synced = "synced"
    skipped = "skipped"
    failed = "failed"


class SyncResponse(BaseModel):
    synced: int
    skipped: int
    failed: int
    status: SyncStatus


class SeedResult(BaseModel):
    seeded: int
    status: str
```

---

- [ ] **Step 10: Create `backend/app/schemas/metrics.py`**

```python
from pydantic import BaseModel


class MetricsResponse(BaseModel):
    total_tokens: int
    total_cost_usd: float
    phase_latencies: dict[str, float]
    eval_pass_rate: float
    github_sync_success_rate: float
```

---

- [ ] **Step 11: Create `backend/app/models/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

---

- [ ] **Step 12: Create `backend/app/routers/projects.py` — empty shells only**

```python
from fastapi import APIRouter

router = APIRouter(tags=["projects"])


@router.post("/projects")
def create_project():
    pass


@router.post("/projects/{project_id}/documents")
def upload_document(project_id: str):
    pass


@router.get("/projects/{project_id}/tbds")
def get_tbds(project_id: str):
    pass


@router.post("/projects/{project_id}/clarifications")
def create_clarification(project_id: str):
    pass


@router.post("/projects/{project_id}/proposal")
def generate_proposal(project_id: str):
    pass


@router.get("/projects/{project_id}/proposal")
def get_proposal(project_id: str):
    pass


@router.post("/projects/{project_id}/stack")
def suggest_stack(project_id: str):
    pass


@router.post("/projects/{project_id}/estimate")
def estimate_effort(project_id: str):
    pass


@router.post("/projects/{project_id}/sync")
def sync_to_github(project_id: str):
    pass


@router.get("/projects/{project_id}/metrics")
def get_metrics(project_id: str):
    pass
```

---

- [ ] **Step 13: Create `backend/app/routers/factory.py` — empty shells only**

```python
from fastapi import APIRouter

router = APIRouter(tags=["factory"])


@router.post("/factory/seed-employees")
def seed_employees():
    pass


@router.post("/factory/seed-projects")
def seed_projects():
    pass


@router.post("/factory/seed-technologies")
def seed_technologies():
    pass


@router.post("/factory/seed-all")
def seed_all():
    pass


@router.delete("/factory/reset-db")
def reset_db():
    pass
```

---

- [ ] **Step 14: Run schema tests — verify they pass**

```bash
cd backend
python -m pytest tests/test_schemas.py -v
```

Expected: all 7 tests PASS

---

- [ ] **Step 15: Commit and push**

```bash
git add backend/
git commit -m "feat: [E4-T1] add pydantic schemas and router shells

Closes #30"
git push -u origin feat/epic4-task1-api-contracts
```

---

- [ ] **Step 16: Open PR to main**

```bash
gh pr create \
  --repo krishna-kodes/acuity \
  --base main \
  --title "[E4-T1] API contracts — Pydantic schemas and router shells" \
  --body "$(cat <<'EOF'
## Summary
Formalises the API contract from CLAUDE.md as typed Pydantic schemas and creates empty router shells for all 15 endpoints.

## Related issues
Closes #30

## Changes
- Add `app/schemas/` with 6 schema files covering all request/response types
- Add `app/routers/projects.py` and `factory.py` with empty route shells
- Add `app/models/base.py` (SQLAlchemy declarative base)
- Add schema import/field tests

## Dependency check
- [x] The epic this work depends on is merged to `main` (Epic 0 started — E4-T1 can run in parallel per CONTRIBUTING.md)
- [x] I pulled latest `main` and rebased this branch before opening the PR
- [x] I checked for new issues opened by the other dev that could affect this work

## Testing
- [x] `npx tsc --noEmit` passes (frontend) — N/A, backend only
- [x] `npm run lint` passes (frontend) — N/A
- [x] `pytest tests/test_schemas.py` passes
- [x] Manually verified the change works as expected
EOF
)"
```

- [ ] **Step 17: After PR is merged — pull latest main**

```bash
git checkout main && git pull origin main
git branch -d feat/epic4-task1-api-contracts
```

---

## Task 2: FastAPI app scaffold (Issue #31)

**Branch:** `feat/epic4-task2-fastapi-scaffold`

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`
- Create: `backend/ruff.toml`
- Create: `backend/mypy.ini`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`

---

- [ ] **Step 1: Branch from main**

```bash
git checkout main && git pull origin main
git checkout -b feat/epic4-task2-fastapi-scaffold
```

---

- [ ] **Step 2: Write the failing health endpoint test**

Create `backend/tests/conftest.py` (placeholder for now — fill in Step 7):

```python
# backend/tests/conftest.py
import pytest
```

Create `backend/tests/test_health.py`:

```python
# backend/tests/test_health.py
from fastapi.testclient import TestClient
from app.main import app


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 3: Run test — verify it fails**

```bash
cd backend
python -m pytest tests/test_health.py -v
```

Expected: `ModuleNotFoundError: No module named 'fastapi'`

---

- [ ] **Step 4: Create `backend/requirements.txt`**

```
fastapi==0.111.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.30
pydantic-settings==2.2.1
python-multipart==0.0.9
```

- [ ] **Step 5: Create `backend/requirements-dev.txt`**

```
-r requirements.txt
pytest==8.2.0
httpx==0.27.0
ruff==0.4.4
mypy==1.10.0
```

- [ ] **Step 6: Install dependencies**

```bash
cd backend
pip install -r requirements-dev.txt
```

Expected: installs without errors.

---

- [ ] **Step 7: Create `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    main_llm_provider: str = "google"
    main_llm_model: str = "gemini-1.5-pro"
    fast_llm_provider: str = "google"
    fast_llm_model: str = "gemini-1.5-flash"
    temperature: float = 0.2
    openai_api_key: str = ""
    google_api_key: str = ""
    anthropic_api_key: str = ""
    github_token: str = ""
    github_owner: str = ""
    github_repo: str = ""
    github_use_projects_v2: bool = False
    embedding_dimensions: int = 1536
    chroma_persist_path: str = "./chroma_db"
    pii_encryption_key: str = ""
    pii_detection_enabled: bool = True
    pii_regex_enabled: bool = True
    pii_ner_enabled: bool = True
    pii_review_gate: bool = True
    chunk_size_max_tokens: int = 800
    chunk_size_min_tokens: int = 50
    top_k_retrieval: int = 20
    top_n_rerank: int = 4
    query_rewrite_count: int = 3
    groundedness_threshold: float = 0.7
    max_cost_per_workflow_usd: float = 0.50
    observability_provider: str = "langsmith"
    langsmith_api_key: str = ""
    faker_seed: int = 42
    metrics_enabled: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
```

---

- [ ] **Step 8: Create `backend/app/database.py`**

```python
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

engine = create_engine(
    "sqlite:///./app.db",
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_conn, _record):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

- [ ] **Step 9: Create `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.factory import router as factory_router
from app.routers.projects import router as projects_router

app = FastAPI(title="Acuity API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router, prefix="/api/v1")
app.include_router(factory_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

---

- [ ] **Step 10: Fill in `backend/tests/conftest.py`**

```python
import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = lambda: None
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

---

- [ ] **Step 11: Run health test — verify it passes**

```bash
cd backend
python -m pytest tests/test_health.py -v
```

Expected: `test_health PASSED`

---

- [ ] **Step 12: Create `backend/ruff.toml`**

```toml
line-length = 100
target-version = "py311"

[lint]
select = ["E", "F", "I", "UP"]
ignore = []
```

- [ ] **Step 13: Create `backend/mypy.ini`**

```ini
[mypy]
python_version = 3.11
strict = false
ignore_missing_imports = true
```

- [ ] **Step 14: Run linter and type checker**

```bash
cd backend
ruff check .
mypy .
```

Expected: both pass with no errors. Fix any reported issues before proceeding.

---

- [ ] **Step 15: Verify dev server starts**

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` in a browser. Expected: Swagger UI showing all 15 endpoints listed under `projects` and `factory` tags. Stop the server (`Ctrl+C`).

---

- [ ] **Step 16: Commit and push**

```bash
git add backend/
git commit -m "feat: [E4-T2] FastAPI app scaffold with config, database, and CORS

Closes #31"
git push -u origin feat/epic4-task2-fastapi-scaffold
```

---

- [ ] **Step 17: Open PR to main**

```bash
gh pr create \
  --repo krishna-kodes/acuity \
  --base main \
  --title "[E4-T2] FastAPI app scaffold — config, database, CORS, health endpoint" \
  --body "$(cat <<'EOF'
## Summary
Wires the FastAPI app with pydantic-settings config, SQLAlchemy engine (WAL mode per ADR-007), CORS for localhost:3000, and a /health endpoint. All 15 routes are registered and visible in /docs.

## Related issues
Closes #31

## Changes
- `app/main.py` — FastAPI app, CORS middleware, router registration, /health
- `app/config.py` — typed settings from .env via pydantic-settings
- `app/database.py` — SQLAlchemy engine + WAL mode + get_db() dependency
- `tests/conftest.py` — TestClient fixture with get_db override
- `requirements.txt` / `requirements-dev.txt` / `ruff.toml` / `mypy.ini`

## Dependency check
- [x] Task 1 (feat/epic4-task1-api-contracts) is merged to `main`
- [x] I pulled latest `main` and rebased this branch before opening the PR
- [x] I checked for new issues opened by the other dev that could affect this work

## Testing
- [x] `pytest tests/test_health.py` passes
- [x] `ruff check .` passes
- [x] `mypy .` passes
- [x] `uvicorn app.main:app --reload` starts and /docs shows 15 endpoints
EOF
)"
```

- [ ] **Step 18: After PR is merged — pull latest main**

```bash
git checkout main && git pull origin main
git branch -d feat/epic4-task2-fastapi-scaffold
```

---

## Task 3: Stub responses + smoke tests (Issue #32)

**Branch:** `feat/epic4-task3-stub-responses`

**Files:**
- Modify: `backend/app/routers/projects.py`
- Modify: `backend/app/routers/factory.py`
- Create: `backend/tests/test_routes.py`

---

- [ ] **Step 1: Branch from main**

```bash
git checkout main && git pull origin main
git checkout -b feat/epic4-task3-stub-responses
```

---

- [ ] **Step 2: Write the failing smoke tests**

Create `backend/tests/test_routes.py`:

```python
import pytest
from fastapi.testclient import TestClient


ENDPOINTS = [
    ("POST",   "/api/v1/projects",                                  {"name": "Test Project"}),
    ("GET",    "/api/v1/projects/stub-id/tbds",                     None),
    ("POST",   "/api/v1/projects/stub-id/clarifications",           {"tbd_id": "t1", "action": "TBD"}),
    ("POST",   "/api/v1/projects/stub-id/proposal",                 None),
    ("GET",    "/api/v1/projects/stub-id/proposal",                 None),
    ("POST",   "/api/v1/projects/stub-id/stack",                    None),
    ("POST",   "/api/v1/projects/stub-id/estimate",                 None),
    ("POST",   "/api/v1/projects/stub-id/sync",                     None),
    ("GET",    "/api/v1/projects/stub-id/metrics",                  None),
    ("POST",   "/api/v1/factory/seed-employees",                    None),
    ("POST",   "/api/v1/factory/seed-projects",                     None),
    ("POST",   "/api/v1/factory/seed-technologies",                 None),
    ("POST",   "/api/v1/factory/seed-all",                          None),
    ("DELETE", "/api/v1/factory/reset-db",                          None),
]


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_endpoint_returns_2xx(client, method, path, body):
    resp = getattr(client, method.lower())(path, json=body)
    assert resp.status_code < 300, f"{method} {path} returned {resp.status_code}: {resp.text}"


def test_upload_document(client):
    import io
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
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
cd backend
python -m pytest tests/test_routes.py -v
```

Expected: multiple failures — routes return `None` (FastAPI converts to `null`, which causes validation errors or 500s).

---

- [ ] **Step 4: Implement stubs in `backend/app/routers/projects.py`**

```python
from fastapi import APIRouter, Depends, UploadFile
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


@router.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    # TODO(Epic 5 #35): persist to DB
    return ProjectResponse(
        id="stub-id",
        name=payload.name,
        status="draft",
        current_phase=1,
        created_at="2026-01-01T00:00:00Z",
    )


@router.post("/projects/{project_id}/documents", response_model=DocumentResponse, status_code=201)
def upload_document(
    project_id: str,
    file: UploadFile,
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


@router.get("/projects/{project_id}/tbds", response_model=list[TBDItem])
def get_tbds(
    project_id: str,
    db: Session = Depends(get_db),
) -> list[TBDItem]:
    # TODO(Epic 5 #37): retrieve TBDs from LangGraph state
    return []


@router.post("/projects/{project_id}/clarifications", response_model=ClarificationResponse, status_code=201)
def create_clarification(
    project_id: str,
    payload: ClarificationCreate,
    db: Session = Depends(get_db),
) -> ClarificationResponse:
    # TODO(Epic 5 #40): persist clarification
    return ClarificationResponse(
        id="stub-clarification-id",
        tbd_id=payload.tbd_id,
        action=payload.action,
        answer=payload.answer,
    )


@router.post("/projects/{project_id}/proposal", response_model=ProposalResponse, status_code=201)
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


@router.get("/projects/{project_id}/proposal", response_model=ProposalResponse)
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


@router.post("/projects/{project_id}/stack", response_model=TechStackResponse)
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


@router.post("/projects/{project_id}/estimate", response_model=EstimationResponse)
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


@router.post("/projects/{project_id}/sync", response_model=SyncResponse)
def sync_to_github(
    project_id: str,
    db: Session = Depends(get_db),
) -> SyncResponse:
    # TODO(Epic 5 #39): call GitHub MCP sync tools
    return SyncResponse(synced=0, skipped=0, failed=0, status=SyncStatus.pending)


@router.get("/projects/{project_id}/metrics", response_model=MetricsResponse)
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

- [ ] **Step 5: Implement stubs in `backend/app/routers/factory.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.sync import SeedResult

router = APIRouter(tags=["factory"])


@router.post("/factory/seed-employees", response_model=SeedResult)
def seed_employees(db: Session = Depends(get_db)) -> SeedResult:
    # TODO(Epic 5 #40): seed from Faker with FAKER_SEED
    return SeedResult(seeded=0, status="ok")


@router.post("/factory/seed-projects", response_model=SeedResult)
def seed_projects(db: Session = Depends(get_db)) -> SeedResult:
    # TODO(Epic 5 #40): seed from Faker with FAKER_SEED
    return SeedResult(seeded=0, status="ok")


@router.post("/factory/seed-technologies", response_model=SeedResult)
def seed_technologies(db: Session = Depends(get_db)) -> SeedResult:
    # TODO(Epic 5 #40): seed from Faker with FAKER_SEED
    return SeedResult(seeded=0, status="ok")


@router.post("/factory/seed-all", response_model=SeedResult)
def seed_all(db: Session = Depends(get_db)) -> SeedResult:
    # TODO(Epic 5 #40): seed all tables
    return SeedResult(seeded=0, status="ok")


@router.delete("/factory/reset-db")
def reset_db(db: Session = Depends(get_db)) -> dict:
    # TODO(Epic 5 #35): drop and recreate all tables
    return {"status": "reset"}
```

---

- [ ] **Step 6: Run all tests — verify they pass**

```bash
cd backend
python -m pytest tests/ -v
```

Expected: all tests PASS including:
- `test_schemas.py` (7 tests)
- `test_health.py` (1 test)
- `test_routes.py` (14 parametrised + 4 named = 18 tests)

---

- [ ] **Step 7: Run linter and type checker**

```bash
cd backend
ruff check .
mypy .
```

Expected: both pass. Fix any issues before committing.

---

- [ ] **Step 8: Verify OpenAPI spec**

```bash
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs`. Verify:
- All 15 endpoints visible with correct HTTP methods
- Request/response schemas shown for each endpoint
- `POST /api/v1/projects` shows `ProjectCreate` body and `ProjectResponse` response

Stop the server (`Ctrl+C`).

---

- [ ] **Step 9: Commit and push**

```bash
git add backend/
git commit -m "feat: [E4-T3] typed stub responses on all 15 endpoints + smoke tests

Closes #32"
git push -u origin feat/epic4-task3-stub-responses
```

---

- [ ] **Step 10: Open PR to main**

```bash
gh pr create \
  --repo krishna-kodes/acuity \
  --base main \
  --title "[E4-T3] Typed stub responses on all 15 endpoints" \
  --body "$(cat <<'EOF'
## Summary
All 15 endpoints return typed Pydantic responses. Frontend can now integrate against /docs. Every TODO is tagged with the Epic 5 issue that will implement it.

## Related issues
Closes #32

## Changes
- `routers/projects.py` — 10 stub endpoints with typed response_model
- `routers/factory.py` — 5 stub endpoints with typed response_model
- `tests/test_routes.py` — 18 smoke tests (14 parametrised + 4 named assertions)

## Dependency check
- [x] Task 2 (feat/epic4-task2-fastapi-scaffold) is merged to `main`
- [x] I pulled latest `main` and rebased this branch before opening the PR
- [x] I checked for new issues opened by the other dev that could affect this work

## Testing
- [x] `pytest tests/` — 26 tests pass
- [x] `ruff check .` passes
- [x] `mypy .` passes
- [x] `/docs` shows all 15 endpoints with correct schemas
EOF
)"
```

- [ ] **Step 11: After PR is merged — pull latest main**

```bash
git checkout main && git pull origin main
git branch -d feat/epic4-task3-stub-responses
```
