# Acuity — AI-Driven Project Management

A capstone AI engineering project. PMs upload requirements documents, refine them through an AI chat interface, extract structured work modules, receive team and tech stack suggestions, effort estimates, and sync generated epics/tasks to GitHub.

**Project board:** https://github.com/users/krishna-kodes/projects/1

---

## Prerequisites

- Python **3.11.14** — `pyenv install 3.11.14` (reads `.python-version`)
- Node **22.17.0** — `nvm install` (reads `.nvmrc`)
- `OPENAI_API_KEY` and `GOOGLE_API_KEY` (minimum to run)

---

## Local setup

```bash
# 1. Clone and configure env
git clone https://github.com/krishna-kodes/acuity.git
cd acuity
cp .env.example .env
# Fill in at minimum: OPENAI_API_KEY, GOOGLE_API_KEY
# Generate PII key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

```bash
# 2. Install all dependencies (venv + pip lock + spaCy model + npm)
make setup
```

```bash
# 3. Apply database migrations
make db-upgrade
```

```bash
# 4. Activate backend venv, then start servers
source backend/.venv/bin/activate
make dev-be   # → http://localhost:8000/docs
make dev-fe   # → http://localhost:3000  (new terminal)
# or: make dev  (both at once, requires: npm i -g concurrently)
```

```bash
# 5. (Optional) seed demo data — backend must be running
make seed
```

---

## PM workflow / phases

The app guides a PM through 7 sequential phases:

| # | Route | Description |
|---|-------|-------------|
| 1 | `/redaction` | PII detection review — regex + NER + LLM quality filter |
| 2 | `/chat` | RAG-powered requirements chat; TBD surfacing; proposal generation |
| 3 | `/modules` | **Extract work modules** from proposal (LLM-extracted, PM-editable, grouped by label) |
| 4 | `/techstack` | AI tech stack suggestion from approved technology list |
| 5 | `/team` | AI team suggestion matched to skills + availability |
| 6 | `/estimation` | Effort estimation (story points, weeks, per-module breakdown) |
| 7 | `/epics` | Epic + task generation; sync to GitHub Milestones / Issues |

Phase N is gated behind Phase N−1. The "Approve & Proceed" button on each phase is the only way to advance.

---

## Project structure

```
acuity/
├── frontend/                    Next.js 16.2 App Router, Tailwind v4, shadcn/ui
│   ├── app/(app)/projects/[id]/ One directory per phase (redaction, chat, modules, …)
│   ├── components/              Shared UI components
│   └── lib/                     api.ts, project-phases.ts, utils
├── backend/
│   ├── app/
│   │   ├── routers/projects.py  All project API endpoints
│   │   ├── models/              SQLAlchemy ORM (enums, project, sync, …)
│   │   ├── schemas/             Pydantic request/response schemas
│   │   ├── services/            workflow.py (LangGraph), rag.py, ingestion.py, …
│   │   └── mcp/                 GitHub MCP tools (FastMCP)
│   ├── alembic/versions/        Migration history
│   └── tests/                   pytest suite
├── evals/                       Eval harness, graders, tool schemas
├── fixtures/                    Stub documents for eval test cases
├── results/                     Eval run output (gitignored)
├── test_cases.json              15 eval tasks with ground truth
├── eval_suite.py                CI gate: python eval_suite.py --threshold 0.90
└── docs/                        Architecture, design handoff, design HTML
```

Key docs:
- `CLAUDE.md` — full architecture, non-negotiable rules, env var reference
- `CONTRIBUTING.md` — branch strategy, pre/post task checklists
- `EPICS_TASKS.md` — implementation plan (Epics 0–6)
- `DESIGN_HANDOFF.md` — UI design file, screen inventory, implementation status
- `TESTING.md` — acceptance criteria and AI engineering metrics coverage
- `BACKEND_GAPS.md` — endpoint audit log (original gaps; most resolved)
- `.env.example` — all required environment variables

---

## API surface (all routes prefixed `/api/v1/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/projects` | Create project |
| GET | `/projects` | List all projects |
| POST | `/projects/{id}/documents` | Upload requirements document |
| GET | `/projects/{id}/redaction-decisions` | Fetch PII detections |
| PATCH | `/projects/{id}/redaction-decisions` | Submit redaction decisions |
| POST | `/projects/{id}/pii-llm-filter` | LLM quality filter for NER false positives |
| GET | `/projects/{id}/document-status` | Poll document ingestion status |
| POST | `/projects/{id}/chat` | RAG chat turn (SSE streaming) |
| GET | `/projects/{id}/tbds` | Fetch detected TBD items |
| POST | `/projects/{id}/clarifications` | Submit TBD answers |
| POST | `/projects/{id}/proposal` | Generate proposal |
| GET | `/projects/{id}/proposal` | Retrieve latest proposal |
| POST | `/projects/{id}/proposal/retry` | Regenerate with PM feedback |
| POST | `/projects/{id}/proposal/approve` | Approve proposal → advance to Modules |
| GET | `/projects/{id}/export/proposal` | Download proposal as DOCX |
| POST | `/projects/{id}/modules` | LLM-extract work modules from proposal |
| GET | `/projects/{id}/modules` | Retrieve stored modules |
| PATCH | `/projects/{id}/modules` | Save PM edits to modules |
| POST | `/projects/{id}/modules/approve` | Approve modules → advance to Tech Stack |
| POST | `/projects/{id}/stack` | AI tech stack suggestion |
| POST | `/projects/{id}/team` | AI team suggestion |
| PUT | `/projects/{id}/team` | Save confirmed team |
| POST | `/projects/{id}/estimate` | Run effort estimation |
| POST | `/projects/{id}/epics` | Generate epics + tasks |
| GET | `/projects/{id}/epics` | Retrieve stored epics |
| POST | `/projects/{id}/sync` | Sync epics/tasks to GitHub or Jira |
| GET | `/projects/{id}/metrics` | Project observability metrics |
| GET | `/projects/{id}/sync-config` | Retrieve sync provider config |
| PATCH | `/projects/{id}/sync-config` | Update sync provider config |
| POST | `/factory/seed-all` | Seed all demo data |
| DELETE | `/factory/reset-db` | Reset database |

OpenAPI docs available at `http://localhost:8000/docs` when server is running.

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16.2 App Router, Tailwind CSS v4 (`@theme` in `globals.css`), shadcn/ui, Recharts |
| Backend | FastAPI + Uvicorn |
| Database | SQLite + SQLAlchemy + Alembic (WAL mode); two DBs: `app.db` + `project_state.db` |
| Vector DB | ChromaDB `PersistentClient` |
| Embeddings | `text-embedding-3-small` (OpenAI, 1536 dims, cosine) |
| LLM (main) | Gemini 2.5 Pro via `langchain-google-genai` (switchable via `MAIN_LLM_PROVIDER`) |
| LLM (fast) | Gemini 2.5 Flash — query rewriting, LLM-as-judge |
| LLM (structured) | Claude Sonnet — estimation + epic generation |
| Sparse retrieval | BM25 (`rank-bm25`) merged with dense via RRF |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` (local) |
| PII | regex + spaCy `en_core_web_sm` + LLM quality filter; Fernet encryption |
| Orchestration | LangGraph + `SqliteSaver` |
| Sync | GitHub MCP (milestones + issues) + Jira (`atlassian-python-api`) |

---

## Make targets

```
make setup          First-time install (venv + pip + spaCy + npm)
make dev            Start both servers concurrently
make dev-be         FastAPI dev server → http://localhost:8000/docs
make dev-fe         Next.js dev server → http://localhost:3000
make test           Run all tests (pytest + tsc)
make test-be        pytest on backend
make lint           ESLint + Ruff
make typecheck-fe   tsc --noEmit
make db-upgrade     Apply pending Alembic migrations
make db-migrate     Generate new migration (MSG="description")
make db-reset       DESTRUCTIVE: drop app.db and reapply all migrations
make seed           Seed demo employees, projects, technologies
make seed-reset     Reset DB then reseed
make modules-extract  LLM-extract modules for a project (ID=<n>)
make modules-approve  Approve modules and advance phase (ID=<n>)
make pii-filter     Run LLM PII quality filter for a project (ID=<n>)
make evals          Run full eval suite (CI gate at 90%)
make clean          Remove build artifacts and caches
```

---

## Evals

```bash
# Install eval dependencies (separate from backend)
pip install -r evals/requirements.txt

# Offline baseline run (mock mode — no API keys needed)
python eval_suite.py --threshold 0.0 --output results/baseline_eval_run_001.json --no-sync

# Single test case
python -m evals.harness --test-case tc-001

# Full CI gate
python eval_suite.py --threshold 0.90

# Real mode (requires GOOGLE_API_KEY + running backend)
EVAL_MODE=real python eval_suite.py --threshold 0.90
```

---

## Contributing

See `CONTRIBUTING.md` for the full workflow including branch naming, pre/post task checklists, and PR guidelines.
