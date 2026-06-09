# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Implementation status (June 2026):** Frontend (Next.js 16.2, Tailwind v4) through Epics 0–3 complete. Backend: FastAPI scaffold, SQLite schema (17+ tables + Alembic), ChromaDB ingestion pipeline, GitHub MCP sync, eval harness (33 test cases), structured proposal generator all done. LLM stack: OpenAI `gpt-5.4-nano` (main + fast + structured), `text-embedding-3-small` (embeddings).

> **Design document overrides:** `capstone_project_design_document.md` is the original submission artifact and has not been updated. Where it conflicts with this file, **this file wins**:
> - **Embedding model:** Design doc says `Gemini text-embedding-004` — overridden by ADR-004. Use `text-embedding-3-small` (OpenAI, 1536 dims).
> - **Integration target:** Design doc says Jira via FastMCP — overridden by ADR-001. Use GitHub Issues + Milestones. `tasks.jira_key` → `tasks.github_issue_number`. `/sync-jira` → `/sync`. No Jira code, dependencies, or env vars.

---

## Non-Negotiable Rules

1. **Never use `chromadb.Client()`** — always `chromadb.PersistentClient(path=os.environ["CHROMA_PERSIST_PATH"])`
2. **Never use `MemorySaver`** — always `SqliteSaver` for the LangGraph checkpointer
3. **Never change `EMBEDDING_DIMENSIONS` after ingestion** — requires full re-embedding of all projects. Embedding model is `text-embedding-3-small` (OpenAI, 1536 dims). The design doc incorrectly specifies `Gemini text-embedding-004` — this is overridden here.
4. **All API routes prefixed `/api/v1/`**
5. **Retry logic at LangGraph node level, not FastAPI endpoint level** (exponential backoff, max 3 retries)
6. **`phase_status` dict must be updated in `ProjectState` at every phase transition**
7. **Fernet for PII encryption** — key from `PII_ENCRYPTION_KEY` env var
8. **SQLite WAL mode** — `PRAGMA journal_mode=WAL` on engine init; `check_same_thread=False`
9. **LLM provider switchable via env var** — never hardcode provider names; read from `MAIN_LLM_PROVIDER` / `FAST_LLM_PROVIDER`
10. **Sync provider switchable via `SYNC_PROVIDER` env var** — `github` (default) or `jira`; resolved at runtime via `sync_factory.py`
11. **Two separate SQLite databases** — `app.db` for application data, `project_state.db` for LangGraph checkpoints
12. **Use `langchain-openai` for LLM calls** — main and fast LLM both use `MAIN_LLM_PROVIDER=openai` / `FAST_LLM_PROVIDER=openai`. Models: `gpt-5.4-nano` (main and fast).

---

## Commands

### Backend
```bash
# Run from backend/
cd backend

# Create and activate venv (first time)
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements-dev.txt
python -m spacy download en_core_web_sm

# Run dev server
uvicorn app.main:app --reload --port 8000

# Run all tests
pytest

# Run a single test
pytest tests/path/test_file.py::test_name -v

# Apply migrations
alembic upgrade head

# Generate a new migration
alembic revision --autogenerate -m "description"

# Seed database
curl -X POST http://localhost:8000/api/v1/factory/seed-all

# Generate Fernet PII key (run once, store in .env)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Frontend
```bash
# Run from frontend/
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev        # http://localhost:3000

# Type check
npx tsc --noEmit

# Lint
npm run lint
```

### Evals
```bash
# Run full eval suite
python eval_suite.py --threshold 0.90

# Run a single eval
python -m evals.harness --test-case <id>
```

---

## Architecture

### What This Is

A PM uploads a requirements document (PDF/DOCX), refines it through an AI-assisted chat, receives team/tech stack suggestions and effort estimates, then syncs generated epics/tasks to GitHub. Graded on: system design quality · eval coverage · cost analysis.

### Processing Pipeline

**Phases 1–3** run as a deterministic pipeline. **Phases 4–6** run as a LangGraph ReAct agent.

| Phase | Name | Key Components |
|-------|------|----------------|
| 1 | Document Ingestion | PDF/DOCX parser, structure-aware chunker, `text-embedding-3-small`, ChromaDB |
| 2 | Chat & Refinement | Hybrid RAG (dense ChromaDB + sparse BM25 merged), query rewriting (3 sub-queries), BERT reranker (top-20→top-4), TBD detector, clarification widget, proposal generation |
| 3 | Tech Stack Suggestion | `approved_technologies` tool, employee skills tool, LLM reasoning |
| 4 | Team Suggestion | SQLite employee tool, skills matcher, availability filter |
| 5 | Effort Estimation | Historical projects retrieval, LangGraph state, LLM estimation |
| 6 | Epic & Task Gen + Sync | Pydantic structured output, GitHub MCP server, sync status tracking |

**Phase 2 sub-steps:**
1. RAG chat loop — PM asks questions; TBDs surfaced via LLM
2. Clarification widget — PM responds per TBD item with one of: **Answer / TBD / Out-of-Scope**; each response saved to `clarifications` table
3. Proposal generation — PM clicks "Generate Proposal"; 10-section structured proposal generated via fan-out (`asyncio.gather`). Sections: overview, problem_statement, goals_and_non_goals, target_audience, key_features, technical_requirements, risks_and_mitigations, success_metrics, timeline_and_milestones, open_questions. Stored as `sections_json` in `proposals` table (`template_version="1.0"`); DOCX written to `/documents/`. Per-section regeneration via `POST /proposal/sections/{section_id}/regenerate`. `open_questions` is zero-LLM (direct DB read of TBD clarifications).

**API endpoints for Phase 2:**
```
POST   /api/v1/projects/{id}/clarifications     # submit TBD answers
POST   /api/v1/projects/{id}/proposal           # trigger proposal generation
GET    /api/v1/projects/{id}/proposal           # retrieve generated proposal
```

### LangGraph State

```python
class ProjectState(TypedDict):
    project_id: str
    raw_doc_text: str          # Phase 1
    proposal_state: dict       # Phase 2
    proposal_sections: dict    # Phase 2 — keyed by ProposalSectionId str value
    tbd_items: list            # Phase 2
    tech_stack: dict           # Phase 3
    team_suggestion: dict      # Phase 4
    effort_estimates: dict     # Phase 5
    epics: list                # Phase 6
    metrics: dict              # All phases
    phase_status: dict         # REQUIRED: {"phase_1": "complete", "phase_2": "in_progress", ...}
```

Phase transitions are PM-initiated ("Proceed" button). Phase N cannot start until Phase N-1 `phase_status == "complete"`.

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16.2, Tailwind CSS v4 (`@theme` in `globals.css`), shadcn/ui, Recharts (metrics only) |
| Backend | FastAPI + Uvicorn |
| ORM / DB | SQLAlchemy + SQLite + Alembic |
| Vector DB | ChromaDB `PersistentClient` |
| LLM (main) | `gpt-5.4-nano` via `langchain-openai` — switchable via `MAIN_LLM_PROVIDER` |
| LLM (fast) | `gpt-5.4-nano` — query rewriting, LLM-as-judge |
| LLM (structured) | `gpt-5.4-nano` — estimation + epic generation (Phase 5–6) |
| Embeddings | `text-embedding-3-small`, 1536 dims, cosine distance |
| Sparse retrieval | BM25 (rank-bm25) — merged with dense results before reranker |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` (local, ~500MB) |
| PII | regex + spaCy `en_core_web_sm`, two-pass; Fernet encryption |
| Orchestration | LangGraph + `SqliteSaver` |
| GitHub sync | GitHub MCP (FastMCP) — replaces Jira |
| Observability | LangSmith or Langfuse (env-switchable, decision pending) |
| Seed data | Faker (`seed=42`) |

---

## Key Implementation Details

### ChromaDB Collection Setup

```python
client = chromadb.PersistentClient(path=os.environ["CHROMA_PERSIST_PATH"])
collection = client.get_or_create_collection(
    name=f"project_{project_id}",
    metadata={"hnsw:space": "cosine"},
    embedding_function=OpenAIEmbeddingFunction(
        api_key=os.environ["OPENAI_API_KEY"],
        model_name="text-embedding-3-small",
        dimensions=1536
    )
)
```

### LangGraph Checkpointer

```python
from langgraph.checkpoint.sqlite import SqliteSaver
checkpointer = SqliteSaver.from_conn_string("./project_state.db")
graph = workflow.compile(checkpointer=checkpointer)
```

### Full API Surface

All routes prefixed `/api/v1/`. OpenAPI spec auto-generated at `/docs`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/projects` | Create project |
| POST | `/projects/{id}/documents` | Upload requirements document |
| GET | `/projects/{id}/tbds` | Retrieve detected TBD items |
| POST | `/projects/{id}/clarifications` | Submit TBD clarification answers |
| POST | `/projects/{id}/proposal` | Trigger proposal generation |
| GET | `/projects/{id}/proposal` | Retrieve generated proposal |
| POST | `/projects/{id}/proposal/sections/{section_id}/regenerate` | Regenerate single proposal section |
| GET  | `/projects/{id}/stack` | Get cached tech stack (204 if not generated) |
| POST | `/projects/{id}/stack` | Run tech stack suggestion (non-streaming) |
| POST | `/projects/{id}/stack/stream` | Stream tech stack suggestion (SSE: status → category×4 → rationale → done) |
| POST | `/projects/{id}/estimate` | Run effort estimation |
| POST | `/projects/{id}/estimate/stream` | Stream effort estimation (SSE: status → epic×N → summary → done) |
| POST | `/projects/{id}/epics` | Generate epics and tasks (non-streaming) |
| POST | `/projects/{id}/epics/stream` | Stream epic generation (SSE: status → epic×N → done; cache path replays DB epics) |
| GET | `/projects/{id}/epics` | Retrieve persisted epics with tasks and sync status |
| POST | `/projects/{id}/sync` | Sync epics/tasks to GitHub |
| GET | `/projects/{id}/metrics` | Retrieve project metrics |
| POST | `/factory/seed-employees` | Seed employee data |
| POST | `/factory/seed-projects` | Seed historical projects |
| POST | `/factory/seed-technologies` | Seed approved technologies |
| POST | `/factory/seed-all` | Seed all |
| DELETE | `/factory/reset-db` | Reset database |

---

### GitHub MCP Tools (FastMCP)

Epics → GitHub Milestones. Stories/Tasks → GitHub Issues with labels.

```python
@mcp.tool
def create_github_milestone(repo: str, title: str, description: str, due_date: str) -> dict: ...

@mcp.tool
def create_github_issue(repo: str, title: str, body: str, milestone_number: int,
                        labels: list[str], assignees: list[str]) -> dict: ...

@mcp.tool
def get_github_repo_issues(repo: str, milestone: int) -> list[dict]: ...
```

DB fields: `epics.github_milestone_number INTEGER`, `epics.github_milestone_url VARCHAR`, `tasks.github_issue_number INTEGER`, `tasks.github_issue_url VARCHAR`. Sync status enum: `pending | synced | skipped | failed`.

### Hybrid RAG Retrieval (Phase 2)

Dense and sparse results are merged before the reranker:

1. **Dense** — ChromaDB cosine similarity, top-`TOP_K_RETRIEVAL` (default 20)
2. **Sparse** — BM25 (`rank-bm25`) over the same corpus, top-`TOP_K_RETRIEVAL`
3. **Merge** — Reciprocal Rank Fusion (RRF) or score normalisation to combine both result sets
4. **Rerank** — `cross-encoder/ms-marco-MiniLM-L-6-v2` scores the merged set, top-`TOP_N_RERANK` (default 4) passed to LLM

Query rewriting generates 3 sub-queries per user message (env: `QUERY_REWRITE_COUNT=3`); each sub-query runs the full dense+sparse+rerank pipeline, results de-duplicated by chunk ID before the final top-4 selection.

### Chunking

- Size: 50–800 tokens (env: `CHUNK_SIZE_MIN_TOKENS`, `CHUNK_SIZE_MAX_TOKENS`)
- Strategy: header detection → paragraph fallback → size normalization
- Tables are atomic chunks — never split mid-row
- Chunk metadata: `project_id`, `chunk_index`, `detected_type`, `page_number`, `section_hint`
- Adjacent chunk cosine similarity must be < 0.85

### ChromaDB Abstraction

ChromaDB is the MVP vector store but the architecture treats it as swappable. Isolate all collection access behind a thin adapter so a post-MVP migration to Qdrant or Pinecone requires only an adapter swap:

```python
class VectorStoreAdapter:
    def upsert(self, chunks: list[dict]) -> None: ...
    def query(self, embedding: list[float], top_k: int) -> list[dict]: ...

class ChromaAdapter(VectorStoreAdapter): ...   # MVP implementation
```

Never call ChromaDB client methods directly from phase nodes — always go through the adapter.

### Caching

| What | Method |
|------|--------|
| Document embeddings | Check ChromaDB for `project_id` before re-embedding |
| Phase LLM outputs | Skip if `phase_status == "complete"` |
| Employee DB queries | In-memory dict, loaded once per session |
| Prompts + tool defs | Static content first in prompt (KV cache) |

### PII Detection

Two-pass: regex first (`PII_REGEX_ENABLED`), then spaCy NER (`PII_NER_ENABLED`). Gate controlled by `PII_REVIEW_GATE=true`. TBD detection in Phase 2 covers all 4 levels: Level 1 (explicit), Level 2 (vague), Level 3 (missing sections), Level 4 (contradictions). GitHub milestones #8 and #9 track implementation.

---

## Database Schema

Core tables: `projects`, `documents`, `clarifications`, `proposals`, `proposal_state`, `employees`, `skills`, `employee_skills`, `approved_technologies`, `historical_projects`, `epics`, `tasks`, `pii_detections`, `pii_ingestion_logs`, `metrics`, `latency_logs`, `error_logs`

Key table definitions:
```sql
documents (
  id, project_id, filename, upload_ts,
  anonymized_path, status
)

clarifications (
  id, document_id, question, answer,
  action  -- 'Answer' | 'TBD' | 'Out-of-Scope'
)

proposals (
  id, project_id, document_id,
  content_path, content_json, created_at,
  sections_json,       -- JSON array of 10 structured SectionResponse objects (template_version 1.0+)
  template_version     -- "1.0" for structured proposals; NULL for legacy
)
```

Seed factory endpoints (Swagger-accessible):
```
POST /api/v1/factory/seed-employees
POST /api/v1/factory/seed-projects
POST /api/v1/factory/seed-technologies
POST /api/v1/factory/seed-all
DELETE /api/v1/factory/reset-db
```

---

## Eval Layer

File layout:
```
test_cases.json          # 10–15 eval tasks with ground truth
evals/graders.py         # code-based + semantic graders
evals/harness.py         # HybridRAGAgentEval + EvalResult
results/                 # eval_results_<timestamp>.json
eval_suite.py            # CI gate: python eval_suite.py --threshold 0.90
```

Eval results are synced to Google Drive after each run via rclone:
```bash
rclone copy results/ gdrive:acuity/eval-results/
```
Configure the remote once with `rclone config`; add the sync call at the end of `eval_suite.py`.

```python
@dataclass
class EvalResult:
    test_case_id: str
    grader_name: str
    passed: bool
    score: float
    reasoning: str
    trial: int

class HybridRAGAgentEval:
    def run_eval(self, test_case: dict, n_trials: int = 3) -> list[EvalResult]: ...
    def run_all(self) -> dict: ...
```

Graders, their implementation library, and per-test pass thresholds:

| Grader | Library | Threshold |
|--------|---------|-----------|
| Retrieval source match | RAGAS (`context_recall`) | ≥ 0.80 |
| Answer relevancy | RAGAS (`answer_relevancy`) | ≥ 0.75 |
| Reranker precision improvement | Custom (rank comparison) | ≥ 70% of cases |
| TBD detection — explicit | Custom (exact match) | 100% |
| TBD detection — vague | Custom (LLM-as-judge prompt) | ≥ 0.70 |
| TBD detection — missing sections | Custom (section checklist) | ≥ 0.85 |
| Tool selection accuracy | Custom (`tool_calls[].name` match) | — |
| Loop safety | Custom (`len(tool_calls) <= max_iterations`) | — |
| Tool argument validity | Custom (Pydantic validate) | — |
| Phase ordering compliance | Custom (phase N−1 complete before N) | — |
| Proposal completeness | DeepEval (G-Eval rubric) | ≥ 0.75 |
| Tech stack rationale quality | DeepEval (G-Eval rubric) | ≥ 0.70 |
| Effort estimate plausibility | Custom (range check vs. historical) | ≥ 0.80 |
| GitHub ticket structure validity | Custom (schema check) | 100% |
| Round-trip sync (doc → GitHub) | Custom (end-to-end) | ≥ 0.90 |
| Groundedness | Custom (LLM-as-judge prompt) | ≥ 0.70 (env: `GROUNDEDNESS_THRESHOLD`) |

Metrics: primary is `pass@1`. Dev uses `pass@k`, production uses `pass^k`. CI gate threshold: 90%. Any eval with `pass_rate > 0.80` graduates to regression suite — mark with `# REGRESSION: do not change this prompt without re-running evals/regression_suite.py`.

LLM-as-judge groundedness prompt:
```python
GROUNDEDNESS_JUDGE_PROMPT = """
System: You are an evaluation judge. Answer only with a JSON object.
User:
  Context: {retrieved_chunks}
  Response: {llm_response}
  Question: Is every factual claim in the Response directly supported by the Context?
  Score 0-1 where 1 = fully grounded, 0 = contains unsupported claims.
  Output: {"score": float, "reasoning": str, "unsupported_claims": list[str]}
"""
```

---

## UI Routes

| Screen | Route |
|--------|-------|
| Project Dashboard | `/` |
| New Project / Upload | `/projects/new` |
| Redaction Review | `/projects/[id]/redaction` |
| Chat & Refinement | `/projects/[id]/chat` |
| Tech Stack Review | `/projects/[id]/techstack` |
| Team Suggestion | `/projects/[id]/team` |
| Effort Estimation | `/projects/[id]/estimation` |
| Epic & Task Review | `/projects/[id]/epics` |
| Metrics | `/projects/[id]/metrics` |

Metrics page has 5 tabs:

| Tab | Content |
|-----|---------|
| Token Usage & Cost | Token count and USD cost per LLM call and per session |
| AI Quality | Eval pass rates for proposal completeness (DeepEval scores) |
| Retrieval | Retrieval precision/recall; TBD detection precision/recall across clarification rounds |
| Error Handling | Error rates, retry counts per phase, failed GitHub sync attempts |
| Latency | P50/P95 latency per LangGraph agent node |

GitHub Sync stats (tickets created, sync success/failure rate) surface in the Error Handling tab.

---

## Environment Variables

Copy this to `.env` and fill in values:

```bash
# LLM — available models on this OpenAI key: gpt-5.4-mini, gpt-5.4-nano, text-embedding-3-small
MAIN_LLM_PROVIDER=openai
MAIN_LLM_MODEL=gpt-5.4-nano
FAST_LLM_PROVIDER=openai
FAST_LLM_MODEL=gpt-5.4-nano
TEMPERATURE=0.2

# APIs
OPENAI_API_KEY=
# GOOGLE_API_KEY and ANTHROPIC_API_KEY not used — leave blank or omit

# Sync provider (global default — overridable per-project)
SYNC_PROVIDER=github              # "github" | "jira"

# GitHub MCP
GITHUB_TOKEN=
GITHUB_OWNER=
GITHUB_REPO=
GITHUB_USE_PROJECTS_V2=false

# Jira MCP (required when SYNC_PROVIDER=jira)
JIRA_URL=
JIRA_USERNAME=
JIRA_API_TOKEN=
JIRA_PROJECT_KEY=

# Embeddings (never change EMBEDDING_DIMENSIONS after first ingestion)
EMBEDDING_DIMENSIONS=1536
CHROMA_PERSIST_PATH=./chroma_db

# PII
PII_ENCRYPTION_KEY=
PII_DETECTION_ENABLED=true
PII_REGEX_ENABLED=true
PII_NER_ENABLED=true
PII_REVIEW_GATE=true

# RAG
CHUNK_SIZE_MAX_TOKENS=800
CHUNK_SIZE_MIN_TOKENS=50
TOP_K_RETRIEVAL=20
TOP_N_RERANK=4
QUERY_REWRITE_COUNT=3

# Guardrails
GROUNDEDNESS_THRESHOLD=0.7
GROUNDEDNESS_CHECK_ENABLED=true
HALLUCINATION_FLAG_ENABLED=true
MAX_FILE_SIZE_MB=10
MIN_EXTRACTABLE_CHARS=100
ALLOWED_FILE_TYPES=pdf,docx
PROMPT_INJECTION_DETECTION=true
MAX_COST_PER_WORKFLOW_USD=0.50

# Observability (LangSmith)
OBSERVABILITY_PROVIDER=langsmith
LANGSMITH_API_KEY=
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=acuity

# Seed data
FAKER_SEED=42
SEED_EMPLOYEE_COUNT=20
SEED_PROJECT_COUNT=15
SEED_TECHNOLOGY_COUNT=22

# Metrics
METRICS_ENABLED=true
TOKEN_TRACKING_ENABLED=true
COST_PER_1K_INPUT_TOKENS=0.0015
COST_PER_1K_OUTPUT_TOKENS=0.002

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Add to `.gitignore`: `.env`, `chroma_db/`, `project_state.db`, `app.db`, `documents/`

---

## Open Decisions

| Item | Status |
|------|--------|
| Observability provider | Both LangSmith and Langfuse configured via env — decision pending |
| Google Drive source documents folder path | Not yet recorded — ask Krishna |
| DOCX export versioning (v1, v2) | Not yet specified |

---

## Promoted to MVP (June 2026)

Previously post-MVP; now in-scope. GitHub milestones created.

| Item | Milestone | Issues |
|------|-----------|--------|
| TBD Detection Level 3 — missing sections | #8 | #90–#93 |
| TBD Detection Level 4 — contradictions | #9 | #94–#97 |
| GitHub Projects V2 GraphQL (`GITHUB_USE_PROJECTS_V2=true`) | #10 | #98–#101 |
| Generic Sync Provider — Jira + GitHub abstraction (`sync_factory.py`) | #11 | #102–#108 |

For Jira sync: use `atlassian-python-api` (not `mcp-atlassian` — subprocess-only, not importable). Wrap in `backend/app/mcp/jira_server.py` FastMCP server. Provider resolved at runtime via `backend/app/services/sync_factory.py`. Rule 10 ("GitHub MCP only") is superseded — both GitHub and Jira sync are now in-scope.
