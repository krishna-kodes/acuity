# Acuity — AI-Driven Project Management

A capstone AI engineering project. PMs upload requirements documents, refine them through an AI chat interface, receive team and tech stack suggestions, effort estimates, and sync generated epics/tasks to GitHub.

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
# 3. Activate backend venv, then start servers
source backend/.venv/bin/activate
make dev-be   # → http://localhost:8000/docs
make dev-fe   # → http://localhost:3000  (new terminal)
# or: make dev  (both at once, requires: npm i -g concurrently)
```

---

## Project structure

```
acuity/
├── frontend/          Next.js 14 App Router, Tailwind CSS, shadcn/ui
├── backend/           FastAPI + Uvicorn, SQLAlchemy, LangGraph
│   ├── app/mcp/       GitHub MCP tools (FastMCP)
│   ├── app/services/  Sync orchestration
│   └── tests/         pytest suite
├── evals/             Eval harness, graders, tool schemas
├── fixtures/          Stub documents for eval test cases
├── results/           Eval run output (gitignored)
├── test_cases.json    15 eval tasks with ground truth
├── eval_suite.py      CI gate: python eval_suite.py --threshold 0.90
└── docs/              Architecture, design handoff, design html
```

Key docs:
- `CLAUDE.md` — full architecture and non-negotiable rules
- `CONTRIBUTING.md` — branch strategy, pre/post task checklists
- `EPICS_TASKS.md` — implementation plan (Epics 0–6)
- `DESIGN_HANDOFF.md` — UI design file, screen inventory, implementation status
- `TESTING.md` — acceptance criteria and AI engineering metrics coverage
- `BACKEND_GAPS.md` — new endpoints discovered during frontend build
- `.env.example` — all required environment variables

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14+ App Router, Tailwind CSS, shadcn/ui, Recharts |
| Backend | FastAPI + Uvicorn |
| Database | SQLite + SQLAlchemy + Alembic (WAL mode) |
| Vector DB | ChromaDB PersistentClient |
| Embeddings | `text-embedding-3-small` (OpenAI, 1536 dims) |
| Orchestration | LangGraph with SqliteSaver |
| GitHub Sync | GitHub MCP server (milestones + issues) |

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
