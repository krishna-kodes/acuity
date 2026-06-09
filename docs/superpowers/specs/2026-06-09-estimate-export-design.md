# Effort Estimate Export — CSV & XLSX

**Date:** 2026-06-09
**Status:** Approved

---

## Overview

Two read-only export endpoints that stream the effort estimation data as a flat CSV or a two-sheet XLSX. Export buttons appear on the Estimation page. Both are gated behind phase 5 completion.

---

## Architecture

### New files
- `backend/app/services/estimate_export.py` — CSV and XLSX generation logic
- `backend/tests/test_export_estimate.py` (or appended to `test_routes_coverage.py`)

### Modified files
- `backend/app/routers/projects.py` — add `export_estimate` endpoint after `export_proposal`
- `backend/requirements.txt` — add `openpyxl==3.1.5`
- `frontend/lib/api.ts` — add `getEstimateExportUrl`
- `frontend/app/(app)/projects/[id]/estimation/page.tsx` — add Export CSV / Export XLSX buttons

---

## Backend

### Endpoint

```
GET /api/v1/projects/{project_id}/export/estimate?format=csv|xlsx
```

- No request body. No phase_status mutation.
- Registered in `projects.py` router (prefix `/api/v1` in `main.py`) — identical registration pattern to `export_proposal`.

### Phase guard

```python
if project.phase not in _POST_ESTIMATION_PHASES:
    raise HTTPException(status_code=409, detail="Phase 5 not complete")
```

`_POST_ESTIMATION_PHASES` is already defined: `{ProjectPhase.estimation, ProjectPhase.epics, ProjectPhase.complete}`.

### Error responses

| Condition | Status | Detail |
|---|---|---|
| Project not found | 404 | "Project not found" |
| Phase 5 not complete | 409 | "Phase 5 not complete" |
| Invalid format param | 400 | "format must be csv or xlsx" |

### Response headers

**CSV:**
```
Content-Type: text/csv
Content-Disposition: attachment; filename="estimate_{project_id}.csv"
```

**XLSX:**
```
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="estimate_{project_id}.xlsx"
```

Both use `StreamingResponse` with `io.StringIO` / `io.BytesIO` — no temp files written to disk.

---

## Service: `estimate_export.py`

### `build_estimate_csv(project_id: int, db: Session) -> io.StringIO`

Queries `epics` JOIN `tasks` (left join — epics with no tasks still appear with empty task columns).

**Columns (in order):**

| Column | Source |
|---|---|
| `epic_title` | `epic.title` |
| `epic_estimated_points` | `epic.estimated_points` |
| `task_title` | `task.title` |
| `task_assignee` | `task.assignees[0]` if non-empty, else `""` |
| `task_estimated_points` | `task.estimated_points` |
| `confidence_low` | `round(task.estimated_points * 0.8, 1)` |
| `confidence_mid` | `task.estimated_points` |
| `confidence_high` | `round(task.estimated_points * 1.3, 1)` |
| `github_issue_url` | `task.github_issue_url or ""` |
| `sync_status` | `task.sync_status` |

Rows with no tasks: `task_*` columns are empty strings, confidence columns are empty.

### `build_estimate_xlsx(project_id: int, db: Session) -> io.BytesIO`

Uses `openpyxl` direct cell writes (no pandas).

**Font:** Arial throughout (`Font(name="Arial")`).

**Header style (both sheets):**
- Bold, background fill `4472C4` (PatternFill solid), white font
- Row 1 frozen (`freeze_panes = "A2"`)
- Autofilter on row 1

#### Sheet 1 — "Summary"

| Col | Header | Width | Source |
|---|---|---|---|
| A | Epic | 40 | `epic.title` |
| B | Estimated Points | 18 | `epic.estimated_points` |
| C | Actual Points | 18 | _(empty — column not in model)_ |
| D | Variance | 12 | Excel formula `=C{row}-B{row}` |
| E | % Variance | 14 | Excel formula `=IF(B{row}=0,"—",D{row}/B{row})` |
| F | Sync Status | 14 | `epic.sync_status` |

One row per epic. Data rows start at row 2.

#### Sheet 2 — "Task Breakdown"

| Col | Header | Width | Source |
|---|---|---|---|
| A | Epic | 35 | `epic.title` |
| B | Task | 40 | `task.title` |
| C | Assignee | 20 | `task.assignees[0]` or `""` |
| D | Est. Points | 14 | `task.estimated_points` |
| E | Low | 8 | `round(task.estimated_points * 0.8, 1)` |
| F | Mid | 8 | `task.estimated_points` |
| G | High | 8 | `round(task.estimated_points * 1.3, 1)` |
| H | GitHub Issue | 40 | `task.github_issue_url or ""` |
| I | Sync Status | 14 | `task.sync_status` |

Plain values (not formulas) for Low/Mid/High.

---

## Frontend

### `frontend/lib/api.ts`

```ts
export const getEstimateExportUrl = (projectId: string, format: "csv" | "xlsx"): string =>
  `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/projects/${projectId}/export/estimate?format=${format}`
```

### `estimation/page.tsx`

Two `<a download>` buttons added in the action bar row (before "Generate Epics & Tasks" button):

- **Export CSV** → `href={getEstimateExportUrl(id, "csv")}`
- **Export XLSX** → `href={getEstimateExportUrl(id, "xlsx")}`

**Disabled state:** `pointer-events-none opacity-40` when `loading || !effort` (estimation not yet complete). Matches existing button disabled pattern in the page.

No new components. Inline anchor tags styled as buttons using existing Tailwind classes.

---

## Data Model Notes

- `Epic` model: `backend/app/models/sync.py` — relevant fields: `id, title, estimated_points, sync_status, github_milestone_url`
- `Task` model: same file — relevant fields: `id, epic_id, title, estimated_points, assignees (JSON array), github_issue_url, sync_status`
- `assignees` is a JSON-encoded array; export takes `assignees[0]` (first element) for the single-assignee display column

---

## Tests

Added to `backend/tests/test_routes_coverage.py`, using existing `client`, `project_id`, `db_session` fixtures. Conftest project is at `phase=ProjectPhase.estimation` → phase guard passes.

Each test seeds one Epic + one Task inline via `db_session`.

| Test | Asserts |
|---|---|
| `test_export_estimate_csv_returns_attachment` | 200, `text/csv` content-type, `attachment` in Content-Disposition, CSV header row in body |
| `test_export_estimate_xlsx_returns_attachment` | 200, `openxmlformats` in content-type, `len(response.content) > 0` |
| `test_export_estimate_phase_guard` | Updates project to `phase=ProjectPhase.chat`, asserts 409 |

---

## Constraints

- `openpyxl` only — no pandas
- No temp files — stream via `io.BytesIO` / `io.StringIO`
- No new environment variables
- No Google Sheets integration
- All errors: `{"detail": string}` (FastAPI default)
