# Capstone Project Design Document — v2

**Project:** AI-Driven Project Management Tool  
**Author:** Krishna Kumar  
**Version:** 2.0 (June 2026 — Week 11, Evals phase)  
**Status:** Living document. Where this file conflicts with `CLAUDE.md`, **CLAUDE.md wins**.

---

## 1. Executive Summary

A Hybrid RAG + LangGraph Agent system that assists project managers in transforming unstructured requirements documents into structured, actionable project artifacts. A PM uploads source documents, refines them through an AI-assisted chat interface, receives AI-generated team and tech stack recommendations with effort estimates, and syncs the resulting epics and tasks directly to **GitHub Issues and Milestones** via a FastMCP integration.

The system is graded on three axes: **system design quality · eval coverage · cost analysis**.

Designed around production-grade AI engineering principles: configurable guardrails, a custom evaluation harness, observability instrumentation, and a multi-layer RAG + agent architecture that mirrors real-world deployment patterns.

---

## 2. Problem Statement

Project managers routinely spend significant time manually extracting requirements, identifying gaps, estimating effort, and decomposing work into tickets — a process that is error-prone and heavily dependent on individual experience. Existing PM tools offer templates and structure but no intelligent augmentation of the requirements refinement process itself.

**Core gaps addressed:**

- Requirements documents contain ambiguity (TBDs, vague language) that propagates into poor sprint planning
- Tech stack and team composition decisions are made informally, without leveraging historical data on employee skills or approved technologies
- Effort estimation lacks grounding in historical actual vs. estimated story points
- Manual ticket creation is a high-friction, low-value task

---

## 3. Goals & Non-Goals

### Goals

- Parse and analyze uploaded requirements documents to detect TBDs at two levels (MVP): explicit flags and vague statements
- Drive an AI-assisted clarification loop using a structured UI (Answer / TBD / Out-of-Scope per question)
- Generate a new structured proposal document from refined source material
- Recommend a tech stack and team composition based on requirements, employee skill profiles, and an approved technologies list
- Estimate effort per epic/story informed by historical estimated vs. actual story point data
- Sync generated epics and tasks to **GitHub** (Milestones + Issues) via a FastMCP server integration
- Expose real-time cost, latency, and task-specific eval metrics per project
- Support multiple projects with SQLite-backed session state persistence

### Non-Goals (MVP)

- In-place editing of uploaded source documents (system generates a new proposal document)
- Real-time collaborative editing
- Fine-tuned models (system uses prompt engineering + RAG over pretrained LLMs)
- Multi-agent orchestration — post-MVP

---

## 4. System Architecture

### 4.1 High-Level Flow

```
PM uploads requirements doc
        │
        ▼
PII Anonymization (regex + spaCy NER → PM review gate)
        │
        ▼
Document chunking + embedding → ChromaDB vector store
        │
        ▼
Hybrid RAG retrieval (dense ChromaDB + sparse BM25, merged via RRF, BERT cross-encoder reranking)
        │
        ▼
TBD Detection (LangGraph) — Level 1 (explicit) + Level 2 (vague)
        │
        ▼
Clarification UI (Answer / TBD / Out-of-Scope per TBD item)
        │
        ▼
Proposal Document Generation (new structured document, not in-place edit)
        │
        ├──► Tech Stack + Team Suggestion Agent
        │         (requirements + skills DB + approved tech list)
        │
        ├──► Effort Estimation Agent
        │         (historical story point data)
        │
        └──► GitHub Sync via FastMCP
                  (epics → Milestones; stories/tasks → Issues with labels)
```

### 4.2 Phase Summary

**Phases 1–3** run as a deterministic pipeline. **Phases 4–6** run as a LangGraph ReAct agent.

| Phase | Name | Key Components |
|-------|------|----------------|
| 1 | Document Ingestion | PDF/DOCX parser, structure-aware chunker, `text-embedding-3-small`, ChromaDB |
| 2 | Chat & Refinement | Hybrid RAG (dense + sparse BM25 merged via RRF), query rewriting (3 sub-queries), BERT reranker (top-20→top-4), TBD detector, clarification widget, proposal generation |
| 3 | Tech Stack Suggestion | `approved_technologies` tool, employee skills tool, LLM reasoning |
| 4 | Team Suggestion | SQLite employee tool, skills matcher, availability filter |
| 5 | Effort Estimation | Historical projects retrieval, LangGraph state, LLM estimation |
| 6 | Epic & Task Gen + Sync | Pydantic structured output, GitHub MCP server, sync status tracking |

Phase transitions are **PM-initiated** ("Proceed" button). Phase N cannot start until Phase N-1 `phase_status == "complete"`. Backend enforces this with `HTTP 409` if the client tries to skip ahead.

### 4.3 Component Breakdown

| Layer | Component | Technology |
|-------|-----------|-----------|
| Frontend | Chat UI, structured clarification widget, metrics dashboard | Next.js 16.2, Tailwind CSS v4 (`@theme` in `globals.css`), shadcn/ui, Recharts |
| Backend | REST API, agent orchestration | FastAPI + Uvicorn |
| Vector Store | Chunk storage and retrieval | ChromaDB `PersistentClient` behind `VectorStoreAdapter` |
| Relational Store | Session state, project metadata, historical data | SQLite + SQLAlchemy + Alembic (WAL mode) |
| LLM (main) | Inference | Gemini 2.5 Pro via `google-genai` SDK (`langchain-google-genai`) — switchable via `MAIN_LLM_PROVIDER` |
| LLM (fast) | Query rewriting, LLM-as-judge | Gemini 2.5 Flash — switchable via `FAST_LLM_PROVIDER` |
| LLM (structured) | Estimation + epic generation | Claude Sonnet (Phases 5–6, optional) |
| LLM Factory | Provider abstraction | LangChain factory pattern — env-var driven |
| Reranker | Cross-encoder reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` (local BERT, ~500MB) |
| Sparse retrieval | BM25 hybrid | `rank-bm25` — merged with dense results before reranker |
| Orchestration | Agent + state machine | LangGraph + `SqliteSaver` checkpointer (`project_state.db`) |
| GitHub Integration | Epic/task sync | FastMCP server (replaces Jira) |
| PII | Detection + encryption | regex + spaCy `en_core_web_sm`, Fernet symmetric encryption |
| Observability | Traces, spans, LLM call logs | LangSmith or Langfuse (env-configurable via `OBSERVABILITY_PROVIDER`) |
| Seed Data | Demo/test data generation | Faker (`seed=42`) via Swagger factory endpoints |

---

## 5. Key Design Decisions

### ADR-001: GitHub is default sync target; Jira supported via provider abstraction

GitHub Issues + Milestones is the default sync target. Jira is now in-scope as an optional provider via `sync_factory.py` (milestone #11). Per-project `sync_provider` + `sync_config` fields on the Project model control which target is used.

| Concept | GitHub | Jira |
|---------|--------|------|
| Epic | Milestone | Issue type `Epic` |
| Story / Task | Issue with label + milestone ref | Issue type `Story` with `parent.key = epic_key` |

**GitHub DB fields:** `epics.github_milestone_number INTEGER`, `epics.github_milestone_url VARCHAR`, `tasks.github_issue_number INTEGER`, `tasks.github_issue_url VARCHAR`.  
**Jira DB fields:** `epics.jira_epic_id VARCHAR`, `epics.jira_epic_url VARCHAR`, `tasks.jira_issue_id VARCHAR`, `tasks.jira_issue_url VARCHAR`.  
**Project-level config:** `projects.sync_provider VARCHAR(50)`, `projects.sync_config JSON`.  
**Env vars (GitHub):** `GITHUB_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO`.  
**Env vars (Jira):** `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`.  
**Env vars (global default):** `SYNC_PROVIDER=github` (overridable per-project).  
**Flag:** `GITHUB_USE_PROJECTS_V2=true` now in-scope (milestone #10). Jira library: `atlassian-python-api` (not `mcp-atlassian` — subprocess-only).

### ADR-002: SqliteSaver replaces MemorySaver

```python
from langgraph.checkpoint.sqlite import SqliteSaver
checkpointer = SqliteSaver.from_conn_string("./project_state.db")
graph = workflow.compile(checkpointer=checkpointer)
```

`project_state.db` is kept separate from `app.db`.

### ADR-003: ChromaDB PersistentClient — always

```python
import chromadb
client = chromadb.PersistentClient(path=os.environ["CHROMA_PERSIST_PATH"])
```

Never use `chromadb.Client()`. ChromaDB is treated as swappable behind a `VectorStoreAdapter` — migrating to Qdrant or Pinecone requires only an adapter swap.

```python
class VectorStoreAdapter:
    def upsert(self, chunks: list[dict]) -> None: ...
    def query(self, embedding: list[float], top_k: int) -> list[dict]: ...

class ChromaAdapter(VectorStoreAdapter): ...   # MVP implementation
```

### ADR-004: Embedding contract locked

- Model: `text-embedding-3-small` (OpenAI)
- Dimensions: `1536` (`EMBEDDING_DIMENSIONS=1536`)
- Distance: `cosine`
- **Changing dimensions after ingestion requires full re-embedding. Do not do this.**

> Note: The original design document specified `Gemini text-embedding-004`. This is overridden. Use OpenAI only.

### ADR-005: Phase status + retry logic

Every phase node updates `phase_status` in `ProjectState`. Retry logic (exponential backoff, max 3 retries) lives at the LangGraph node level, not the FastAPI endpoint level.

### ADR-006: PII encryption

Fernet symmetric encryption via `cryptography` library. Key in `.env` as `PII_ENCRYPTION_KEY`.

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### ADR-007: Concurrency model (MVP)

Sequential phase transitions within a project. No concurrent project processing. SQLite WAL mode: `PRAGMA journal_mode=WAL`. Engine: `create_engine("sqlite:///./app.db", connect_args={"check_same_thread": False})`.

### ADR-008: Phase transition rules

- All transitions are PM-initiated via explicit "Proceed" button
- Phase N cannot start until Phase N-1 `phase_status == "complete"`
- Backend enforces with `HTTP 409 { "detail": "Phase N-1 not complete" }`
- PM can navigate backward to review but cannot re-run a completed phase without explicit "Re-run Phase" action

### ADR-009: TBD detection scope (MVP)

- Level 1 (explicit TBDs): literal "TBD", "TODO", "N/A"
- Level 2 (vague statements): imprecise language without measurable criteria
- Levels 3 (missing sections) and 4 (contradictions) are post-MVP

### ADR-010: Model usage strategy

- **Nano/Flash:** RAG retrieval, query rewriting, basic agent loops
- **Pro:** Main reasoning, proposal generation, tech stack + team suggestions
- **Claude Sonnet (optional):** Structured output for estimation + epic generation (Phases 5–6)

### ADR-011: SDK — `google-genai` only

Use `google-genai` SDK with `langchain-google-genai` for LangChain integration. `google-generativeai` is deprecated/EOL. Models: `gemini-2.5-pro` (main), `gemini-2.5-flash` (fast).

---

## 6. Data Model

### 6.1 Relational (SQLite — `app.db`)

17 tables total:

```sql
projects (
  id, name, domain, created_at, status, current_phase,
  tech_stack JSON, team_suggestion JSON, effort_estimates JSON
)

documents (
  id, project_id, filename, upload_ts, anonymized_path, status
)

clarifications (
  id, document_id, question, answer,
  action  -- 'Answer' | 'TBD' | 'Out-of-Scope'
)

proposals (
  id, project_id, document_id, content_path, created_at
)

proposal_state (
  id, project_id, content JSON, version, created_at
)

epics (
  id, project_id, title, description, estimated_points, actual_points,
  github_milestone_number INTEGER,
  github_milestone_url VARCHAR,
  sync_status  -- 'pending' | 'synced' | 'skipped' | 'failed'
)

tasks (
  id, epic_id, title, description, assignee, points,
  github_issue_number INTEGER,
  github_issue_url VARCHAR,
  sync_status  -- 'pending' | 'synced' | 'skipped' | 'failed',
  sync_error VARCHAR
)

employees (
  id, name, seniority
)

skills (
  id, name, category
)

employee_skills (
  employee_id, skill_id, proficiency_level
)

approved_technologies (
  id, name, category, tags JSON
)

historical_projects (
  id, name, domain, estimated_points, actual_points, tech_stack JSON, team_size, duration_weeks
)

pii_detections (
  id, document_id, original, type, method, placeholder, confidence, decision
)

pii_ingestion_logs (
  id, document_id, total_detected, confirmed, overridden, created_at
)

metrics (
  id, project_id, phase, input_tokens, output_tokens, cost_usd, created_at
)

latency_logs (
  id, project_id, phase, node_name, duration_ms, created_at
)

error_logs (
  id, project_id, phase, error_code, message, retries, created_at
)
```

### 6.2 LangGraph State Database (`project_state.db`)

Managed entirely by `SqliteSaver`. Not an application table — do not query directly.

### 6.3 Vector Store (ChromaDB)

- Collection per project: `project_{project_id}`
- Embedding model: `text-embedding-3-small` (OpenAI, 1536 dims, cosine distance)
- Chunk metadata: `project_id`, `chunk_index`, `detected_type`, `page_number`, `section_hint`

### 6.4 LangGraph State Object

```python
class ProjectState(TypedDict):
    project_id: str
    raw_doc_text: str          # Phase 1
    proposal_state: dict       # Phase 2
    tbd_items: list            # Phase 2
    tech_stack: dict           # Phase 3
    team_suggestion: dict      # Phase 4
    effort_estimates: dict     # Phase 5
    epics: list                # Phase 6
    metrics: dict              # All phases
    phase_status: dict         # REQUIRED: {"phase_1": "complete", "phase_2": "in_progress", ...}
```

---

## 7. Agent Design

### 7.1 Hybrid RAG Retrieval (Phase 2)

Query rewriting generates 3 sub-queries per user message (`QUERY_REWRITE_COUNT=3`). Each sub-query runs the full pipeline below, with results de-duplicated by chunk ID:

1. **Dense** — ChromaDB cosine similarity, top-`TOP_K_RETRIEVAL` (default 20)
2. **Sparse** — BM25 (`rank-bm25`) over same corpus, top-`TOP_K_RETRIEVAL`
3. **Merge** — Reciprocal Rank Fusion (RRF)
4. **Rerank** — `cross-encoder/ms-marco-MiniLM-L-6-v2`, top-`TOP_N_RERANK` (default 4) passed to LLM

### 7.2 TBD Detection (Phase 2 sub-step)

LangGraph nodes: `detect_explicit` → `detect_vague` → `detect_missing_sections` → `detect_contradictions` → `aggregate` → `output`

Each node produces `TBDItem` objects consumed by the clarification UI.

| Level | Type | Grader target |
|-------|------|---------------|
| 1 | Explicit (literal TBD/TODO/N/A) | 100% exact match |
| 2 | Vague statements | ≥ 0.70 LLM-as-judge |
| 3 | Missing sections | ≥ 0.85 section checklist |
| 4 | Contradictions | LLM-as-judge (threshold post-baseline) |

GitHub milestones: Level 3 → #8, Level 4 → #9.

### 7.3 Phase 2 Sub-Steps

1. **RAG chat loop** — PM asks questions; TBDs surfaced via LLM
2. **Clarification widget** — PM responds per TBD: Answer / TBD / Out-of-Scope; each saved to `clarifications` table
3. **Proposal generation** — PM clicks "Generate Proposal"; fresh structured proposal created from refined requirements; stored in `proposals` table; DOCX written to `/documents/`

### 7.4 Tech Stack Suggestion Agent (Phase 3)

Inputs: refined requirements text, employee skill profiles, approved technologies list  
Output: recommended stack with rationale per layer

### 7.5 Effort Estimation Agent (Phase 5)

Inputs: epics/stories list, historical story point data (estimated vs. actual per category)  
Output: point estimate per story with confidence interval (low/mid/high)

### 7.6 Sync via FastMCP (Phase 6)

Provider resolved at runtime by `sync_factory.py`. Default: GitHub. Optional: Jira.

**GitHub MCP tools (`backend/app/mcp/github_server.py`):**
```python
@mcp.tool
def create_github_milestone(repo: str, title: str, description: str, due_date: str) -> dict: ...

@mcp.tool
def create_github_issue(repo: str, title: str, body: str, milestone_number: int,
                        labels: list[str], assignees: list[str]) -> dict: ...

@mcp.tool
def get_github_repo_issues(repo: str, milestone: int) -> list[dict]: ...
```

**Jira MCP tools (`backend/app/mcp/jira_server.py`):**
```python
@mcp.tool
def create_jira_epic(project_key: str, title: str, description: str) -> dict: ...

@mcp.tool
def create_jira_issue(project_key: str, title: str, body: str,
                      epic_key: str, labels: list[str]) -> dict: ...

@mcp.tool
def get_jira_project_issues(project_key: str, epic_key: str) -> list[dict]: ...
```

Sync status tracked per epic and per task: `pending | synced | skipped | failed`. Per-item `sync_error` stored for inline error display in UI.

---

## 8. API Surface (FastAPI)

All routes prefixed `/api/v1/`. OpenAPI spec auto-generated at `/docs` — treat as source of truth for frontend contract.

All error responses: `{ "detail": string }` — FastAPI default, matches frontend `ErrorBanner`.

### Core Routes

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/projects` | Create project |
| GET | `/api/v1/projects` | List projects (dashboard) |
| GET | `/api/v1/projects/{id}` | Get project detail |
| POST | `/api/v1/projects/{id}/documents` | Upload requirements document |
| PATCH | `/api/v1/projects/{id}/redaction-decisions` | Submit PII redaction decisions |
| GET | `/api/v1/projects/{id}/pii_detections` | Retrieve PII detections |
| GET | `/api/v1/projects/{id}/tbds` | Retrieve detected TBD items |
| POST | `/api/v1/projects/{id}/chat` | Phase 2 RAG message (SSE streaming) |
| POST | `/api/v1/projects/{id}/clarifications` | Submit TBD clarification answers |
| POST | `/api/v1/projects/{id}/proposal` | Trigger proposal generation |
| GET | `/api/v1/projects/{id}/proposal` | Retrieve generated proposal |
| GET | `/api/v1/projects/{id}/stack` | Retrieve tech stack suggestion |
| POST | `/api/v1/projects/{id}/stack` | Run tech stack suggestion |
| GET | `/api/v1/projects/{id}/team` | Retrieve team suggestion |
| GET | `/api/v1/projects/{id}/estimate` | Retrieve effort estimates |
| POST | `/api/v1/projects/{id}/estimate` | Run effort estimation |
| GET | `/api/v1/projects/{id}/epics` | Retrieve epics + tasks |
| POST | `/api/v1/projects/{id}/sync` | Sync epics/tasks to GitHub |
| GET | `/api/v1/projects/{id}/metrics` | Retrieve project metrics |
| GET | `/api/v1/projects/{id}/export/proposal` | Download proposal DOCX (attachment) |

### Phase Transition Routes

PM-initiated. Backend returns `HTTP 409` if Phase N-1 is not complete.

| Method | Endpoint | Trigger |
|--------|----------|---------|
| POST | `/api/v1/projects/{id}/phases/2/start` | After redaction review |
| POST | `/api/v1/projects/{id}/phases/3/start` | After proposal generation |
| POST | `/api/v1/projects/{id}/phases/4/start` | After tech stack review |
| POST | `/api/v1/projects/{id}/phases/5/start` | After team review |
| POST | `/api/v1/projects/{id}/phases/6/start` | After estimation review |

Response: `{ "phase": number, "status": "in_progress" }` or `{ "detail": "Phase N-1 not complete" }`

### Seed Factory Routes

```
POST   /api/v1/factory/seed-employees
POST   /api/v1/factory/seed-projects
POST   /api/v1/factory/seed-technologies
POST   /api/v1/factory/seed-all
DELETE /api/v1/factory/reset-db
```

### Key Response Shapes

```typescript
// GET /api/v1/projects (dashboard list)
[{
  id: string;
  name: string;
  domain: string;
  phase: string;           // "redaction" | "chat" | "techstack" | "team" | "estimation" | "epics"
  updated: string;         // ISO 8601
  syncStatus?: "pending" | "synced" | "skipped" | "failed";
}]

// GET /api/v1/projects/{id}/epics
[{
  id: string;
  title: string;
  description: string;     // GitHub Milestone description
  points: number;
  syncStatus: "pending" | "synced" | "skipped" | "failed";
  syncError?: string;
  selected: boolean;
  tasks: [{
    id: string;
    title: string;
    description: string;   // GitHub Issue body
    points: number;
    assignee?: string;
    syncStatus: "pending" | "synced" | "skipped" | "failed";
    syncError?: string;
  }]
}]

// GET /api/v1/projects/{id}/metrics
{
  tokenUsage: { totalTokens, totalCostUsd, inputTokens, outputTokens, byPhase[], trend[] };
  quality: { graders: [{ grader, score }] };
  retrieval: { byQuery: [{ phase, recall, relevancy }] };
  errors: { byPhase: [{ phase, errors, retries }], recent: [{ phase, code, msg, ts }] };
  latency: { byNode: [{ node, p50, p95 }] };
}
```

---

## 9. Chunking Strategy

- Size: 50–800 tokens (env: `CHUNK_SIZE_MIN_TOKENS`, `CHUNK_SIZE_MAX_TOKENS`)
- Strategy: header detection → paragraph fallback → size normalization
- Tables: atomic chunks, never split mid-row
- Chunk metadata: `project_id`, `chunk_index`, `detected_type`, `page_number`, `section_hint`
- Adjacent chunk cosine similarity must be < 0.85

---

## 10. Evaluation Strategy

Graded on three axes. Evals are the primary quality signal.

### 10.1 RAG Layer

| Test | Grader | Target |
|------|--------|--------|
| Retrieval recall | RAGAS `context_recall` | ≥ 0.80 |
| Answer relevancy | RAGAS `answer_relevancy` | ≥ 0.75 |
| Reranker precision improvement | Custom rank comparison | ≥ 70% of cases |

### 10.2 Agent Layer

| Test | Grader | Target |
|------|--------|--------|
| TBD detection — explicit | Custom exact match | 100% |
| TBD detection — vague | Custom LLM-as-judge | ≥ 0.70 |
| TBD detection — missing sections | Custom section checklist | ≥ 0.85 (post-MVP) |
| Tool selection accuracy | Custom `tool_calls[].name` match | — |
| Loop safety | Custom `len(tool_calls) <= max_iterations` | — |
| Tool argument validity | Custom Pydantic validate | — |
| Phase ordering compliance | Custom phase N-1 complete before N | — |
| Proposal completeness | DeepEval G-Eval rubric | ≥ 0.75 |
| Tech stack rationale quality | DeepEval G-Eval rubric | ≥ 0.70 |
| Effort estimate plausibility | Custom range check vs. historical | ≥ 0.80 |
| Groundedness | Custom LLM-as-judge | ≥ 0.70 (`GROUNDEDNESS_THRESHOLD`) |

### 10.3 Integration Layer

| Test | Grader | Target |
|------|--------|--------|
| GitHub ticket structure validity | Custom schema check | 100% |
| Round-trip: doc → GitHub sync | Custom end-to-end | ≥ 0.90 |

### 10.4 Eval Infrastructure

```
test_cases.json          # 10–15 eval tasks with ground truth
evals/graders.py         # code-based + semantic graders
evals/harness.py         # HybridRAGAgentEval + EvalResult dataclass
results/                 # eval_results_<timestamp>.json per run
eval_suite.py            # CI gate: python eval_suite.py --threshold 0.90
```

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

**Metrics:** Primary is `pass@1`. Dev uses `pass@k`, production uses `pass^k`. CI gate threshold: 90%.

**Regression rule:** Any eval with `pass_rate > 0.80` graduates to regression suite. Mark:
```python
# REGRESSION: do not change this prompt without re-running evals/regression_suite.py
```

**LLM-as-judge groundedness prompt:**
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

Eval results synced to Google Drive after each run:
```bash
rclone copy results/ gdrive:acuity/eval-results/
```

---

## 11. Observability

| Signal | Tool | Notes |
|--------|------|-------|
| LLM call traces + spans | LangSmith or Langfuse | Both configured via env; final choice pending |
| Cost per project | LangSmith/Langfuse + custom | Surfaced in metrics tab |
| Latency per agent node | LangSmith/Langfuse | Per-node breakdown |
| Eval results | Custom `eval_results.json` | Synced to Google Drive via rclone |

**Distinction:** metrics describe the running system (cost, latency); evals verify behavior (correctness). Metrics run in production; evals run in dev and CI.

---

## 12. Metrics Dashboard

Five sub-tabs per project:

| Tab | Content |
|-----|---------|
| Token Usage & Cost | Token count and USD cost per LLM call and per session |
| AI Quality | Eval pass rates for proposal completeness (DeepEval scores) |
| Retrieval | Retrieval precision/recall; TBD detection precision/recall across clarification rounds |
| Error Handling | Error rates, retry counts per phase, failed GitHub sync attempts, GitHub sync stats |
| Latency | P50/P95 latency per LangGraph agent node |

Visualization: Recharts (line, bar, stat card components).

---

## 13. Cost Estimate (One Full Workflow)

| Phase | Model | Est. Tokens | Est. Cost |
|-------|-------|-------------|-----------|
| Phase 1 (embedding) | `text-embedding-3-small` | ~50K | ~$0.005 |
| Phase 2 (RAG chat, 5 turns) | Gemini 2.5 Pro | ~30K | ~$0.11 |
| Phase 3–4 (tool calls) | Gemini 2.5 Flash | ~10K | ~$0.01 |
| Phase 5–6 (estimation + epics) | Claude Sonnet | ~20K | ~$0.06 |
| **Total** | | ~110K | **~$0.19** |

Budget guardrail: `MAX_COST_PER_WORKFLOW_USD=0.50`

---

## 14. Security & Privacy

- **PII anonymization** before any data reaches vector store or LLM
- **PM review gate** before chunking proceeds — no silent anonymization
- **Fernet encryption** for stored PII values (`PII_ENCRYPTION_KEY`)
- **No LLM training on user data** — inference-only
- **API keys** managed via environment variables, never hardcoded
- **Local reranker** — requirements text does not leave the host for reranking
- **Prompt injection detection** enabled via `PROMPT_INJECTION_DETECTION=true`

---

## 15. Environment Variables

```bash
# LLM
MAIN_LLM_PROVIDER=google
MAIN_LLM_MODEL=gemini-2.5-pro
FAST_LLM_PROVIDER=google
FAST_LLM_MODEL=gemini-2.5-flash
TEMPERATURE=0.2

# APIs
OPENAI_API_KEY=
GOOGLE_API_KEY=
ANTHROPIC_API_KEY=           # optional, Phase 5+6

# GitHub
GITHUB_TOKEN=
GITHUB_OWNER=
GITHUB_REPO=
GITHUB_USE_PROJECTS_V2=false

# Embeddings + ChromaDB
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

# Observability
OBSERVABILITY_PROVIDER=langsmith
LANGSMITH_API_KEY=

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
```

Add to `.gitignore`: `.env`, `chroma_db/`, `project_state.db`, `app.db`, `documents/`

---

## 16. UI Routes

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

---

## 17. Implementation Status (June 2026)

| Layer | Status |
|-------|--------|
| Frontend (Next.js 16.2, Tailwind v4) | Epics 0–3 complete; all screens scaffolded |
| Backend FastAPI scaffold + 17-table SQLite schema + Alembic | Complete |
| ChromaDB ingestion pipeline (Phase 1) | Real implementation done |
| GitHub MCP sync tools (Phase 6) | Functional stubs — await Phase 6 epics |
| LangGraph orchestration + phase transitions | Epic 5 in progress |
| PII detection pipeline | Epic 5 in progress |
| Eval harness | Week 11 active focus |

---

## 18. Open Decisions

| Item | Status |
|------|--------|
| Observability provider (LangSmith vs Langfuse) | Both configured via env — decision pending |
| Google Drive source documents folder path | Not yet recorded — ask Krishna |
| DOCX export versioning (v1, v2) | Not yet specified |
| Chat endpoint: SSE streaming vs. polling | SSE preferred; frontend refactor needed |

---

## 19. Post-MVP Backlog

- Fine-tuning: TBD detection model on Qwen 2.5 1.5B (Unsloth)
- Langfuse migration (better UI, self-hosting)
- Multi-agent orchestration
- AWS S3 to replace Google Drive (rclone command swap)
- Linear MCP as alternative to GitHub
- CSV bulk import for employee seed data
- GitHub sync rollback on complete failure
- Multi-user support with RBAC
- Cloud deployment (Railway, Render, or AWS)

---

*v2 generated June 2026 — Week 11, AI Engineering Cohort Capstone. Supersedes v1 (original submission artifact).*
