# AI-Driven Project Management Tool — Claude Code Handover

> **Purpose:** Full context handover for Claude Code. Read this before touching any file.
> **Last updated:** June 2026

---

## 1. What This Project Is

A capstone AI engineering project. A PM uploads a requirements document (PDF/DOCX), refines it through an AI-assisted chat interface, receives team/tech stack suggestions and effort estimates, and syncs generated epics/tasks to **GitHub** (Jira replaced — see decisions below).

**Three axes on which this is graded:** system design quality · eval coverage · cost analysis.

---

## 2. Architecture

### Pattern
- **Phases 1–3** (ingestion → refinement → tech stack): deterministic pipeline
- **Phases 4–6** (team suggestion → estimation → epic gen + sync): LangGraph ReAct agent

### Phase Summary

| Phase | Name | Key Components |
|-------|------|----------------|
| 1 | Document Ingestion | PDF/DOCX parser, structure-aware chunker, `text-embedding-3-small`, ChromaDB |
| 2 | Chat & Refinement | RAG pipeline, query rewriting (3 sub-queries), BERT reranker (top-20→top-4), TBD detector |
| 3 | Tech Stack Suggestion | `approved_technologies` tool, employee skills tool, LLM reasoning |
| 4 | Team Suggestion | SQLite employee tool, skills matcher, availability filter |
| 5 | Effort Estimation | Historical projects retrieval, LangGraph state, LLM estimation |
| 6 | Epic & Task Gen + Sync | Pydantic structured output, GitHub MCP server, sync status tracking |

### LangGraph State Object
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

## 3. Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Frontend | Next.js 14+ (App Router) | Tailwind CSS + shadcn/ui |
| Charts | Recharts | Metrics tab only |
| Backend | FastAPI + Uvicorn | All routes prefixed `/api/v1/` |
| ORM / DB | SQLAlchemy + SQLite + Alembic | WAL mode enabled; `check_same_thread=False` |
| Vector DB | ChromaDB | **PersistentClient only** — see §6 |
| LLM (main) | Gemini (default, switchable) | Via LangChain factory + `MAIN_LLM_PROVIDER` env var |
| LLM (fast) | Gemini Flash / Nano | Query rewriting, LLM-as-judge |
| LLM (structured) | Claude Sonnet (optional) | Estimation + epic generation |
| Embeddings | `text-embedding-3-small` (OpenAI) | **1536 dims, cosine distance — never change post-ingestion** |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Local BERT, ~500MB, sentence-transformers |
| PII Detection | regex + spaCy `en_core_web_sm` | Two-pass: regex first, then NER |
| Orchestration | LangGraph | `SqliteSaver` checkpointer (not MemorySaver) |
| Structured Output | Pydantic | All epics/tasks/team suggestions |
| Doc Export | python-docx | Proposal DOCX to `/documents` |
| GitHub Integration | GitHub MCP server | Replaces Jira — see §5 |
| Observability | LangSmith or Langfuse | Both configured via env; decision pending |
| Evals | Custom harness + RAGAS + DeepEval | See §8 |
| Seed Data | Faker (seed=42) | Via Swagger factory endpoints |

---

## 4. Architectural Decisions (Locked)

### ADR-001: GitHub replaces Jira
Jira MCP is replaced with GitHub Issues + Milestones for MVP.

**Mapping:**
| PRD (Jira) | GitHub Equivalent |
|------------|-------------------|
| `create_project` | `POST /repos` |
| `create_epic` | Milestone (`POST /repos/{owner}/{repo}/milestones`) |
| `create_story` | Issue with `story` label |
| `create_task` | Issue with `task` label + milestone reference |

**MCP tools (FastMCP):**
```python
@mcp.tool
def create_github_milestone(repo: str, title: str, description: str, due_date: str) -> dict: ...

@mcp.tool
def create_github_issue(repo: str, title: str, body: str, milestone_number: int,
                        labels: list[str], assignees: list[str]) -> dict: ...

@mcp.tool
def get_github_repo_issues(repo: str, milestone: int) -> list[dict]: ...
```

**DB schema changes:** `jira_epic_id VARCHAR` → `github_milestone_number INTEGER` + `github_milestone_url VARCHAR`; `jira_issue_id VARCHAR` → `github_issue_number INTEGER` + `github_issue_url VARCHAR`

**Env vars:** `GITHUB_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO` (no `JIRA_*` vars)
**Flag:** `GITHUB_USE_PROJECTS_V2=false` (Projects V2 GraphQL is post-MVP)

---

### ADR-002: SqliteSaver replaces MemorySaver
```python
from langgraph.checkpoint.sqlite import SqliteSaver
checkpointer = SqliteSaver.from_conn_string("./project_state.db")
graph = workflow.compile(checkpointer=checkpointer)
```
Keep `project_state.db` separate from the application `app.db`.

---

### ADR-003: ChromaDB PersistentClient
```python
import chromadb
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(
    name=f"project_{project_id}",
    metadata={"hnsw:space": "cosine"},
    embedding_function=OpenAIEmbeddingFunction(
        api_key=os.environ["OPENAI_API_KEY"],
        model_name="text-embedding-3-small",
        dimensions=1536  # NEVER change post-ingestion
    )
)
```
Add `chroma_db/` and `project_state.db` to `.gitignore`.

---

### ADR-004: Embedding contract locked
- Model: `text-embedding-3-small`
- Dimensions: `1536` (env var: `EMBEDDING_DIMENSIONS=1536`)
- Distance: `cosine`
- **Changing dimensions after ingestion requires full re-embedding. Do not do this.**

---

### ADR-005: Phase status + retry logic
Every phase node must update `phase_status` in `ProjectState`. Retry logic (exponential backoff, max 3 retries) lives at the LangGraph node level, not at the FastAPI endpoint level.

---

### ADR-006: PII encryption
Fernet symmetric encryption via `cryptography` library. Key in `.env` as `PII_ENCRYPTION_KEY`.
```bash
# Generate key (run once, store in .env):
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

### ADR-007: Concurrency model (MVP)
- Sequential phase transitions within a project
- No concurrent project processing in MVP
- SQLite WAL mode: `PRAGMA journal_mode=WAL`
- Engine: `create_engine("sqlite:///./app.db", connect_args={"check_same_thread": False})`

---

### ADR-008: Phase transition rules
- All transitions are PM-initiated via explicit "Proceed" button
- Phase N cannot start until Phase N-1 `phase_status` = `"complete"`
- PM can navigate backward to review but cannot re-run a completed phase without explicit "Re-run Phase" action

---

### ADR-009: TBD detection scope (MVP)
- Level 1 (explicit TBDs) and Level 2 (vague statements via LLM prompt) only
- Levels 3 (missing sections) and 4 (contradictions) are post-MVP

---

### ADR-010: Model usage strategy
- **Nano model:** basic testing — RAG retrieval, chunking, initial agent loops
- **Mini model:** evals and agents after basic testing completes
- Rationale: cost efficiency for iteration and eval runs

---

## 5. Environment Variables

```bash
# LLM
MAIN_LLM_PROVIDER=google          # or anthropic
MAIN_LLM_MODEL=gemini-1.5-pro
FAST_LLM_PROVIDER=google
FAST_LLM_MODEL=gemini-1.5-flash
TEMPERATURE=0.2

# APIs
OPENAI_API_KEY=
GOOGLE_API_KEY=
ANTHROPIC_API_KEY=                 # optional, Phase 5+6

# GitHub MCP (replaces Jira)
GITHUB_TOKEN=
GITHUB_OWNER=
GITHUB_REPO=
GITHUB_USE_PROJECTS_V2=false

# Embeddings
EMBEDDING_DIMENSIONS=1536

# ChromaDB
CHROMA_PERSIST_PATH=./chroma_db

# PII
PII_ENCRYPTION_KEY=               # generate with Fernet
PII_DETECTION_ENABLED=true
PII_REGEX_ENABLED=true
PII_NER_ENABLED=true
PII_REVIEW_GATE=true

# RAG Pipeline
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

# Cost guardrail
MAX_COST_PER_WORKFLOW_USD=0.50

# Observability
OBSERVABILITY_PROVIDER=langsmith   # or langfuse
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

---

## 6. Database Schema (SQLite)

Core tables: `projects`, `proposal_state`, `employees`, `skills`, `employee_skills`, `approved_technologies`, `historical_projects`, `epics`, `tasks`, `pii_detections`, `pii_ingestion_logs`, `metrics`, `latency_logs`, `error_logs`

**GitHub-specific fields:**
- `epics`: `github_milestone_number INTEGER`, `github_milestone_url VARCHAR` (not `jira_epic_id`)
- `tasks`: `github_issue_number INTEGER`, `github_issue_url VARCHAR` (not `jira_issue_id`)

**Sync status enum:** `pending` | `synced` | `skipped` | `failed`

**Seed factory endpoints:**
```
POST /api/v1/factory/seed-employees
POST /api/v1/factory/seed-projects
POST /api/v1/factory/seed-technologies
POST /api/v1/factory/seed-all
DELETE /api/v1/factory/reset-db
```

---

## 7. API Routes

All routes prefixed `/api/v1/`. FastAPI auto-generates OpenAPI spec at `/docs` — treat as source of truth for frontend contract.

Key route groups: `/projects`, `/projects/{id}/phases`, `/projects/{id}/export`, `/factory`

DOCX export: `GET /api/v1/projects/{id}/export/proposal` → `Content-Disposition: attachment`

---

## 8. Eval Layer (Week 11 — Active Focus)

### Current status
Phase 1 Foundation — in progress.

### File structure
```
/test_cases.json              # 10–15 eval tasks (ground truth)
/evals/graders.py             # code-based + semantic graders
/evals/harness.py             # HybridRAGAgentEval class + run_all()
/results/                     # eval_results_<timestamp>.json per run
eval_suite.py                 # CI gate: python eval_suite.py --threshold 0.90
```

### Graders to implement
| Grader | Type | What it checks |
|--------|------|----------------|
| Retrieval source match | Code-based | Retrieved chunk IDs match expected |
| Tool selection accuracy | Code-based | `tool_calls[].name` matches expected |
| Loop safety | Code-based | `len(tool_calls) <= max_iterations` |
| Tool argument validity | Code-based | Pydantic-validate each tool call's args |
| Phase ordering compliance | Code-based | Phase N complete before N+1 starts |
| Semantic relevance | Semantic | Cosine similarity: retrieved chunks vs query |
| Groundedness | LLM-as-judge | All claims supported by context? |

### LLM-as-judge prompt template (groundedness)
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

### HybridRAGAgentEval harness
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

### Eval metrics
- **Development:** `pass@k` (at least 1 success in k trials)
- **Production:** `pass^k` (all k trials succeed)
- **Primary metric:** `pass@1`
- **Baseline target:** ~40% pass rate before any tuning
- **CI gate threshold:** 90%

### Baseline protocol
On Day 7 morning, before any prompt tuning, run all evals and save as `results/baseline_eval_run_001.json`. All subsequent runs compare against this.

### Regression suite rule
Any eval with `pass_rate > 0.80` is graduated to the regression suite. Mark in code:
```python
# REGRESSION: do not change this prompt without re-running evals/regression_suite.py
```

### Cost estimate (one full workflow)
| Phase | Model | Est. Tokens | Est. Cost |
|-------|-------|-------------|-----------|
| Phase 1 (embedding) | text-embedding-3-small | ~50K | ~$0.005 |
| Phase 2 (RAG chat, 5 turns) | Gemini 1.5 Pro | ~30K | ~$0.11 |
| Phase 3–4 (tool calls) | Gemini 1.5 Flash | ~10K | ~$0.01 |
| Phase 5–6 (estimation + epics) | Claude Sonnet | ~20K | ~$0.06 |
| **Total** | | ~110K | **~$0.19** |

---

## 9. Chunking Rules

- Size: 50–800 tokens (configurable)
- Strategy: structure-aware hybrid — header detection → paragraph fallback → size normalization
- Tables: atomic chunks, never split mid-row
- Every chunk gets metadata: `project_id`, `chunk_index`, `detected_type`, `page_number`, `section_hint`
- Healthy size distribution: Pareto-shaped (P90 < 600 tokens, P10 > 50 tokens)
- Adjacent chunk cosine similarity threshold: < 0.85 (higher = over-splitting)

---

## 10. Caching Strategy

| What | Cached? | Method |
|------|---------|--------|
| Document embeddings | Yes | Check ChromaDB for `project_id` before re-embedding |
| Phase LLM outputs | Yes | `phase_status` field in SQLite — skip if `"complete"` |
| Employee DB queries | Yes | In-memory Python dict loaded once per session |
| Prompt + tool definitions | Yes | Static content first in prompt (KV cache) |
| GitHub API calls | No | Write-only |

---

## 11. UI Screens

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

**Metrics tabs (5):** Token Usage & Cost · AI Quality · Retrieval · Error Handling · Latency

---

## 12. Week 11 Checklist (Current Sprint)

- [ ] Extract 10–15 test cases from real MVP manual tests + edge cases → `test_cases.json`
- [ ] Write unambiguous success criteria for each test case
- [ ] Implement code-based graders (retrieval source match, tool selection, loop safety, phase ordering)
- [ ] Implement semantic grader (cosine similarity: retrieved chunks vs query)
- [ ] Implement LLM-as-judge grader (groundedness)
- [ ] Build `HybridRAGAgentEval` harness with `run_eval()` + `EvalResult` dataclass
- [ ] Run baseline (3 trials per test case); target ~40% pass rate
- [ ] Read 20+ failed transcripts; document findings
- [ ] Add CI gate: `python eval_suite.py --threshold 0.90`

---

## 13. Known Gaps (from PRD Gap Analysis)

All critical gaps are resolved in the decisions above. Remaining open items:

| Item | Status |
|------|--------|
| Observability provider (LangSmith vs Langfuse) | Open — both configured via env |
| Google Drive source documents folder | Not yet recorded — ask Krishna |
| TBD detection levels 3 & 4 | Post-MVP |
| Projects V2 GraphQL for GitHub | Post-MVP (`GITHUB_USE_PROJECTS_V2=false`) |
| Multi-agent orchestration | Post-MVP |
| AWS S3 migration | Post-MVP (Google Drive → rclone for MVP) |
| DOCX export versioning (v1, v2) | Not yet specified |
| API versioning contract for frontend | Use `/api/v1/` prefix; generate OpenAPI spec at `/docs` |

---

## 14. Post-MVP Backlog

- Fine-tuning: TBD detection model on Qwen 2.5 1.5B (Unsloth)
- Langfuse migration (better UI, self-hosting)
- CSV bulk import for employee seed data
- GitHub sync rollback on complete failure
- Multi-user support with RBAC
- Cloud deployment (Railway, Render, or AWS)
- Linear MCP as alternative to GitHub
- AWS S3 to replace Google Drive (folder structure transfers directly; rclone command swap only)
- Multi-agent orchestration

---

## 15. Non-Negotiable Rules for Claude Code

1. **Never use `chromadb.Client()`** — always `chromadb.PersistentClient(path=os.environ["CHROMA_PERSIST_PATH"])`
2. **Never use `MemorySaver`** — always `SqliteSaver` for the LangGraph checkpointer
3. **Never change `EMBEDDING_DIMENSIONS` after ingestion** — requires full re-embedding
4. **All routes prefixed `/api/v1/`**
5. **Retry logic at LangGraph node level, not FastAPI endpoint level**
6. **`phase_status` dict must be updated in `ProjectState` at every phase transition**
7. **Fernet for PII encryption** — key from `PII_ENCRYPTION_KEY` env var
8. **SQLite WAL mode** — `PRAGMA journal_mode=WAL` on engine init
9. **LLM provider switchable via env var** — never hardcode `google` or `anthropic`
10. **GitHub MCP only** — no Jira references anywhere in codebase

---

*Generated June 2026 
