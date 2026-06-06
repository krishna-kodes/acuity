# Acuity — AI-Driven Project Management

A capstone AI engineering project. PMs upload requirements documents, refine them through an AI chat interface, receive team and tech stack suggestions, effort estimates, and sync generated epics/tasks to GitHub.

**Project board:** https://github.com/users/krishna-kodes/projects/1

---

## Prerequisites

- Node 20+ �� use `nvm use` (reads `.nvmrc`)
- Python 3.11+ — use `pyenv` (reads `.python-version`)
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
# 2. Frontend
cd frontend
nvm use
npm install
npm run dev
# → http://localhost:3000
```

```bash
# 3. Backend (new terminal)
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
# → http://localhost:8000/docs
```

---

## Project structure

```
acuity/
├── frontend/          Next.js 14 App Router, Tailwind CSS, shadcn/ui
├── backend/           FastAPI + Uvicorn, SQLAlchemy, LangGraph
├── evals/             Eval harness, graders, test cases
├── results/           Eval run output (gitignored)
└── docs/              Architecture, design handoff, design html
```

Key docs:
- `CLAUDE.md` — full architecture and non-negotiable rules
- `CONTRIBUTING.md` — branch strategy, pre/post task checklists
- `EPICS_TASKS.md` — implementation plan (Epics 0–6)
- `DESIGN_HANDOFF.md` — UI design file and screen inventory
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

## Contributing

See `CONTRIBUTING.md` for the full workflow including branch naming, pre/post task checklists, and PR guidelines.
