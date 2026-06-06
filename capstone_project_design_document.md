# Capstone Project Design Document

**Project:** AI-Driven Project Management Tool  
**Author:** Krishna Kumar

---

## 1. Executive Summary

This project is a Hybrid RAG + Agent system that assists project managers in transforming unstructured requirements documents into structured, actionable project artifacts. A PM uploads source documents, refines them through an AI-assisted chat interface, receives AI-generated team and tech stack recommendations with effort estimates, and syncs the resulting epics and tasks directly to Jira via an MCP integration.

The system is designed around production-grade AI engineering principles: configurable guardrails, a custom evaluation harness, observability instrumentation, and a multi-layer RAG + agent architecture that mirrors real-world deployment patterns.

---

## 2. Problem Statement

Project managers routinely spend significant time manually extracting requirements, identifying gaps, estimating effort, and decomposing work into Jira tasks — a process that is error-prone and heavily dependent on individual experience. Existing PM tools offer templates and structure but no intelligent augmentation of the requirements refinement process itself.

**Core gaps addressed:**

- Requirements documents contain ambiguity (TBDs, vague language, missing sections, contradictions) that propagates into poor sprint planning
- Tech stack and team composition decisions are made informally, without leveraging historical data on employee skills or approved technologies
- Effort estimation lacks grounding in historical actual vs. estimated story points
- The manual Jira ticket creation step is a high-friction, low-value task

---

## 3. Goals & Non-Goals

### Goals

- Parse and analyze uploaded requirements documents to detect TBDs at four levels: explicit flags, vague statements, missing sections, and logical contradictions
- Drive an AI-assisted clarification loop using a structured UI (Answer / TBD / Out-of-Scope per question)
- Generate a new structured proposal document from refined source material
- Recommend a tech stack and team composition based on requirements, employee skill profiles, and an approved technologies list
- Estimate effort per epic/story informed by historical estimated vs. actual story point data
- Sync generated epics and tasks to Jira via a FastMCP server integration
- Expose real-time cost, latency, and task-specific eval metrics per project
- Support multiple concurrent projects with SQLite-backed session state persistence

### Non-Goals

- In-place editing of uploaded source documents (system generates a new proposal document)
- Real-time collaborative editing
- Support for project management tools other than Jira at MVP stage
- Fine-tuned models (system uses prompt engineering + RAG over pretrained LLMs)

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
Hybrid RAG retrieval (dense + sparse, BERT cross-encoder reranking)
        │
        ▼
TBD Detection Agent (LangGraph) — 4-level analysis
        │
        ▼
Clarification UI (Answer / TBD / Out-of-Scope per question)
        │
        ▼
Proposal Document Generation
        │
        ├──► Tech Stack + Team Suggestion Agent
        │         (requirements + skills DB + approved tech list)
        │
        ├──► Effort Estimation Agent
        │         (historical story point data)
        │
        └──► Jira Sync via FastMCP
                  (epics → stories → tasks)
```

### 4.2 Component Breakdown

| Layer | Component | Technology |
|---|---|---|
| Frontend | Chat UI, structured clarification widget, metrics dashboard | Next.js 14+, Tailwind CSS, shadcn/ui, Recharts |
| Backend | REST API, agent orchestration | FastAPI, LangGraph |
| Vector Store | Chunk storage and retrieval | ChromaDB |
| Relational Store | Session state, project metadata, historical data | SQLite + SQLAlchemy + Alembic |
| LLM | Inference | Gemini (default), Anthropic (switchable via env) |
| LLM Factory | Provider abstraction | LangChain factory pattern |
| Reranker | Cross-encoder reranking | sentence-transformers (local BERT, ~500MB) |
| Jira Integration | Epic/task sync | FastMCP server |
| Observability | Traces, spans, LLM call logs | LangSmith or Langfuse (env-configurable) |
| Seed Data | Demo/test data generation | Faker (via Swagger UI factory endpoints) |

---

## 5. Key Design Decisions

### 5.1 New Document Generation vs. In-Place Editing

The system generates a fresh structured proposal from source material rather than annotating or editing the uploaded document. This ensures the output is always consistently formatted and AI-graded, regardless of the quality or structure of the input.

### 5.2 TBD Detection — Four-Level Analysis

| Level | Description | Example |
|---|---|---|
| Explicit flags | Literal "TBD", "TODO", "N/A" | "Authentication: TBD" |
| Vague statements | Imprecise language without measurable criteria | "The system should be fast" |
| Missing sections | Required sections absent from the document | No mention of error handling |
| Contradictions | Conflicting statements within the document | "Single-tenant" in one section, "multi-tenant" in another |

### 5.3 PII Anonymization — Two-Pass Pipeline

All documents pass through a two-pass anonymizer before chunking:

1. **Pass 1:** Regex patterns for structured PII (emails, phone numbers, SSNs, credit card numbers)
2. **Pass 2:** spaCy NER for contextual PII (names, organizations, locations)

A PM review gate surfaces detected PII before chunking proceeds, allowing the PM to confirm or override anonymization decisions.

### 5.4 LLM Provider Abstraction

A LangChain factory pattern resolves the active LLM at runtime from environment variables. Switching between Gemini and Anthropic Claude requires only an env var change — no code modifications.

```
LLM_PROVIDER=gemini   # or: anthropic
GOOGLE_API_KEY=...
ANTHROPIC_API_KEY=...
```

### 5.5 Guardrail Configurability

All guardrail thresholds (confidence cutoffs, reranking score floors, TBD detection sensitivity) are environment-variable driven, enabling tuning without code changes.

### 5.6 ChromaDB vs. Production Vector Stores

ChromaDB is used for MVP speed and simplicity. The architecture does not couple retrieval logic to ChromaDB internals — migrating to Qdrant or Pinecone requires only a store adapter swap.

---

## 6. Data Model

### 6.1 Relational (SQLite)

```
projects
  id, name, created_at, status

documents
  id, project_id, filename, upload_ts, anonymized_path, status

clarifications
  id, document_id, question, answer, action (Answer/TBD/Out-of-Scope)

proposals
  id, project_id, document_id, content_path, created_at

epics
  id, proposal_id, title, description, estimated_points, actual_points

tasks
  id, epic_id, title, description, jira_key, status

employees
  id, name, skills (JSON), seniority

approved_technologies
  id, name, category, tags
```

### 6.2 Vector Store (ChromaDB)

- **Collection per project:** chunks of the source document + proposal
- **Metadata per chunk:** document_id, section, page, chunk_index
- **Embedding model:** Gemini text-embedding-004 (default)

---

## 7. Agent Design

### 7.1 TBD Detection Agent (LangGraph)

```
State: { document_text, chunks, tbds: [] }

Nodes:
  parse_document → chunk_document → detect_explicit → detect_vague
  → detect_missing → detect_contradictions → aggregate → output
```

Each detection node is independently testable and produces structured `TBDItem` objects consumed by the clarification UI.

### 7.2 Tech Stack Suggestion Agent

Inputs: refined requirements text, employee skill profiles, approved technologies list  
Output: recommended stack with rationale per layer (frontend, backend, database, infra)

### 7.3 Effort Estimation Agent

Inputs: epics/stories list, historical story point data (estimated vs. actual per category)  
Output: point estimate per story + confidence interval

### 7.4 Jira Sync via FastMCP

The FastMCP server exposes tools the LangGraph agent calls to:
- Create epics
- Create stories under each epic
- Create subtasks
- Set labels, assignees, and sprint targets

---

## 8. Evaluation Strategy

Evals are the primary quality signal for this system. Three evaluation layers are maintained:

### 8.1 RAG Layer Evals

| Test | Grader | Target |
|---|---|---|
| Retrieval recall — TBD context | RAGAS `context_recall` | ≥ 0.80 |
| Answer relevancy | RAGAS `answer_relevancy` | ≥ 0.75 |
| Reranker improves precision | Code-based rank comparison | ≥ 70% of cases |

### 8.2 Agent Layer Evals

| Test | Grader | Target |
|---|---|---|
| TBD detection — explicit | Exact match | 100% |
| TBD detection — vague | LLM-as-judge | ≥ 0.70 |
| TBD detection — missing sections | Code-based (section checklist) | ≥ 0.85 |
| Proposal completeness | LLM-as-judge (rubric) | ≥ 0.75 |
| Tech stack rationale quality | LLM-as-judge | ≥ 0.70 |
| Effort estimate plausibility | Code-based (range check vs. historical) | ≥ 0.80 |

### 8.3 Integration Layer Evals

| Test | Grader | Target |
|---|---|---|
| Jira ticket structure validity | Code-based (schema check) | 100% |
| Round-trip: doc → Jira sync | Code-based end-to-end | ≥ 0.90 |

### 8.4 Eval Infrastructure

```
/test_cases.json          # 10–15 eval tasks
/evals/graders.py         # code-based + semantic graders
/evals/harness.py         # HybridRAGAgentEval class + run_all()
/results/                 # eval_results.json per run
```

CI gate: `python eval_suite.py --threshold 0.90` — blocks merges below threshold.

Trials: minimum 3 per test case; pass@k for development, pass^k for production reliability.

---

## 9. Observability

| Signal | Tool | Notes |
|---|---|---|
| LLM call traces + spans | LangSmith or Langfuse | Both configured via env; final choice TBD |
| Cost per project | LangSmith/Langfuse + custom | Surfaced in metrics tab |
| Latency per agent node | LangSmith/Langfuse | Per-node breakdown |
| Eval results | Custom (eval_results.json) | Synced to Google Drive via rclone |

**Distinction:** metrics describe the running system (cost, latency); evals verify behavior (correctness). Metrics run in production; evals run in dev and CI.

---

## 10. Metrics Dashboard

A real-time metrics tab in the frontend surfaces five sub-tabs per project:

| Sub-tab | Content |
|---|---|
| Cost | Token usage and USD cost per LLM call and session |
| Latency | P50/P95 latency per agent node |
| TBD Detection | Precision/recall across clarification rounds |
| Proposal Quality | Eval pass rates for proposal completeness |
| Jira Sync | Tickets created, sync success/failure rate |

Visualization: Recharts (line, bar, and stat card components).

---

## 11. API Surface (FastAPI)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/projects` | Create new project |
| POST | `/projects/{id}/documents` | Upload requirements document |
| GET | `/projects/{id}/tbds` | Retrieve detected TBDs |
| POST | `/projects/{id}/clarifications` | Submit clarification answers |
| POST | `/projects/{id}/proposal` | Generate proposal document |
| GET | `/projects/{id}/proposal` | Retrieve generated proposal |
| POST | `/projects/{id}/stack` | Run tech stack suggestion |
| POST | `/projects/{id}/estimate` | Run effort estimation |
| POST | `/projects/{id}/sync-jira` | Sync epics/tasks to Jira |
| GET | `/projects/{id}/metrics` | Retrieve project metrics |
| POST | `/seed/fake-project` | Generate a fake project for demos |

---

## 12. Security & Privacy

- **PII anonymization** before any data reaches the vector store or LLM
- **PM review gate** before chunking proceeds — no silent anonymization
- **No LLM training on user data** — inference-only usage of Gemini/Anthropic APIs
- **API keys** managed via environment variables, never hardcoded
- **Local reranker** (BERT cross-encoder) — requirements text does not leave the host for reranking

---
