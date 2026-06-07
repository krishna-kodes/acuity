# Metrics Features

Reference for the `/projects/[id]/metrics` page — data sources, gaps, todos, and improvements.

---

## Overview

Five observability tabs backed by three DB tables (tokens, latency, errors) plus three new tables (quality, retrieval, eval results). All data is scoped per `project_id`.

**API endpoint:** `GET /api/v1/projects/{project_id}/metrics`  
**Auto-refresh:** 30 seconds

---

## Database Tables

| Table | Purpose | Populated by |
|-------|---------|-------------|
| `metrics` | LLM token usage + cost per phase | `record_tokens()` in workflow.py (all 6 phases) |
| `latency_logs` | Duration per LangGraph node | `record_latency()` / `timed_node()` context manager |
| `error_logs` | Structured error captures | `timed_node()` on exception |
| `quality_logs` | Groundedness score per chat turn | `_chat_turn_node` after LLM-as-judge runs |
| `retrieval_logs` | Reranker stats per RAG query | `_chat_turn_node` after `retrieve()` call |
| `eval_results` | Offline eval harness per-grader scores | `eval_suite.py --persist-db` |

---

## Tab 1: Token Usage & Cost

**Status:** Full real data

| Panel | Data source | Notes |
|-------|------------|-------|
| Total Tokens | `SUM(input_tokens + output_tokens)` from `metrics` | |
| Total Cost | `SUM(cost_usd)` from `metrics` | Rates from env vars `COST_PER_1K_*` |
| Input Tokens | `SUM(input_tokens)` from `metrics` | |
| Output Tokens | `SUM(output_tokens)` from `metrics` | |
| Daily Token Trend | `GROUP BY DATE(created_at)` on `metrics` | Falls back to sample data if no runs |
| Tokens by Phase | Grouped by `metrics.phase` | |

---

## Tab 2: AI Quality

**Status:** Live groundedness from `quality_logs`; full grader breakdown requires `--persist-db`

| Panel | Data source | Notes |
|-------|------------|-------|
| Avg Pass Rate | `eval_results` latest run avg, or mean of `quality_scores` | Falls back to sample data |
| Graders Passing | Count of scores ≥ 0.75 | From `eval_results` or sample |
| Groundedness | `AVG(score)` from `quality_logs WHERE score_type='groundedness'` | Live per-chat-turn signal |
| TBD Detection | `eval_results` grader named `tbd*` | Only after `--persist-db` run |
| Pass Rate by Grader chart | `eval_results` latest run | Shows "(sample)" until `--persist-db` is run |

### Running the Eval Harness

```bash
cd /path/to/acuity
python eval_suite.py --threshold 0.90 --persist-db
```

This writes one row per grader to the `eval_results` table. The AI Quality tab automatically shows the latest run.

---

## Tab 3: Retrieval

**Status:** Live proxy data from `retrieval_logs` (per-query reranker scores)

| Panel | Data source | Notes |
|-------|------------|-------|
| Context Recall (proxy) | `AVG(avg_score)` from `retrieval_logs` | `avg_score` = mean of all BERT reranker scores before top-n selection |
| Answer Relevancy (proxy) | `AVG(top_score)` from `retrieval_logs` | `top_score` = highest reranker score |
| Reranker Precision | Same as Answer Relevancy | BERT cross-encoder confidence |
| Query Rewrites | Hardcoded 3 | Matches `QUERY_REWRITE_COUNT` env var default |
| Chart | Per-query from `retrieval_logs` | Shows "(proxy)" label when live; "(sample)" if no data |

### Why "proxy"

True RAGAS-style context recall and answer relevancy require ground-truth relevant chunks (labels). These are only available in the offline eval harness (`evals/graders.py`). The live system uses BERT cross-encoder scores as a proxy — they correlate with relevancy but are not identical.

---

## Tab 4: Error Handling

**Status:** Full real data

| Panel | Data source | Notes |
|-------|------------|-------|
| Total Errors | `COUNT(*)` from `error_logs` | |
| GitHub Sync Fails | `COUNT(*) WHERE sync_status='failed'` on `epics` + `tasks` | |
| Recovery Rate | `synced / total` from `epics` + `tasks` sync_status | Returns `1.0` if no sync attempted |
| Error Phases | Distinct phases with errors in `error_logs` | |
| Errors by Phase chart | `error_logs` grouped by `phase` | |

---

## Tab 5: Latency

**Status:** Full real data

| Panel | Data source | Notes |
|-------|------------|-------|
| P50 Total | Sum of `PERCENTILE_50(duration_ms)` per node | |
| P95 Total | Sum of `PERCENTILE_95(duration_ms)` per node | |
| Slowest/Fastest Node | Max/min P50 from `latency_logs` | |
| P50/P95 per Node chart | `latency_logs` grouped by `node_name` | |

---

## Token Tracking Coverage

After this implementation, token usage is tracked for all phases:

| Phase | Method |
|-------|--------|
| Phase 2 (RAG Chat) | `astream()` usage_metadata (streaming accumulation) |
| Phase 3 (Tech Stack) | `with_structured_output(include_raw=True)` usage_metadata |
| Phase 4 (Team) | Sum `usage_metadata` across agent messages |
| Phase 5 (Estimation) | Sum `usage_metadata` across agent messages |
| Phase 6 (Epics) | Sum `usage_metadata` across agent messages |

---

## MetricInfo Tooltip Component

Every stat card and chart panel has an info icon (lucide-react `<Info />`). Hovering shows a tooltip with:
- **What it measures** — concise definition
- **Why it matters** — actionability and impact
- **Target** (optional) — threshold or benchmark

**Component:** `frontend/components/ui/metric-info.tsx`  
**Dependencies:** `@base-ui/react/tooltip` (already installed), `lucide-react` (already installed)

Usage:
```tsx
import { MetricInfo } from "@/components/ui/metric-info";

<MetricInfo
  what="Sum of all input + output tokens."
  why="Tracks model consumption."
  target="< 100k per project"
/>
```

Add to `MetricsStatCard` via the `infoIcon` prop (renders inline with the label text, distinct from the decorative `icon` prop).

---

## Gaps and Todos

| Gap | Priority | Effort | Notes |
|-----|---------|--------|-------|
| True RAGAS recall/precision in live system | Medium | High | Requires embedding ground truth labels into the pipeline; not feasible without a curated eval corpus per project |
| Per-turn TBD detection quality tracking | Medium | Low | Log TBD detection hit rate per chat turn to `quality_logs` |
| Cost breakdown by model (Gemini vs Claude vs OpenAI) | Low | Low | `metrics.model` column exists; add a breakdown chart |
| Cumulative cost alert / budget gate | High | Medium | Add `MAX_COST_PER_WORKFLOW_USD` check in metrics endpoint; surface warning in UI |
| Retrieval chart: show n_retrieved vs n_reranked | Low | Low | Already in `retrieval_logs`; add a second chart |
| Error drill-down: show traceback on click | Medium | Medium | `error_logs.traceback` column exists; add expandable row in UI |
| Phase latency trend over time | Low | Medium | `latency_logs.created_at` supports time-series grouping |
| Eval harness auto-run on deploy | Medium | Medium | Add `eval_suite.py --persist-db` to CI pipeline post-deploy |

---

## Improvements

- **Streaming latency**: Currently P50/P95 computed in Python with `statistics.median()`. Could move to SQLite percentile approximation for large datasets.
- **Groundedness threshold alert**: Surface a warning in the AI Quality tab if `avg_groundedness < GROUNDEDNESS_THRESHOLD` (env var).
- **Token budget progress bar**: Show remaining budget vs `MAX_COST_PER_WORKFLOW_USD` as a progress indicator on the Token Usage tab.
- **Eval run history**: Show a list of past `eval_suite.py` runs in the AI Quality tab with timestamps and pass rates.
- **Sync retry button**: Add a "Retry Failed Syncs" button in the Error Handling tab that re-triggers failed epics/tasks.

---

## Environment Variables (metrics-related)

```bash
METRICS_ENABLED=true
TOKEN_TRACKING_ENABLED=true
COST_PER_1K_INPUT_TOKENS=0.0015
COST_PER_1K_OUTPUT_TOKENS=0.002
MAX_COST_PER_WORKFLOW_USD=0.50
GROUNDEDNESS_THRESHOLD=0.7
GROUNDEDNESS_CHECK_ENABLED=true
```
