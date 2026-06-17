# Improvements Design Document

**Project:** AI-Driven Project Management Tool (Acuity)
**Status:** Living document — tracks post-MVP improvements beyond `capstone_project_design_document_v2.md`
**Last updated:** 2026-06-13

> **Scope.** This document records production-grade improvements layered on top of the MVP. It is the source of truth for the SDLC-loop-closing features. Where it conflicts with the v2 design doc, **this document wins** for the features it covers.

---

## 1. Motivation

The MVP pipeline stops at ticket creation: `doc → refine → tech stack → team → estimate → epics → sync GitHub`. It is **write-only** — once epics/tasks are pushed to GitHub the tool is blind to what happens next. Two consequences:

1. The `actual_points` columns exist in the data model but are never populated.
2. Effort estimation has no feedback — it cannot learn from how previous projects actually delivered.

These improvements close the **plan → execute → learn** loop, which is the highest-leverage upgrade across all three grading axes (system design · eval coverage · cost analysis).

---

## 2. Feature Roadmap

| # | Feature | Stage | Notes |
|---|---------|-------|-------|
| **1** | **Bidirectional GitHub sync** | **Shipped** | Pull issue/milestone state + actuals back into DB |
| **2** | **Estimation accuracy feedback loop** | **Shipped** | Calibrate future estimates from realized actuals |
| 3 | Requirements traceability matrix | Planned | proposal § → epic → task → issue; coverage gaps |
| 4 | Acceptance criteria + DoD (Gherkin) | Planned | per-story testable criteria |
| 5 | Dependency graph + critical path | Planned | epic/task DAG, topological order |
| 6 | Auto status report | Planned | GitHub state → narrative report |
| 7 | Sprint plan / capacity allocation | Planned | estimates + velocity + deps → sprints |
| 8 | Per-task assignee recommendation | Planned | `employee_skills` → `tasks.assignee` |
| 9 | Auto-split oversized stories (>13 pts) | Planned | grooming automation |
| 10 | Requirements diff + change impact | Planned | re-upload → semantic diff → delta re-sync |
| 11 | Idempotent sync hardening | Partial | upsert-by-title exists; key by stored numbers |

Sections 3–6 below document the **shipped** features (#1, #2) in full. Section 7 captures the planned backlog at design granularity.

---

## 3. ADR-101: Bidirectional GitHub Sync (#1)

### Decision

Add a **read-back path** to the GitHub sync. After epics/tasks are pushed, a pull operation reads each remote's current state (open/closed, `closed_at`, realized points) back into the DB. This populates `actual_points` and unlocks the feedback loop (ADR-102).

The pull is **idempotent** — it keys on the persisted `github_milestone_number` / `github_issue_number`, so re-running converges to the same DB state.

### Trigger model (MVP)

- **Poll endpoint:** `POST /api/v1/projects/{id}/sync/pull` — manual "Refresh status" button on the Epics page.
- Webhook receiver (`/webhooks/github`) deferred — needs a public URL; the poll endpoint covers local demo + grading. See §7.

### `actual_points` resolution contract

GitHub has **no native story-point field**. Realized points per task are resolved in this documented order:

1. Issue label `actual-points:N` — dev sets the realized value on close (authoritative).
2. Issue label `points:N` — planning estimate carried on the issue.
3. Fallback: `task.estimated_points` if the issue is **closed** (delivered its estimate); `0` if still **open**.

Implemented in [`resolve_actual_points`](backend/app/services/github_pull.py). Unit-tested across all three tiers.

> **Operational note for PMs/devs:** to capture true velocity (not just estimate-carried-forward), add an `actual-points:N` label to each issue when closing it. Without it, closed issues count their original estimate.

### Roll-up

- Epic `actual_points` = Σ task `actual_points`.
- Epic `remote_state` = milestone state from `get_milestone`; falls back to "closed when all tasks closed" if the milestone read fails.
- Project marked `complete` when every synced epic has `remote_state == "closed"`.

### Schema changes

```sql
-- epics
ALTER TABLE epics ADD COLUMN actual_points INTEGER;
ALTER TABLE epics ADD COLUMN remote_state  VARCHAR(20);   -- 'open' | 'closed'
ALTER TABLE epics ADD COLUMN closed_at     DATETIME;

-- tasks
ALTER TABLE tasks ADD COLUMN actual_points INTEGER;
ALTER TABLE tasks ADD COLUMN remote_state  VARCHAR(20);
ALTER TABLE tasks ADD COLUMN closed_at     DATETIME;
```

Migration: `alembic/versions/f1a2b3c4d5e6_add_actuals_and_estimation_outcomes.py` (down_revision `d40caa69f6fa`).

### MCP read tool

```python
@mcp.tool
def get_milestone(repo: str, number: int) -> dict:
    """state ('open'|'closed'), open/closed issue counts, due_on, closed_at."""
```
`get_github_repo_issues(repo, milestone)` already existed and returns full issue JSON (`state`, `closed_at`, `labels`) — reused. PRs are filtered out (`pull_request` key).

### Bug fixed en route

The original sync handler blanket-set every epic/task `sync_status = synced` even when a per-item create failed. Now: when the provider reports `failed == 0`, all items are `synced`; on a **partial** failure, status is derived per-item from whether a tracker ref came back. ([projects.py](backend/app/routers/projects.py), sync handler.)

### Endpoint

```
POST /api/v1/projects/{id}/sync/pull
→ {
    updated: int,            # tasks refreshed from their remote issue
    closed: int,             # tasks now closed
    still_open: int,
    skipped_unsynced: int,   # epics with no remote milestone yet
    outcomes_recorded: int,  # estimation_outcomes rows written this pull
    project_complete: bool
  }
```

---

## 4. ADR-102: Estimation Accuracy Feedback Loop (#2)

### Decision

Once a project's epics close on the tracker, record realized estimate-vs-actual per epic into a dedicated `estimation_outcomes` table. Aggregate those outcomes into a **calibration factor** that nudges future estimates toward what teams actually deliver. The estimator becomes self-improving.

Depends hard on ADR-101 — calibration needs `actual_points`, which only the read-back fills.

### Why a separate table

`historical_projects` is Faker-seeded reference data. Realized outcomes are kept in `estimation_outcomes` so the learn-loop corpus stays clean and is never confused with seed data.

```sql
CREATE TABLE estimation_outcomes (
  id               INTEGER PRIMARY KEY,
  project_id       INTEGER NOT NULL,   -- indexed
  epic_id          INTEGER,
  domain           VARCHAR(255),
  category         VARCHAR(100),       -- dominant task label, e.g. "backend"
  estimated_points INTEGER,
  actual_points    INTEGER,
  created_at       DATETIME
);
```

### Calibration factor

`factor = mean(actual / estimated)` over matching outcomes.

- **Bucket resolution** (first bucket with ≥ `MIN_SAMPLES` wins): `domain+category` → `category` → `domain` → `global`.
- **Cold start:** fewer than `MIN_SAMPLES = 3` rows → factor `1.0` (no-op). Thin corpus never distorts early projects.
- **Clamp:** `[0.5, 2.0]` — one outlier can't 2×+ an estimate.

Implemented in [`get_calibration`](backend/app/services/calibration.py).

### Recording outcomes

`record_outcomes(project, db)` runs when a pull marks the project complete. Idempotent per `(project_id, epic_id)` — re-running writes no duplicates. Category = dominant task label on the epic.

### Wiring into estimation

[`_phase_5_estimate_node`](backend/app/services/workflow.py) (Phase 5):

1. **Fixed a latent gap:** `estimate_effort` now passes each reference project's `actual_points` to the LLM (previously only `estimated_points` was shown — actuals were silently dropped).
2. After the LLM returns `total_points`, multiply by the calibration factor (resolved by project domain). Original value preserved as `raw_total_points`; factor/samples/bucket attached to the effort dict for display.

### Metrics surface

`GET /api/v1/projects/{id}/metrics` gains `estimation_accuracy`:

```python
estimation_accuracy: {
  per_epic: [{ epic, estimated, actual }],
  estimated_total, actual_total,
  bias_pct,              # +ve = under-estimated (actual > estimate)
  mae_pct,               # mean absolute % error across epics
  calibration_factor,    # multiplier applied to future estimates
  calibration_samples,   # outcomes backing the factor
  calibration_bucket
}
```

---

## 5. Frontend Changes

### Epics page (`/projects/[id]/epics`)
- **"Refresh status"** button → `POST /sync/pull`, then refetch epics. Toast reports closed/open counts, or "project complete" when calibration is recorded.
- Per epic/task: **actual-points badge** (green under-estimate / amber over-estimate / neutral) and a **closed dot** when the remote is closed.
- `getEpics` response + `EpicItem`/`TaskItem` extended with `actualPoints` / `remoteState`.

### Metrics page (`/projects/[id]/metrics`)
- New **Estimation** tab (6th tab):
  - Stat cards: Estimate Bias, Mean Abs Error, Calibration Factor, Outcome Samples.
  - Bar chart: estimated vs actual points per closed epic.
  - Empty state guides the PM to sync + Refresh once issues close.

---

## 6. Tests / Evals

[backend/tests/test_bidirectional_sync.py](backend/tests/test_bidirectional_sync.py) — 10 tests, all passing:

| Grader | What it checks | Result |
|--------|----------------|--------|
| `actual_points` resolution contract | All 3 fallback tiers + tier-1 precedence | ✅ |
| Pull fills actuals + state | task/epic `actual_points`, `remote_state`, `closed_at` | ✅ |
| Pull idempotency | Run twice → identical DB state | ✅ |
| Record outcomes + calibration | Idempotent write; factor converges to mean(actual/est) after MIN_SAMPLES | ✅ |
| Accuracy summary bias | `bias_pct` correct for known est/actual | ✅ |
| `/sync/pull` endpoint | Marks project complete, records outcomes | ✅ |

GitHub MCP calls are monkeypatched — no network. The 1 pre-existing sync-status test was updated to reflect the bug fix. Other unrelated suite failures (rag/pii/ingestion/migrations/seed) pre-date this work (env/keys/seed-count) and fail on a clean tree too.

---

## 7. Planned Backlog (design notes)

### #11 — Webhook receiver (sync hardening)
`POST /api/v1/webhooks/github`, HMAC-verified via `GITHUB_WEBHOOK_SECRET`, routes `issues`/`milestone` events to the same `pull_sync_state` path. Needs a public URL (ngrok/deploy). Poll endpoint is the MVP substitute.

### #3 — Requirements traceability matrix
Link proposal section → epic → task → issue using IDs already persisted. Surface coverage gaps (requirement with no ticket; ticket with no source = scope creep). Cheap, pure-accuracy.

### #4 — Acceptance criteria + DoD
Gherkin Given/When/Then per story, grounded in proposal section + clarifications. New eval: "every story has measurable AC."

### #5 — Dependency graph + critical path
Extract task dependencies from descriptions → DAG → topological order + critical path. Feeds sprint planning. Render on Epic Review.

### #6 — Auto status report
GitHub issue states → done/in-progress/blocked + % complete + slip risk. Counts zero-LLM; narrative LLM-only.

### #7 — Sprint plan / capacity allocation
Pack stories into sprints from estimates + team velocity + dependencies (#5).

### #8 — Per-task assignee recommendation
Match task tech tags to `employee_skills` + availability → `tasks.assignee` → GitHub `assignees` on sync.

### #9 — Auto-split oversized stories
Flag stories >13 pts, LLM-split into sub-tasks. Smaller stories estimate better — compounds with #2.

### #10 — Requirements diff + change impact
Re-upload revised doc → cosine diff over per-project embeddings → affected epics/tasks → delta-only re-sync (reuses idempotency keys).

---

## 8. File Index (shipped #1 + #2)

| Area | File |
|------|------|
| Migration | `backend/alembic/versions/f1a2b3c4d5e6_add_actuals_and_estimation_outcomes.py` |
| Models | `backend/app/models/sync.py`, `backend/app/models/reference.py` (`EstimationOutcome`) |
| MCP read tool | `backend/app/mcp/github_server.py` (`get_milestone`) |
| Pull service | `backend/app/services/github_pull.py` |
| Calibration | `backend/app/services/calibration.py` |
| Estimation wiring | `backend/app/services/workflow.py` |
| Endpoints / metrics | `backend/app/routers/projects.py` |
| Schemas | `backend/app/schemas/sync.py` (`PullSyncResponse`), `backend/app/schemas/metrics.py` (`EstimationAccuracy`) |
| Tests | `backend/tests/test_bidirectional_sync.py` |
| Frontend — epics | `frontend/app/(app)/projects/[id]/epics/page.tsx`, `frontend/components/epic-task-list-item.tsx`, `frontend/lib/api.ts` |
| Frontend — metrics | `frontend/app/(app)/projects/[id]/metrics/page.tsx` |
