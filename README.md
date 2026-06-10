# Acuity — AI-Driven Project Management

A PM uploads a requirements document (PDF/DOCX), refines it through an AI chat interface, extracts structured work modules, receives team and tech stack suggestions with effort estimates, then syncs generated epics/tasks to GitHub or Jira.

**Project board:** https://github.com/users/krishna-kodes/projects/1

---

## Prerequisites

- Python **3.11.14** — `pyenv install 3.11.14` (reads `.python-version`)
- Node **22.17.0** — `nvm install` (reads `.nvmrc`)
- `OPENAI_API_KEY` (minimum to run — embeddings + LLM)

---

## Local setup

```bash
# 1. Clone and configure env
git clone https://github.com/krishna-kodes/acuity.git
cd acuity
cp .env.example .env
# Fill in at minimum: OPENAI_API_KEY
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

The app guides a PM through 7 sequential phases. Each phase is gated behind the previous; the "Approve & Proceed" button is the only way to advance.

| # | Route | Description |
|---|-------|-------------|
| 1 | `/redaction` | PII detection — regex + spaCy NER + LLM quality filter; PM reviews each detection before advancing |
| 2 | `/chat` | RAG-powered requirements chat; TBD surfacing (all 4 levels); clarification widget; proposal generation with per-section regeneration |
| 3 | `/modules` | LLM-extracts work modules from proposal; PM can edit, reorder, and label before approving |
| 4 | `/techstack` | AI tech stack suggestion from the approved-technology list; streams category-by-category via SSE |
| 5 | `/team` | AI team suggestion matched to skills and availability; effective availability shown (reduced by active-project load); multi-key sort by match score / availability / active projects |
| 6 | `/estimation` | Effort estimation (story points, weeks, per-module breakdown); streams per-epic via SSE |
| 7 | `/epics` | Epic + task generation streamed via SSE; one-click sync to GitHub Milestones/Issues or Jira |

---

## Architecture

### Processing pipeline

Phases 1–3 run as a deterministic pipeline. Phases 4–7 run as a **LangGraph ReAct agent** with `SqliteSaver` checkpointing.

```
Document upload
  └─ Phase 1: PII detection (regex → NER → LLM filter) → anonymised text stored
      └─ Phase 2: RAG chat loop
           ├─ Hybrid retrieval: ChromaDB dense (cosine) + BM25 sparse → RRF merge → BERT reranker
           ├─ Query rewriting: 3 sub-queries per user turn
           ├─ Guardrails: domain classifier (reject off-topic) + retrieval gate (block low-confidence)
           ├─ TBD detection: Level 1 (explicit) + Level 2 (vague) + Level 3 (missing sections) + Level 4 (contradictions)
           └─ Proposal generation: 10-section fan-out (asyncio.gather), DOCX export
               └─ Phase 3: Work module extraction (LLM-extracted, PM-editable)
                   └─ Phase 4: Tech stack suggestion (approved-technology tool + employee skills)
                       └─ Phase 5: Team suggestion (skills matcher + availability filter)
                           └─ Phase 6: Effort estimation (historical projects + LangGraph state)
                               └─ Phase 7: Epic + task generation → GitHub / Jira sync
```

### Hybrid RAG retrieval (Phase 2)

1. Dense — ChromaDB cosine similarity, top-`TOP_K_RETRIEVAL` (default 20)
2. Sparse — BM25 (`rank-bm25`) over same corpus, top-`TOP_K_RETRIEVAL`
3. Merge — Reciprocal Rank Fusion (RRF)
4. Rerank — `cross-encoder/ms-marco-MiniLM-L-6-v2`, top-`TOP_N_RERANK` (default 4) passed to LLM

### Guardrails (Phase 2)

| Guardrail | Trigger | Behaviour |
|-----------|---------|-----------|
| Domain classifier | Every chat turn | LLM classifies query as `pm_relevant` / `off_topic`; rejects off-topic before retrieval (flag: `DOMAIN_CLASSIFIER_ENABLED`) |
| Retrieval gate | After retrieval | Sigmoid confidence score on retrieved chunks; blocks low-confidence sets before LLM inference (flag: `RETRIEVAL_GATE_ENABLED`) |
| Groundedness check | After LLM response | LLM-as-judge scores all claims against retrieved context; flags unsupported claims (flag: `GROUNDEDNESS_CHECK_ENABLED`) |
| Prompt injection detection | Upload + chat | Regex scan for injection patterns (flag: `PROMPT_INJECTION_DETECTION`) |

### SSE streaming

Every long-running phase has a companion `*/stream` endpoint that emits Server-Sent Events so the UI updates progressively:

| Endpoint | Events emitted |
|----------|---------------|
| `POST /proposal/stream` | `status` → section×10 → `done` |
| `POST /proposal/retry/stream` | same as above |
| `POST /modules/stream` | `status` → module×N → `done` |
| `POST /stack/stream` | `status` → category×4 → `rationale` → `done` |
| `POST /estimate/stream` | `status` → epic×N → `summary` → `done` |
| `POST /epics/stream` | `status` → epic×N → `done`; cache path replays DB epics |
| `GET /live-status/stream` | Phase status heartbeat (replaces polling) |

### LangGraph state

```python
class ProjectState(TypedDict):
    project_id: str
    raw_doc_text: str          # Phase 1
    proposal_state: dict       # Phase 2
    proposal_sections: dict    # Phase 2 — keyed by section ID
    tbd_items: list            # Phase 2
    tech_stack: dict           # Phase 4
    team_suggestion: dict      # Phase 5
    effort_estimates: dict     # Phase 6
    epics: list                # Phase 7
    metrics: dict
    phase_status: dict         # {"phase_1": "complete", "phase_2": "in_progress", …}
```

Phase transitions are PM-initiated. Phase N cannot start until Phase N−1 `phase_status == "complete"`.

---

## Project structure

```
acuity/
├── frontend/                    Next.js 16.2 App Router, Tailwind v4, shadcn/ui
│   ├── app/(app)/projects/[id]/ One directory per phase
│   │   ├── redaction/           PII review UI
│   │   ├── chat/                RAG chat + TBD clarification + proposal
│   │   ├── modules/             Work module editor
│   │   ├── techstack/           Tech stack review
│   │   ├── team/                Team suggestion + effective-availability sort
│   │   ├── estimation/          Effort estimation
│   │   ├── epics/               Epic/task review + sync
│   │   └── metrics/             5-tab observability dashboard
│   ├── components/              Shared UI (topbar, sidebar, live-status-bar)
│   └── lib/                     api.ts, project-phases.ts, utils
├── backend/
│   ├── app/
│   │   ├── routers/projects.py  All project API endpoints (~2600 lines)
│   │   ├── guardrails/          domain_classifier, retrieval_gate, groundedness
│   │   ├── models/              SQLAlchemy ORM
│   │   ├── schemas/             Pydantic request/response schemas
│   │   ├── services/            workflow.py (LangGraph), rag.py, ingestion.py,
│   │   │                        llm_factory.py, sync_factory.py, proposal_generator.py,
│   │   │                        pii_detection.py, tbd_detection.py, seeder.py, …
│   │   └── mcp/                 github_server.py, jira_server.py (FastMCP)
│   ├── alembic/versions/        Migration history
│   └── tests/                   pytest suite
├── evals/                       Eval harness, graders, tool schemas
├── fixtures/                    Stub documents for eval test cases
├── results/                     Eval run output (gitignored)
├── test_cases.json              33 eval tasks with ground truth
├── eval_suite.py                CI gate: python eval_suite.py --threshold 0.90
└── docs/                        Architecture, design handoff, design HTML
```

Key docs:
- `CLAUDE.md` — full architecture, non-negotiable rules, env var reference
- `CONTRIBUTING.md` — branch strategy, pre/post task checklists
- `EPICS_TASKS.md` — implementation plan (Epics 0–6)
- `DESIGN_HANDOFF.md` — UI design file, screen inventory, implementation status
- `TESTING.md` — acceptance criteria and AI engineering metrics coverage
- `BACKEND_GAPS.md` — endpoint audit log
- `.env.example` — all environment variables

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16.2 App Router, Tailwind CSS v4 (`@theme` in `globals.css`), shadcn/ui, Recharts |
| Backend | FastAPI + Uvicorn |
| Database | SQLite + SQLAlchemy + Alembic (WAL mode); two DBs: `app.db` (app data) + `project_state.db` (LangGraph checkpoints) |
| Vector DB | ChromaDB `PersistentClient` |
| Embeddings | `text-embedding-3-small` (OpenAI, 1536 dims, cosine — **never change post-ingestion**) |
| LLM (default) | `gpt-5.4-mini` (main) + `gpt-5.4-nano` (fast) via `langchain-openai` |
| LLM providers | `openai` / `google` / `anthropic` — switchable via `MAIN_LLM_PROVIDER` / `FAST_LLM_PROVIDER` env vars |
| Sparse retrieval | BM25 (`rank-bm25`) merged with dense results via RRF |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` (local, ~500 MB) |
| PII | regex + spaCy `en_core_web_sm` + LLM quality filter; Fernet encryption (`PII_ENCRYPTION_KEY`) |
| Orchestration | LangGraph + `SqliteSaver` |
| Sync | GitHub MCP (milestones + issues) via FastMCP; Jira via `atlassian-python-api`; resolved at runtime by `sync_factory.py` |
| Observability | LangSmith (default) — switchable to Langfuse via `OBSERVABILITY_PROVIDER` |
| Guardrails | Domain classifier + retrieval gate + groundedness check + prompt injection detection |

---

## API surface (all routes prefixed `/api/v1/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/projects` | List all projects |
| POST | `/projects` | Create project |
| GET | `/projects/{id}` | Project detail |
| PATCH | `/projects/{id}/archive` | Archive project |
| PATCH | `/projects/{id}/unarchive` | Unarchive project |
| GET | `/projects/{id}/live-status` | Current phase status (poll) |
| GET | `/projects/{id}/live-status/stream` | Phase status SSE stream |
| POST | `/projects/{id}/documents` | Upload requirements document |
| GET | `/projects/{id}/document-status` | Poll document ingestion status |
| GET | `/projects/{id}/documents/{doc_id}/download` | Download original document |
| DELETE | `/projects/{id}/documents/{doc_id}` | Delete document |
| GET | `/projects/{id}/redaction-decisions` | Fetch PII detections |
| PATCH | `/projects/{id}/redaction-decisions` | Submit redaction decisions |
| POST | `/projects/{id}/pii-llm-filter` | LLM quality filter for NER false positives |
| POST | `/projects/{id}/chat` | RAG chat turn (SSE streaming) |
| GET | `/projects/{id}/tbds` | Fetch detected TBD items |
| POST | `/projects/{id}/clarifications` | Submit TBD clarification answers |
| POST | `/projects/{id}/proposal` | Generate proposal |
| POST | `/projects/{id}/proposal/stream` | Generate proposal (SSE) |
| GET | `/projects/{id}/proposal` | Retrieve latest proposal |
| POST | `/projects/{id}/proposal/retry` | Regenerate proposal with PM feedback |
| POST | `/projects/{id}/proposal/retry/stream` | Regenerate proposal (SSE) |
| POST | `/projects/{id}/proposal/approve` | Approve proposal → advance to Modules |
| DELETE | `/projects/{id}/proposals/{proposal_id}` | Delete a proposal version |
| GET | `/projects/{id}/export/proposal` | Download proposal as DOCX |
| GET | `/projects/{id}/export/estimate` | Download estimation as DOCX |
| POST | `/projects/{id}/modules` | LLM-extract work modules from proposal |
| POST | `/projects/{id}/modules/stream` | Extract modules (SSE) |
| GET | `/projects/{id}/modules` | Retrieve stored modules |
| PATCH | `/projects/{id}/modules` | Save PM edits to modules |
| POST | `/projects/{id}/modules/approve` | Approve modules → advance to Tech Stack |
| GET | `/projects/{id}/stack` | Get cached tech stack (204 if not generated) |
| POST | `/projects/{id}/stack` | AI tech stack suggestion |
| POST | `/projects/{id}/stack/stream` | Tech stack suggestion (SSE) |
| POST | `/projects/{id}/team` | AI team suggestion |
| PUT | `/projects/{id}/team` | Save confirmed team |
| POST | `/projects/{id}/estimate` | Run effort estimation |
| POST | `/projects/{id}/estimate/stream` | Effort estimation (SSE) |
| POST | `/projects/{id}/epics` | Generate epics + tasks |
| POST | `/projects/{id}/epics/stream` | Generate epics + tasks (SSE) |
| GET | `/projects/{id}/epics` | Retrieve stored epics with sync status |
| POST | `/projects/{id}/sync` | Sync epics/tasks to GitHub or Jira |
| GET | `/projects/{id}/sync-config` | Retrieve sync provider config |
| PATCH | `/projects/{id}/sync-config` | Update sync provider (per-project override) |
| GET | `/projects/{id}/metrics` | Project observability metrics |
| POST | `/factory/seed-all` | Seed all demo data |
| DELETE | `/factory/reset-db` | Reset database |

OpenAPI docs at `http://localhost:8000/docs` when server is running.

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

# Real mode (requires OPENAI_API_KEY + running backend)
EVAL_MODE=real python eval_suite.py --threshold 0.90
```

33 test cases covering: retrieval source match, answer relevancy, reranker precision improvement, TBD detection (all 4 levels), tool selection accuracy, loop safety, phase ordering compliance, proposal completeness, tech stack rationale quality, effort estimate plausibility, GitHub ticket structure validity, round-trip sync, and groundedness.

Primary eval metric: `pass@1`. CI gate threshold: 90%.

---

## Contributing

See `CONTRIBUTING.md` for the full workflow including branch naming, pre/post task checklists, and PR guidelines.
