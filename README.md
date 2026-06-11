# Acuity — AI-Driven Project Management

A PM uploads a requirements document (PDF/DOCX), refines it through an AI chat interface, extracts structured work modules, receives team and tech stack suggestions with effort estimates, then syncs generated epics/tasks to GitHub or Jira.

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
# 5. (Optional) seed demo reference data
make seed          # via API — backend must be running
make seed-offline  # or directly via DB session — no server needed
```

---

## PM workflow / phases

The app guides a PM through 7 sequential phases. Each phase is gated behind the previous; the "Approve & Proceed" button is the only way to advance.

| # | Route | Description |
|---|-------|-------------|
| 1 | `/redaction` | PII detection — regex + spaCy NER + LLM quality filter; PM reviews each detection before advancing |
| 2 | `/chat` | RAG-powered requirements chat with clickable source citations; TBD surfacing (all 4 levels); clarification widget; proposal generation with per-section regeneration |
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
  └─ Phase 1: extract (PyMuPDF→pdfplumber, quality-gated, OCR fallback)
      → PII detection (regex → NER + noise filter → LLM gate) → anonymised text stored
      └─ Phase 2: RAG chat loop
           ├─ Hybrid retrieval: ChromaDB dense (cosine) + BM25 sparse → RRF merge → BERT reranker
           ├─ Query rewriting: 3 sub-queries per user turn
           ├─ Guardrails: domain classifier (reject off-topic) + retrieval gate (block low-confidence)
           ├─ TBD detection: Level 1 (explicit) + Level 2 (vague) + Level 3 (missing sections) + Level 4 (contradictions)
           ├─ Source citations: retrieved chunks (chunk_id, section, page, snippet) streamed as clickable chips → Sources preview panel
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

The reranked chunks are streamed back as the SSE `sources` event (`chunk_id`,
`chunk_index`, `section_hint`, `page_number`, `text`) and persisted on the
assistant message. The UI renders them as clickable citation chips under each
answer; clicking one opens the Sources preview panel and scrolls to / highlights
the cited chunk. Citations survive page reload (they ride the checkpointer's
`chat_messages` JSON — no schema change).

### Guardrails (Phase 2)

Five layers execute in order on every chat turn:

| Layer | Guardrail | Trigger | Behaviour |
|-------|-----------|---------|-----------|
| 0 | **Prompt injection detection** | Before retrieval | Two-pass: (1) regex (29 patterns, unicode-normalised, zero-width stripped) then (2) LLM semantic classifier catches synonym/indirect/encoded bypasses. Blocks on either hit. Flag: `PROMPT_INJECTION_DETECTION_ENABLED`. Threshold: `INJECTION_LLM_CONFIDENCE_THRESHOLD` (default 0.80) |
| 1 | **Domain classifier** | Before retrieval | LLM classifies query; rejects clearly off-topic before retrieval. Flag: `DOMAIN_CLASSIFIER_ENABLED` |
| 2 | **Retrieval gate** | After retrieval | Empty retrieval always blocked (regardless of flag). When `RETRIEVAL_GATE_ENABLED=true`: also checks sigmoid confidence score and chunk provenance |
| 3 | **Groundedness check** | After LLM response | LLM-as-judge scores all claims against retrieved context; flags unsupported claims. Flag: `GROUNDEDNESS_CHECK_ENABLED` |
| 4 | **Output monitor** | After LLM response | Detects canary token leak (system prompt exfiltration). Runtime token embedded in system message; response checked before streaming. Flag: `OUTPUT_MONITOR_ENABLED`. Token: `PROMPT_CANARY_TOKEN` (auto-generated per process if unset) |

Document chunks are also scanned at ingestion time (Layer 0 regex) — flagged chunks logged to `guardrail_logs` but ingestion continues.

**System prompt hardening (Phase 2 LLM context):** Retrieved chunks are wrapped in `<chunk index page section>` XML tags inside a `<document_context>` block. System message explicitly instructs the model to treat document content as data only, never as commands.

### PII detection (Phase 1)

Garbage in = garbage out, so quality is enforced at every stage:

1. **Extraction** — PyMuPDF first (honors the font `ToUnicode` table, avoiding
   ligature/CID corruption like `aWendance`→`attendance`), pdfplumber fallback;
   the higher-quality extraction per page wins. Pages scoring below
   `EXTRACTION_QUALITY_THRESHOLD` (mid-word-caps ratio) attempt OCR
   (`pytesseract`, no-op if the `tesseract` binary is absent).
2. **Regex pass** — email / phone / SSN (`PII_REGEX_ENABLED`).
3. **NER pass** — spaCy `en_core_web_sm` over `PII_NER_LABELS` (default
   `PERSON,ORG,GPE`; narrow to `PERSON` to drop org/place noise). A mechanical
   filter rejects tech acronyms, vendor names, and mid-word-caps garbage.
4. **LLM quality gate** — `PII_AUTO_LLM_FILTER` (default on) pre-prunes NER
   false positives before the PM review screen; the PM can still Undo. Same
   gate is exposed manually as `make pii-filter ID=<n>`.

Originals are Fernet-encrypted (`PII_ENCRYPTION_KEY`); replacement tokens
(`[PERSON_1]`) go into the anonymised text. `PII_REVIEW_GATE=true` holds the
document in `anonymising` until the PM confirms each detection.

> Existing projects don't auto-upgrade — ingestion is cached once detections
> exist and the collection is `ready`. Re-ingest (clear detections + drop the
> collection) to apply the new pipeline to an already-processed document.

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
│   ├── components/              Shared UI (topbar, sidebar, live-status-bar,
│   │                            chat-thread, sources-panel)
│   └── lib/                     api.ts, project-phases.ts, utils
├── backend/
│   ├── app/
│   │   ├── routers/projects.py  All project API endpoints (~2600 lines)
│   │   ├── guardrails/          prompt_injection, domain_classifier, retrieval_gate,
│   │   │                        groundedness, output_monitor
│   │   ├── models/              SQLAlchemy ORM
│   │   ├── schemas/             Pydantic request/response schemas
│   │   ├── services/            workflow.py (LangGraph), rag.py, ingestion.py,
│   │   │                        llm_factory.py, sync_factory.py, proposal_generator.py,
│   │   │                        pii_detection.py, tbd_detection.py, seeder.py, …
│   │   └── mcp/                 github_server.py, jira_server.py (FastMCP)
│   ├── scripts/                 Ops/CLI: vectordb_audit.py, seed_offline.py,
│   │                            import_historical.py
│   ├── fixtures/                historical_projects.sample.csv (import template)
│   ├── alembic/versions/        Migration history
│   └── tests/                   pytest suite
├── evals/                       Eval harness, graders, tool schemas
├── fixtures/                    Stub documents for eval test cases
├── results/                     Eval run output (gitignored)
├── test_cases.json              33 eval tasks with ground truth
├── eval_suite.py                CI gate: python eval_suite.py --threshold 0.90
└── docs/                        Architecture, design handoff, design HTML
```


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
| PDF parsing | PyMuPDF (primary, ToUnicode-aware) + pdfplumber (fallback + tables); optional `pytesseract` OCR |
| PII | regex + spaCy `en_core_web_sm` (NER noise filter) + auto LLM quality gate; Fernet encryption (`PII_ENCRYPTION_KEY`) |
| Orchestration | LangGraph + `SqliteSaver` |
| Sync | GitHub MCP (milestones + issues) via FastMCP; Jira via `atlassian-python-api`; resolved at runtime by `sync_factory.py` |
| Observability | LangSmith (default) — switchable to Langfuse via `OBSERVABILITY_PROVIDER` |
| Guardrails | Domain classifier + retrieval gate + groundedness check + prompt injection detection |

---

## Data stores & maintenance

Three stores share one project lifecycle and **must be reset together**:

| Store | Path | Keyed by | Holds |
|-------|------|----------|-------|
| App DB | `backend/app.db` | `projects.id` | projects, documents, epics, metrics, … |
| Vector DB | `backend/chroma_db/` | collection `project_<id>` | document chunk embeddings |
| Checkpointer | `backend/project_state.db` | `thread_id = <id>` | LangGraph state + chat history |

**Why this matters:** resetting only `app.db` recycles project IDs while the
old `chroma_db/` collection and `project_state.db` thread survive. A reused
project ID then inherits a previous document's embeddings and chat history —
chat answers about the wrong document. These are *orphan* collections.

Both `make db-reset` and the API `DELETE /api/v1/factory/reset-db` now wipe
all three stores atomically, so this can't happen via the normal reset paths.

```bash
make vectordb-audit    # safe: lists orphan collections, exits non-zero if any
make vectordb-prune    # deletes orphans only; keeps valid projects' embeddings
make vectordb-reset    # nuke vector + checkpointer (stop the server first)
```

Run `make vectordb-audit` before a demo to confirm no stale data. If a single
project chats about the wrong document, `make vectordb-prune` clears it without
touching other projects.

**Clean slate.** To wipe all three stores and reseed reference data in one
step (server stopped):

```bash
make fresh    # rm app.db + chroma_db + project_state.db → migrate → seed offline
```

Reference data = employees, historical projects (estimation calibration),
approved technologies. User projects are created by uploading documents in
the UI, not seeded.

### Production historical projects

`make seed` populates `historical_projects` with **Faker** rows — fine for
dev, useless for real estimates. The estimation phase reads this table as
reference data, so in production load your organisation's real past projects
from a CSV:

```bash
# CSV header: name,domain,estimated_points,actual_points,duration_weeks,team_size
make import-historical CSV=path/to/projects.csv            # upsert by name (idempotent)
make import-historical CSV=path/to/projects.csv REPLACE=1  # truncate table first
```

`name` is the upsert key — re-running updates existing rows instead of
duplicating. Other columns are optional (blank → NULL). Sample template:
`backend/fixtures/historical_projects.sample.csv`. For a clean production
load, run `make import-historical CSV=... REPLACE=1` to drop the Faker rows
and insert only real data.

---

## API surface (all routes prefixed `/api/v1/`)

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
make db-reset       DESTRUCTIVE: drop app.db + chroma_db + project_state.db, reapply migrations
make seed           Seed reference data via API (employees, historical projects, technologies) — server must be running
make seed-offline   Seed reference data directly via DB session (no server needed)
make seed-reset     Reset DB (app + vector + checkpointer) then reseed — server must be running
make fresh          DESTRUCTIVE: full wipe + migrate + seed offline (no server needed)
make import-historical  Import real historical projects from CSV (CSV=path [REPLACE=1])
make vectordb-audit Report orphan chroma collections (no matching project row)
make vectordb-prune Delete orphan collections + their checkpointer threads
make vectordb-reset DESTRUCTIVE: wipe chroma_db + project_state.db (stop server first)
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


