# Epic 4 (T1–T3): Backend Scaffold & Stub Endpoints — Spec

**Goal:** Scaffold the FastAPI backend with a full layered structure, formalise the API contract in code, and implement typed stub responses on all 14 endpoints so the frontend can integrate immediately.

**Issues:** #30 (API contracts), #31 (FastAPI scaffold), #32 (stub responses)

**Endpoint count:** 15 total (10 project routes + 5 factory routes). The parametrised smoke test covers 14; `POST /projects/{id}/documents` (file upload) has its own test using `files=`.

**Branch:** `feat/epic4-task1-api-contracts` → `feat/epic4-task2-fastapi-scaffold` → `feat/epic4-task3-stub-responses`

**Runtime:** Python 3.11, FastAPI, Uvicorn, SQLAlchemy, pydantic-settings, ruff, mypy, pytest

---

## Folder structure

```
backend/
├── app/
│   ├── main.py                  # FastAPI app, CORS, router registration, /health
│   ├── config.py                # pydantic-settings Settings class, reads .env
│   ├── database.py              # SQLAlchemy engine (WAL mode), SessionLocal, get_db()
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── projects.py          # 10 project endpoints
│   │   └── factory.py           # 5 factory/seed endpoints
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── project.py           # ProjectCreate, ProjectResponse
│   │   ├── document.py          # DocumentResponse
│   │   ├── clarification.py     # ClarificationCreate, ClarificationResponse
│   │   ├── proposal.py          # ProposalResponse
│   │   ├── sync.py              # SyncResponse, SyncStatus enum
│   │   └── metrics.py           # MetricsResponse
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── base.py              # SQLAlchemy declarative Base (no tables yet)
│   │
│   └── services/
│       └── __init__.py          # empty — Epic 5 fills this in
│
├── tests/
│   ├── conftest.py              # TestClient fixture, in-memory SQLite override
│   └── test_routes.py           # smoke tests: all 14 endpoints return 2xx
│
├── requirements.txt
├── requirements-dev.txt
├── ruff.toml
└── mypy.ini
```

---

## API contract (#30)

All 14 endpoints formalised as router stubs. OpenAPI spec at `/docs` is the living contract — frontend reads it, not a static file.

### `routers/projects.py`

| Method | Path | Status | Schema |
|--------|------|--------|--------|
| POST | `/api/v1/projects` | 201 | `ProjectCreate` → `ProjectResponse` |
| POST | `/api/v1/projects/{id}/documents` | 201 | `UploadFile` → `DocumentResponse` |
| GET | `/api/v1/projects/{id}/tbds` | 200 | → `list[TBDItem]` |
| POST | `/api/v1/projects/{id}/clarifications` | 201 | `ClarificationCreate` → `ClarificationResponse` |
| POST | `/api/v1/projects/{id}/proposal` | 201 | → `ProposalResponse` |
| GET | `/api/v1/projects/{id}/proposal` | 200 | → `ProposalResponse` |
| POST | `/api/v1/projects/{id}/stack` | 200 | → `TechStackResponse` |
| POST | `/api/v1/projects/{id}/estimate` | 200 | → `EstimationResponse` |
| POST | `/api/v1/projects/{id}/sync` | 200 | → `SyncResponse` |
| GET | `/api/v1/projects/{id}/metrics` | 200 | → `MetricsResponse` |

### `routers/factory.py`

| Method | Path | Status | Schema |
|--------|------|--------|--------|
| POST | `/api/v1/factory/seed-employees` | 200 | → `SeedResult` |
| POST | `/api/v1/factory/seed-projects` | 200 | → `SeedResult` |
| POST | `/api/v1/factory/seed-technologies` | 200 | → `SeedResult` |
| POST | `/api/v1/factory/seed-all` | 200 | → `SeedResult` |
| DELETE | `/api/v1/factory/reset-db` | 200 | → `{"status": "reset"}` |

---

## FastAPI scaffold (#31)

### `app/main.py`
```python
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

### `app/config.py`
Typed settings via `pydantic-settings`. All variables from `CLAUDE.md §5` declared with defaults where safe:
```python
class Settings(BaseSettings):
    main_llm_provider: str = "google"
    main_llm_model: str = "gemini-1.5-pro"
    fast_llm_provider: str = "google"
    fast_llm_model: str = "gemini-1.5-flash"
    temperature: float = 0.2
    openai_api_key: str
    google_api_key: str
    anthropic_api_key: str = ""
    github_token: str
    github_owner: str
    github_repo: str
    github_use_projects_v2: bool = False
    embedding_dimensions: int = 1536
    chroma_persist_path: str = "./chroma_db"
    pii_encryption_key: str
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

### `app/database.py`
SQLAlchemy engine with WAL mode (ADR-007). No tables created here — Alembic handles migrations in Epic 5.
```python
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

## Stub responses (#32)

### Stub rules
- Every endpoint declares `response_model` — no bare `dict` returns except factory endpoints
- `POST` endpoints return `201`, all others `200`
- Stub return values match the declared schema with placeholder data
- No database reads or writes — all stubs return hardcoded values
- `db: Session = Depends(get_db)` declared on every router function so Epic 5 can add DB logic without signature changes

### Key schemas

**`schemas/project.py`**
```python
class ProjectCreate(BaseModel):
    name: str

class ProjectResponse(BaseModel):
    id: str
    name: str
    status: str           # draft | active | complete
    current_phase: int    # 1–6
    created_at: str       # ISO datetime string

class TBDItem(BaseModel):
    id: str
    question: str
    level: int            # 1 = explicit, 2 = vague
    resolved: bool
```

**`schemas/document.py`**
```python
class DocumentResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    status: str           # uploaded | anonymising | ready
    upload_ts: str
```

**`schemas/clarification.py`**
```python
class ClarificationCreate(BaseModel):
    tbd_id: str
    action: str           # Answer | TBD | Out-of-Scope
    answer: str | None = None

class ClarificationResponse(BaseModel):
    id: str
    tbd_id: str
    action: str
    answer: str | None
```

**`schemas/sync.py`**
```python
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
```

**`schemas/project.py`** (continued)
```python
class TechStackResponse(BaseModel):
    frontend: list[str]
    backend: list[str]
    database: list[str]
    infra: list[str]
    rationale: str

class EstimationResponse(BaseModel):
    epics: list[dict]           # [{title, estimated_points, confidence}]
    total_points: int
    total_weeks: float
```

**`schemas/metrics.py`**
```python
class MetricsResponse(BaseModel):
    total_tokens: int
    total_cost_usd: float
    phase_latencies: dict[str, float]   # phase_name → p50 ms
    eval_pass_rate: float
    github_sync_success_rate: float
```

**Factory schema**
```python
class SeedResult(BaseModel):
    seeded: int
    status: str
```

### Stub implementation pattern (all 14 endpoints follow this)
```python
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
```

---

## Tests (#32)

### `tests/conftest.py`
```python
@pytest.fixture
def client():
    app.dependency_overrides[get_db] = lambda: None   # no DB needed for stubs
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

### `tests/test_routes.py`
Parametrised smoke test covering all 14 endpoints:
```python
ENDPOINTS = [
    ("POST",   "/api/v1/projects",                          {"name": "Test"}),
    ("POST",   "/api/v1/projects/stub-id/clarifications",   {"tbd_id": "t1", "action": "TBD"}),
    ("POST",   "/api/v1/projects/stub-id/proposal",         None),
    ("GET",    "/api/v1/projects/stub-id/proposal",         None),
    ("POST",   "/api/v1/projects/stub-id/stack",            None),
    ("POST",   "/api/v1/projects/stub-id/estimate",         None),
    ("POST",   "/api/v1/projects/stub-id/sync",             None),
    ("GET",    "/api/v1/projects/stub-id/metrics",          None),
    ("GET",    "/api/v1/projects/stub-id/tbds",             None),
    ("POST",   "/api/v1/factory/seed-employees",            None),
    ("POST",   "/api/v1/factory/seed-projects",             None),
    ("POST",   "/api/v1/factory/seed-technologies",         None),
    ("POST",   "/api/v1/factory/seed-all",                  None),
    ("DELETE", "/api/v1/factory/reset-db",                  None),
]

@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_endpoint_returns_2xx(client, method, path, body):
    resp = getattr(client, method.lower())(path, json=body)
    assert resp.status_code < 300
```

Note: `POST /api/v1/projects/{id}/documents` (file upload) is tested separately with `files=` rather than `json=`.

---

## `requirements.txt`
```
fastapi==0.111.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.30
pydantic-settings==2.2.1
python-multipart==0.0.9
```

## `requirements-dev.txt`
```
-r requirements.txt
pytest==8.2.0
httpx==0.27.0
ruff==0.4.4
mypy==1.10.0
```

---

## Definition of done

- `uvicorn app.main:app --reload` starts without errors
- `GET /health` returns `{"status": "ok"}`
- `GET /docs` shows all 14 endpoints with correct schemas
- `pytest` passes (all 14 smoke tests + file upload test green)
- `ruff check .` passes
- `mypy .` passes
- No `TODO` left untagged with the Epic 5 issue number
