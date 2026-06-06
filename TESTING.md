# Testing Documentation — Acuity AI PM Tool

> **Scope:** Unit · Integration · Eval harness · AI engineering metrics  
> **Current week:** 11 (Evals phase active)  
> **CI gate:** `python eval_suite.py --threshold 0.90`

---

## Table of Contents

1. [Test Layers](#1-test-layers)
2. [Acceptance Criteria by Phase](#2-acceptance-criteria-by-phase)
3. [AI Eval Harness](#3-ai-eval-harness)
4. [Grader Catalogue](#4-grader-catalogue)
5. [AI Engineering Metrics Coverage](#5-ai-engineering-metrics-coverage)
6. [CI / Regression Rules](#6-ci--regression-rules)
7. [Running Tests](#7-running-tests)

---

## 1. Test Layers

| Layer | Location | Tool | Runs on |
|-------|----------|------|---------|
| Schema unit tests | `backend/tests/test_schemas.py` | pytest | Every commit |
| Route smoke tests | `backend/tests/test_routes.py` | pytest + FastAPI `TestClient` | Every commit |
| Health check | `backend/tests/test_health.py` | pytest | Every commit |
| Eval harness | `evals/harness.py` | Custom `HybridRAGAgentEval` | Nightly + manual |
| CI gate | `eval_suite.py` | Custom, threshold 0.90 | Pre-merge |

### What each layer checks

**Schema tests** — Pydantic models accept valid inputs, field defaults, and enum values. No DB hit.

**Route smoke tests** — every `POST/GET/DELETE` endpoint returns HTTP < 300. `TestClient` overrides `get_db` with `lambda: None`; stubs hold the contract.

**Eval harness** — multi-trial runs (`n_trials=3` default) for RAG, agent, and LLM-as-judge graders against `test_cases.json` ground truth.

---

## 2. Acceptance Criteria by Phase

Each criterion uses the format: **Given / When / Then**.

---

### Phase 1 — Document Ingestion

| ID | Criterion | Pass threshold |
|----|-----------|----------------|
| P1-AC1 | Given a valid PDF ≤ 10 MB, when uploaded, then `document.status` = `"ingested"` within 30 s | Required |
| P1-AC2 | Given a valid DOCX ≤ 10 MB, when uploaded, then text extracted without empty result | Required |
| P1-AC3 | Given a file > 10 MB, when uploaded, then HTTP 422 returned with `"File exceeds MAX_FILE_SIZE_MB"` | Required |
| P1-AC4 | Given an unsupported extension (`.txt`, `.png`), when uploaded, then HTTP 422 returned | Required |
| P1-AC5 | Given a document with < 100 extractable chars, when uploaded, then HTTP 422 with `"MIN_EXTRACTABLE_CHARS"` reason | Required |
| P1-AC6 | Given any uploaded document, when ingested, then ChromaDB collection `project_{id}` exists with ≥ 1 chunk | Required |
| P1-AC7 | Given an already-ingested document, when Phase 1 is triggered again, then ChromaDB check skips re-embedding | Required |
| P1-AC8 | Given chunk distribution, then P90 chunk token count < 600 and P10 > 50 | Recommended |
| P1-AC9 | Given adjacent chunks, then cosine similarity < 0.85 (no over-splitting) | Recommended |
| P1-AC10 | Given a table in the document, then table rows are not split across chunks | Required |

---

### Phase 2 — Chat & Refinement

| ID | Criterion | Pass threshold |
|----|-----------|----------------|
| P2-AC1 | Given a user query, when sent to `/api/v1/projects/{id}/chat`, then 3 sub-queries are generated internally (logged) | Required |
| P2-AC2 | Given a user query, when retrieved, then top-4 reranked chunks are passed to the LLM (not raw top-20) | Required |
| P2-AC3 | Given a response, then groundedness score ≥ `GROUNDEDNESS_THRESHOLD` (0.7) | Required |
| P2-AC4 | Given a document containing explicit "TBD" text, when Phase 2 runs, then that item appears in `/tbds` as Level 1 | Required (100%) |
| P2-AC5 | Given a vague statement (e.g., "performance should be good"), when Phase 2 runs, then LLM-as-judge flags it as Level 2 TBD with score ≥ 0.70 | Required |
| P2-AC6 | Given TBD items, when PM submits `action="Answer"` with answer text, then `clarifications` row saved and TBD marked resolved | Required |
| P2-AC7 | Given TBD items, when PM submits `action="TBD"` or `action="Out-of-Scope"`, then `clarifications` row saved with null answer | Required |
| P2-AC8 | Given proposal generation triggered, when complete, then `proposals` row exists and DOCX written to `/documents/` | Required |
| P2-AC9 | Given a proposal, when evaluated by DeepEval G-Eval rubric, then completeness score ≥ 0.75 | Required |
| P2-AC10 | Given a BM25 + dense merge, then hybrid retrieval improves over dense-only on ≥ 70% of test cases | Recommended |

---

### Phase 3 — Tech Stack Suggestion

| ID | Criterion | Pass threshold |
|----|-----------|----------------|
| P3-AC1 | Given Phase 2 complete, when Phase 3 runs, then response contains non-empty `frontend`, `backend`, `database`, `infra` lists | Required |
| P3-AC2 | Given response, then every suggested technology appears in `approved_technologies` table | Required |
| P3-AC3 | Given response, then `rationale` field is non-empty and references at least one employee skill | Required |
| P3-AC4 | Given tech stack rationale, when evaluated by DeepEval G-Eval, then quality score ≥ 0.70 | Required |
| P3-AC5 | Given Phase 2 not complete, when Phase 3 start attempted, then HTTP 409 returned | Required |

---

### Phase 4 — Team Suggestion

| ID | Criterion | Pass threshold |
|----|-----------|----------------|
| P4-AC1 | Given Phase 3 complete, when Phase 4 runs, then response lists ≥ 1 suggested employee per required role | Required |
| P4-AC2 | Given suggested employees, then all have at least one skill matching the tech stack from Phase 3 | Required |
| P4-AC3 | Given availability filter active, then no suggested employee has `availability = false` in DB | Required |
| P4-AC4 | Given Phase 3 not complete, when Phase 4 attempted, then HTTP 409 | Required |

---

### Phase 5 — Effort Estimation

| ID | Criterion | Pass threshold |
|----|-----------|----------------|
| P5-AC1 | Given Phase 4 complete, when estimation runs, then `total_points > 0` and `total_weeks > 0` | Required |
| P5-AC2 | Given historical projects in DB, when estimation runs, then at least one comparable project is retrieved | Required |
| P5-AC3 | Given estimation output, then each epic has `confidence` in [0.0, 1.0] | Required |
| P5-AC4 | Given estimation output, when compared to historical project range, then `total_weeks` within 3× of nearest comparable | ≥ 0.80 of test cases |
| P5-AC5 | Given LangGraph retry logic, when an LLM call fails, then exponential backoff retries up to 3× before failing | Required |

---

### Phase 6 — Epic & Task Gen + GitHub Sync

| ID | Criterion | Pass threshold |
|----|-----------|----------------|
| P6-AC1 | Given Phase 5 complete, when sync triggered, then `epics` table rows have `github_milestone_number` populated | Required |
| P6-AC2 | Given sync, then each task row has `github_issue_number` and `github_issue_url` populated | Required |
| P6-AC3 | Given sync, then `sync_status` for all rows transitions from `pending` to `synced` or `failed` (never stuck at `pending`) | Required |
| P6-AC4 | Given GitHub API unavailable, when sync runs, then `sync_status = "failed"` and error logged — no unhandled exception | Required |
| P6-AC5 | Given ticket structure, when schema-checked by GitHub ticket structure grader, then pass rate = 100% | Required (100%) |
| P6-AC6 | Given round-trip (document upload → GitHub sync), then end-to-end grader pass rate ≥ 0.90 | Required |
| P6-AC7 | Given epics list, then each epic maps to one GitHub Milestone (not an Issue) | Required |
| P6-AC8 | Given tasks list, then each task maps to one GitHub Issue with `task` label and correct `milestone_number` | Required |

---

### Cross-Phase — PII Detection

| ID | Criterion | Pass threshold |
|----|-----------|----------------|
| PII-AC1 | Given a document containing email patterns, when ingested, then `pii_detections` row created | Required |
| PII-AC2 | Given PII detected, when `PII_REVIEW_GATE=true`, then phase transition blocked until PM reviews redaction screen | Required |
| PII-AC3 | Given `PII_REGEX_ENABLED=true`, then regex pass runs before spaCy NER | Required |
| PII-AC4 | Given Fernet key in env, then all PII values encrypted with Fernet before DB write | Required |

---

### Cross-Phase — Cost Guardrail

| ID | Criterion | Pass threshold |
|----|-----------|----------------|
| COST-AC1 | Given a full workflow run, when `MAX_COST_PER_WORKFLOW_USD=0.50` set, then workflow aborted if cost exceeds limit | Required |
| COST-AC2 | Given each LLM call, then tokens logged to `metrics` table with `input_tokens` and `output_tokens` fields | Required |

---

## 3. AI Eval Harness

### Data contract — `test_cases.json`

Each entry must include:

```json
{
  "id": "tc-001",
  "description": "Explicit TBD detection in requirements doc",
  "phase": 2,
  "input": {
    "query": "What is the SLA for the API?",
    "document_fixture": "fixtures/sla_tbd.pdf"
  },
  "expected": {
    "tbd_items": [{"level": 1, "contains": "SLA"}],
    "retrieved_chunk_ids": ["chunk_7", "chunk_12"],
    "tool_calls": ["detect_tbds"],
    "groundedness_min": 0.7
  },
  "max_tool_iterations": 5,
  "regression": false
}
```

Fields `retrieved_chunk_ids` and `tool_calls` are optional — omit when not applicable to the grader under test.

### `EvalResult` dataclass

```python
@dataclass
class EvalResult:
    test_case_id: str
    grader_name: str
    passed: bool
    score: float       # 0.0 – 1.0
    reasoning: str
    trial: int         # 1-indexed
```

### `HybridRAGAgentEval` interface

```python
class HybridRAGAgentEval:
    def run_eval(self, test_case: dict, n_trials: int = 3) -> list[EvalResult]: ...
    def run_all(self, n_trials: int = 3) -> dict: ...
    # Returns: {"pass_rate": float, "results": list[EvalResult], "summary": dict}
```

### Metric modes

| Mode | Formula | When |
|------|---------|------|
| `pass@1` | Pass in trial 1 | **Primary metric** — used for all reporting |
| `pass@k` | Pass in ≥ 1 of k trials | Development iteration |
| `pass^k` | Pass in all k trials | Production readiness gate |

---

## 4. Grader Catalogue

### Code-based graders

| Grader | File | What it checks | Threshold |
|--------|------|----------------|-----------|
| `retrieval_source_match` | `evals/graders.py` | Retrieved chunk IDs ⊆ expected chunk IDs (`context_recall` via RAGAS) | ≥ 0.80 |
| `answer_relevancy` | `evals/graders.py` | RAGAS `answer_relevancy` score | ≥ 0.75 |
| `reranker_precision_improvement` | `evals/graders.py` | Reranked top-4 rank improves vs. pre-rerank for same query | ≥ 70% of cases |
| `tbd_explicit_detection` | `evals/graders.py` | Exact match on Level 1 TBD items | 100% |
| `tbd_vague_detection` | `evals/graders.py` | LLM-as-judge: vague statement flagged as Level 2 | ≥ 0.70 |
| `tool_selection_accuracy` | `evals/graders.py` | `tool_calls[].name` matches expected list (order-insensitive) | — (logged) |
| `loop_safety` | `evals/graders.py` | `len(tool_calls) <= max_iterations` for the test case | Required |
| `tool_argument_validity` | `evals/graders.py` | Each tool call args pass Pydantic schema validation | Required |
| `phase_ordering_compliance` | `evals/graders.py` | `phase_status[N-1] == "complete"` before N starts | Required |
| `effort_estimate_plausibility` | `evals/graders.py` | `total_weeks` within 3× of nearest historical comparable | ≥ 0.80 |
| `github_ticket_structure` | `evals/graders.py` | Epic → Milestone, Task → Issue with label + milestone_number | 100% |
| `round_trip_sync` | `evals/graders.py` | Document upload → epic/task rows exist with GitHub IDs | ≥ 0.90 |

### Semantic grader

| Grader | Implementation | Threshold |
|--------|---------------|-----------|
| `semantic_relevance` | Cosine similarity: query embedding vs. retrieved chunk embeddings (mean) | ≥ 0.70 |

Uses the same `text-embedding-3-small` / 1536-dim contract as production. Never use a different model in evals.

### LLM-as-judge graders

| Grader | Library | Threshold |
|--------|---------|-----------|
| `groundedness` | Custom prompt (see below) | ≥ 0.70 |
| `proposal_completeness` | DeepEval G-Eval | ≥ 0.75 |
| `tech_stack_rationale_quality` | DeepEval G-Eval | ≥ 0.70 |
| `tbd_vague_detection` | Custom LLM-as-judge prompt | ≥ 0.70 |

**Groundedness judge prompt (canonical — do not modify without re-running regression suite):**

```python
# REGRESSION: do not change this prompt without re-running evals/regression_suite.py
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

## 5. AI Engineering Metrics Coverage

This section maps each graded axis (system design · eval coverage · cost analysis) to concrete metrics and where they surface.

### 5.1 Retrieval metrics (Phase 1 & 2)

| Metric | Source | Target | Surfaces in |
|--------|--------|--------|-------------|
| Context recall | RAGAS | ≥ 0.80 | `results/eval_results_*.json` + Metrics / Retrieval tab |
| Answer relevancy | RAGAS | ≥ 0.75 | Same |
| Reranker precision improvement | Custom | ≥ 70% | Same |
| Adjacent chunk cosine similarity | Custom | < 0.85 | Logged at ingestion time; P1-AC9 |
| Chunk size distribution (P90/P10) | Custom | P90 < 600, P10 > 50 tokens | Logged at ingestion time; P1-AC8 |

### 5.2 LLM output quality metrics (Phases 2–6)

| Metric | Source | Target | Surfaces in |
|--------|--------|--------|-------------|
| Groundedness | LLM-as-judge | ≥ 0.70 | Metrics / AI Quality tab |
| Proposal completeness | DeepEval G-Eval | ≥ 0.75 | Same |
| Tech stack rationale quality | DeepEval G-Eval | ≥ 0.70 | Same |
| TBD detection precision (Level 1) | Custom exact match | 100% | Metrics / Retrieval tab |
| TBD detection precision (Level 2) | LLM-as-judge | ≥ 0.70 | Same |
| Effort estimate plausibility | Custom range check | ≥ 0.80 | Metrics / AI Quality tab |

### 5.3 Agent reliability metrics (Phases 4–6)

| Metric | Source | Target | Surfaces in |
|--------|--------|--------|-------------|
| Tool selection accuracy | Custom (`tool_calls[].name`) | Logged (no threshold) | `results/` JSON |
| Loop safety (no runaway agents) | Custom `len(tool_calls)` | 100% within `max_iterations` | Metrics / Error Handling tab |
| Tool argument validity | Pydantic validation | 100% | Same |
| Phase ordering compliance | Custom state check | 100% | Same |
| GitHub sync success rate | Custom round-trip | ≥ 0.90 | Metrics / Error Handling tab |
| GitHub ticket schema validity | Custom schema check | 100% | Same |

### 5.4 Cost metrics

| Metric | Tracked in | Target |
|--------|-----------|--------|
| Input tokens per phase | `metrics` table, `TOKEN_TRACKING_ENABLED` | Logged every call |
| Output tokens per phase | Same | Logged every call |
| USD cost per LLM call | Derived: `(input × 0.0015 + output × 0.002) / 1000` | Displayed in Metrics / Token Usage tab |
| USD cost per full workflow | Aggregated | ≤ `MAX_COST_PER_WORKFLOW_USD` (0.50) |
| Cost estimate vs. actuals | Comparison table in eval report | ± 30% of estimate in §8 of CLAUDE.md |

**Phase-level cost budget (from CLAUDE.md §8):**

| Phase | Model | Budget tokens | Budget cost |
|-------|-------|---------------|-------------|
| 1 (embedding) | text-embedding-3-small | ~50K | ~$0.005 |
| 2 (RAG chat, 5 turns) | Gemini 2.5 Pro | ~30K | ~$0.11 |
| 3–4 (tool calls) | Gemini 2.5 Flash | ~10K | ~$0.01 |
| 5–6 (estimation + epics) | Claude Sonnet | ~20K | ~$0.06 |
| **Total** | | ~110K | **~$0.19** |

### 5.5 Latency metrics

| Metric | Captured in | Target |
|--------|-------------|--------|
| P50 / P95 latency per LangGraph node | `latency_logs` table | Displayed in Metrics / Latency tab |
| Phase 1 ingestion time | `latency_logs` | ≤ 30 s (P1-AC1) |
| Phase 2 chat response time | `latency_logs` | ≤ 10 s per turn (display target) |

### 5.6 Error handling metrics

| Metric | Tracked in | Target |
|--------|-------------|--------|
| Retry count per phase | `metrics` + `error_logs` | ≤ 3 per node |
| Failed GitHub sync attempts | `tasks.sync_status = "failed"` count | Displayed in Metrics / Error Handling tab |
| Unhandled exceptions | FastAPI 500 rate | 0 in eval runs |

---

## 6. CI / Regression Rules

### CI gate

```bash
python eval_suite.py --threshold 0.90
```

Fails the build if overall `pass@1` rate < 90%. Must run after every change to:
- Any file in `evals/`
- Any LLM prompt string
- Any LangGraph node in `backend/app/`
- `CLAUDE.md` section updates that change grader thresholds

### Regression suite graduation

Any test case with `pass_rate > 0.80` across 3 consecutive eval runs is graduated:

1. Set `"regression": true` in `test_cases.json` entry.
2. Add comment to the relevant prompt string:

```python
# REGRESSION: do not change this prompt without re-running evals/regression_suite.py
```

3. Run `evals/regression_suite.py` before merging any prompt change.

### Baseline

First full eval run before any prompt tuning is saved as `results/baseline_eval_run_001.json`. All subsequent runs include a `delta_vs_baseline` field in the summary object. Target baseline pass rate: ~40% (intentionally untuned).

### Google Drive sync

After each `eval_suite.py` run, results are synced:

```bash
rclone copy results/ gdrive:acuity/eval-results/
```

Configure the remote once with `rclone config`. The sync call is appended to the end of `eval_suite.py`.

---

## 7. Running Tests

### Backend unit + route tests

```bash
cd backend
pytest                        # all tests
pytest tests/test_schemas.py  # schema unit tests only
pytest tests/test_routes.py   # route smoke tests only
pytest -v --tb=short          # verbose with short tracebacks
```

### Eval harness (single test case)

```bash
python -m evals.harness --test-case tc-001
```

### Full eval suite with CI gate

```bash
python eval_suite.py --threshold 0.90
```

### Regression suite only

```bash
python evals/regression_suite.py
```

### Type checking + lint (frontend)

```bash
cd frontend
npx tsc --noEmit
npm run lint
```

### Type checking (backend)

```bash
cd evals          # mypy.ini lives here
mypy backend/app
```

---

*Last updated: 2026-06-06 — Week 11, AI Engineering Cohort*
