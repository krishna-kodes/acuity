# Effort Estimate Export (CSV + XLSX) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two streaming export endpoints (`?format=csv` and `?format=xlsx`) for effort estimate data, with download buttons on the Estimation page and three tests covering the new endpoints.

**Architecture:** A new `estimate_export.py` service module generates CSV bytes and openpyxl XLSX bytes; a thin endpoint in `projects.py` handles routing, phase guard, and `StreamingResponse` wrapping; two anchor-tag buttons in `estimation/page.tsx` trigger browser downloads.

**Tech Stack:** Python `csv`, `io`, `json`, `openpyxl==3.1.5`, FastAPI `StreamingResponse`, Next.js `<a download>`

---

## File Map

| Action | Path | Purpose |
|---|---|---|
| Create | `backend/app/services/estimate_export.py` | `build_estimate_csv` + `build_estimate_xlsx` |
| Modify | `backend/app/routers/projects.py` | Add `export_estimate` endpoint after `export_proposal` |
| Modify | `backend/requirements.txt` | Add `openpyxl==3.1.5` |
| Modify | `backend/tests/test_routes_coverage.py` | Add 3 export tests |
| Modify | `frontend/lib/api.ts` | Add `getEstimateExportUrl` |
| Modify | `frontend/app/(app)/projects/[id]/estimation/page.tsx` | Add Export CSV / Export XLSX buttons |

---

## Task 1: Add openpyxl dependency

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1.1: Add openpyxl to requirements.txt**

Open `backend/requirements.txt`. After the `python-docx==1.2.0` line, add:

```
openpyxl==3.1.5
```

- [ ] **Step 1.2: Install the dependency**

```bash
cd backend
source .venv/bin/activate
pip install openpyxl==3.1.5
```

Expected: `Successfully installed openpyxl-3.1.5 et-xmlfile-...`

- [ ] **Step 1.3: Verify import works**

```bash
python -c "import openpyxl; print(openpyxl.__version__)"
```

Expected: `3.1.5`

- [ ] **Step 1.4: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add openpyxl==3.1.5 for estimate XLSX export"
```

---

## Task 2: Write the three failing tests

**Files:**
- Modify: `backend/tests/test_routes_coverage.py`

**Context:** The existing conftest seeds a project at `phase=ProjectPhase.estimation`. `_POST_ESTIMATION_PHASES = {ProjectPhase.estimation, ProjectPhase.epics, ProjectPhase.complete}` — so the guard passes for the seeded project. The `assignees` column on `Task` is plain `Text` (JSON string); write with `json.dumps(["alice"])`.

- [ ] **Step 2.1: Add imports and three tests at the bottom of test_routes_coverage.py**

Append this block to the end of `backend/tests/test_routes_coverage.py`:

```python
# ---------------------------------------------------------------------------
# GET /projects/{id}/export/estimate
# ---------------------------------------------------------------------------

def _seed_epic_and_task(db_session, project_id: str):
    """Helper: create one Epic + one Task for export tests."""
    import json
    from app.models.sync import Epic, Task
    from app.models.enums import SyncStatus

    epic = Epic(
        project_id=int(project_id),
        title="Auth Module",
        estimated_points=8,
        sync_status=SyncStatus.pending,
    )
    db_session.add(epic)
    db_session.flush()

    task = Task(
        epic_id=epic.id,
        title="Implement login",
        estimated_points=5,
        assignees=json.dumps(["alice"]),
        github_issue_url="https://github.com/org/repo/issues/1",
        sync_status=SyncStatus.pending,
    )
    db_session.add(task)
    db_session.commit()


def test_export_estimate_csv_returns_attachment(client, project_id, db_session):
    _seed_epic_and_task(db_session, project_id)
    resp = client.get(f"/api/v1/projects/{project_id}/export/estimate?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert "attachment" in resp.headers.get("content-disposition", "")
    body = resp.text
    assert "epic_title" in body
    assert "task_title" in body


def test_export_estimate_xlsx_returns_attachment(client, project_id, db_session):
    _seed_epic_and_task(db_session, project_id)
    resp = client.get(f"/api/v1/projects/{project_id}/export/estimate?format=xlsx")
    assert resp.status_code == 200
    assert "openxmlformats" in resp.headers.get("content-type", "")
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert len(resp.content) > 0


def test_export_estimate_phase_guard(client, project_id, db_session):
    from app.models.enums import ProjectPhase
    from app.models.project import Project
    db_session.query(Project).filter(
        Project.id == int(project_id)
    ).update({"phase": ProjectPhase.chat})
    db_session.commit()
    resp = client.get(f"/api/v1/projects/{project_id}/export/estimate?format=csv")
    assert resp.status_code == 409
    assert "Phase 5" in resp.json()["detail"]
```

- [ ] **Step 2.2: Run tests to verify they fail (endpoint doesn't exist yet)**

```bash
cd backend
pytest tests/test_routes_coverage.py::test_export_estimate_csv_returns_attachment \
       tests/test_routes_coverage.py::test_export_estimate_xlsx_returns_attachment \
       tests/test_routes_coverage.py::test_export_estimate_phase_guard -v
```

Expected: all 3 FAIL with `404` (endpoint not registered yet). If you see `ImportError` for `app.models.sync`, check that `__init__.py` imports the module — but it likely works since the conftest imports `app.models` with `noqa: F401`.

---

## Task 3: Create the export service

**Files:**
- Create: `backend/app/services/estimate_export.py`

**Key model facts (from `app/models/sync.py`):**
- `Epic.estimated_points: int | None` — use `epic.estimated_points or 0` for arithmetic
- `Epic.sync_status: SyncStatus` — a `str, Enum`; write as `epic.sync_status.value`
- `Task.assignees: str | None` — JSON-encoded text; parse with `json.loads`, take index 0
- `Task.estimated_points: int | None` — nullable; use `task.estimated_points or 0`
- `Task.sync_status: SyncStatus` — same as Epic

- [ ] **Step 3.1: Create the service file**

Create `backend/app/services/estimate_export.py` with this exact content:

```python
"""Streaming export builders for the effort estimate (Phase 5)."""

import csv
import io
import json

import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.models.sync import Epic, Task

_HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill("solid", fgColor="4472C4")
_BODY_FONT = Font(name="Arial")


def _first_assignee(raw: str | None) -> str:
    """Return the first element of a JSON-encoded assignees list, or ''."""
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
        return parsed[0] if parsed else ""
    except (json.JSONDecodeError, IndexError, TypeError):
        return ""


def _style_header(ws, headers: list[str], widths: list[int]) -> None:
    """Bold blue header row, freeze pane, autofilter."""
    for col_idx, width in enumerate(widths, start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"


def build_estimate_csv(project_id: int, db: Session) -> io.BytesIO:
    """Return a BytesIO of UTF-8 CSV with one row per task."""
    epics = db.query(Epic).filter(Epic.project_id == project_id).all()

    strio = io.StringIO()
    writer = csv.writer(strio)
    writer.writerow([
        "epic_title", "epic_estimated_points", "task_title", "task_assignee",
        "task_estimated_points", "confidence_low", "confidence_mid", "confidence_high",
        "github_issue_url", "sync_status",
    ])

    for epic in epics:
        tasks = db.query(Task).filter(Task.epic_id == epic.id).all()
        if not tasks:
            writer.writerow([
                epic.title, epic.estimated_points or "",
                "", "", "", "", "", "", "", "",
            ])
            continue
        for task in tasks:
            pts = task.estimated_points or 0
            writer.writerow([
                epic.title,
                epic.estimated_points or "",
                task.title,
                _first_assignee(task.assignees),
                pts,
                round(pts * 0.8, 1),
                pts,
                round(pts * 1.3, 1),
                task.github_issue_url or "",
                task.sync_status.value if task.sync_status else "",
            ])

    return io.BytesIO(strio.getvalue().encode("utf-8"))


def build_estimate_xlsx(project_id: int, db: Session) -> io.BytesIO:
    """Return a BytesIO of an XLSX workbook with Summary and Task Breakdown sheets."""
    epics = db.query(Epic).filter(Epic.project_id == project_id).all()

    wb = openpyxl.Workbook()

    # ── Sheet 1: Summary ─────────────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Summary"
    headers1 = ["Epic", "Estimated Points", "Actual Points", "Variance", "% Variance", "Sync Status"]
    widths1 = [40, 18, 18, 12, 14, 14]
    ws1.append(headers1)

    for row_idx, epic in enumerate(epics, start=2):
        ws1.cell(row=row_idx, column=1, value=epic.title).font = _BODY_FONT
        ws1.cell(row=row_idx, column=2, value=epic.estimated_points).font = _BODY_FONT
        ws1.cell(row=row_idx, column=3, value=None).font = _BODY_FONT          # actual_points — not in model
        ws1.cell(row=row_idx, column=4, value=f"=C{row_idx}-B{row_idx}").font = _BODY_FONT
        ws1.cell(row=row_idx, column=5, value=f'=IF(B{row_idx}=0,"—",D{row_idx}/B{row_idx})').font = _BODY_FONT
        ws1.cell(row=row_idx, column=6, value=epic.sync_status.value if epic.sync_status else "").font = _BODY_FONT

    _style_header(ws1, headers1, widths1)

    # ── Sheet 2: Task Breakdown ───────────────────────────────────────────────
    ws2 = wb.create_sheet("Task Breakdown")
    headers2 = ["Epic", "Task", "Assignee", "Est. Points", "Low", "Mid", "High", "GitHub Issue", "Sync Status"]
    widths2 = [35, 40, 20, 14, 8, 8, 8, 40, 14]
    ws2.append(headers2)

    task_row = 2
    for epic in epics:
        tasks = db.query(Task).filter(Task.epic_id == epic.id).all()
        for task in tasks:
            pts = task.estimated_points or 0
            row_vals = [
                epic.title,
                task.title,
                _first_assignee(task.assignees),
                pts,
                round(pts * 0.8, 1),
                pts,
                round(pts * 1.3, 1),
                task.github_issue_url or "",
                task.sync_status.value if task.sync_status else "",
            ]
            for col_idx, val in enumerate(row_vals, start=1):
                ws2.cell(row=task_row, column=col_idx, value=val).font = _BODY_FONT
            task_row += 1

    _style_header(ws2, headers2, widths2)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
```

- [ ] **Step 3.2: Verify the module imports cleanly**

```bash
cd backend
python -c "from app.services.estimate_export import build_estimate_csv, build_estimate_xlsx; print('OK')"
```

Expected: `OK`

---

## Task 4: Add the endpoint to projects.py

**Files:**
- Modify: `backend/app/routers/projects.py:974-998` (after `export_proposal`)

- [ ] **Step 4.1: Add the endpoint**

Open `backend/app/routers/projects.py`. Find the line:

```python
@router.get(
    "/projects/{project_id}/documents-list",
```

Insert the following block **immediately before** that line (i.e., after the `export_proposal` function ends at the closing `)`):

```python
@router.get("/projects/{project_id}/export/estimate")
def export_estimate(
    project_id: str,
    format: str = "xlsx",
    db: Session = Depends(get_db),
):
    """Download the effort estimate as CSV or XLSX (Phase 5 must be complete)."""
    if format not in ("csv", "xlsx"):
        raise HTTPException(status_code=400, detail="format must be csv or xlsx")

    project = _get_project_or_404(project_id, db)
    if project.phase not in _POST_ESTIMATION_PHASES:
        raise HTTPException(status_code=409, detail="Phase 5 not complete")

    from app.services.estimate_export import build_estimate_csv, build_estimate_xlsx

    if format == "csv":
        buf = build_estimate_csv(project.id, db)
        return StreamingResponse(
            buf,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=estimate_{project_id}.csv"},
        )

    buf = build_estimate_xlsx(project.id, db)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=estimate_{project_id}.xlsx"},
    )
```

- [ ] **Step 4.2: Run all three new tests**

```bash
cd backend
pytest tests/test_routes_coverage.py::test_export_estimate_csv_returns_attachment \
       tests/test_routes_coverage.py::test_export_estimate_xlsx_returns_attachment \
       tests/test_routes_coverage.py::test_export_estimate_phase_guard -v
```

Expected: all 3 PASS.

- [ ] **Step 4.3: Run the full test suite to check for regressions**

```bash
cd backend
pytest --tb=short -q
```

Expected: all pre-existing tests still pass.

- [ ] **Step 4.4: Commit backend**

```bash
git add backend/app/services/estimate_export.py \
        backend/app/routers/projects.py \
        backend/tests/test_routes_coverage.py
git commit -m "feat(export): add CSV + XLSX estimate export endpoint (Phase 5)"
```

---

## Task 5: Frontend — add export URL helper

**Files:**
- Modify: `frontend/lib/api.ts`

**Context:** `getProposalExportUrl` at line 115 of `api.ts` is the existing pattern — a one-liner that builds the full URL. Add the same pattern for estimates.

- [ ] **Step 5.1: Add getEstimateExportUrl to api.ts**

Open `frontend/lib/api.ts`. Find:

```typescript
export const getProposalExportUrl = (projectId: string): string =>
  `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/projects/${projectId}/export/proposal`
```

Add this immediately after that line:

```typescript
export const getEstimateExportUrl = (projectId: string, format: "csv" | "xlsx"): string =>
  `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/projects/${projectId}/export/estimate?format=${format}`
```

- [ ] **Step 5.2: Verify TypeScript compiles**

```bash
cd frontend
npx tsc --noEmit
```

Expected: no errors.

---

## Task 6: Frontend — add export buttons to Estimation page

**Files:**
- Modify: `frontend/app/(app)/projects/[id]/estimation/page.tsx`

**Context:** The action bar is at the bottom of the content div (around line 159). It currently has a single "Generate Epics & Tasks" button. The export buttons go in the same flex row, left of that button. Disabled state: `loading || !effort` — same logic that gates the proceed button on `proceeding`.

- [ ] **Step 6.1: Add the import for getEstimateExportUrl**

Open `frontend/app/(app)/projects/[id]/estimation/page.tsx`. Find:

```typescript
import { estimateEffort, getModules } from "@/lib/api";
```

Replace with:

```typescript
import { estimateEffort, getModules, getEstimateExportUrl } from "@/lib/api";
```

- [ ] **Step 6.2: Replace the action bar div**

Find this exact block (around line 159):

```tsx
        <div className="flex items-center justify-end pt-2 border-t border-border">
          <button
            onClick={handleProceed}
            disabled={proceeding}
            className={cn(
              "inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors",
              !proceeding ? "bg-primary text-primary-foreground hover:bg-accent-hover" : "bg-muted text-text-muted cursor-not-allowed"
            )}
          >
            {proceeding ? (
              <><svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}><path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" /></svg>Processing…</>
            ) : (
              <>Generate Epics &amp; Tasks<svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}><path d="M2 7h10M8 3l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" /></svg></>
            )}
          </button>
        </div>
```

Replace with:

```tsx
        <div className="flex items-center justify-between pt-2 border-t border-border">
          {/* Export buttons */}
          <div className="flex items-center gap-2">
            <a
              href={getEstimateExportUrl(id, "csv")}
              download
              aria-disabled={loading || !effort}
              className={cn(
                "inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium border border-border transition-colors",
                loading || !effort
                  ? "pointer-events-none opacity-40 text-text-muted"
                  : "text-foreground hover:bg-surface-subtle"
              )}
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}>
                <path d="M7 2v7M4 6l3 3 3-3M2 11h10" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Export CSV
            </a>
            <a
              href={getEstimateExportUrl(id, "xlsx")}
              download
              aria-disabled={loading || !effort}
              className={cn(
                "inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium border border-border transition-colors",
                loading || !effort
                  ? "pointer-events-none opacity-40 text-text-muted"
                  : "text-foreground hover:bg-surface-subtle"
              )}
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}>
                <path d="M7 2v7M4 6l3 3 3-3M2 11h10" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Export XLSX
            </a>
          </div>

          {/* Proceed */}
          <button
            onClick={handleProceed}
            disabled={proceeding}
            className={cn(
              "inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors",
              !proceeding ? "bg-primary text-primary-foreground hover:bg-accent-hover" : "bg-muted text-text-muted cursor-not-allowed"
            )}
          >
            {proceeding ? (
              <><svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}><path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" /></svg>Processing…</>
            ) : (
              <>Generate Epics &amp; Tasks<svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}><path d="M2 7h10M8 3l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" /></svg></>
            )}
          </button>
        </div>
```

- [ ] **Step 6.3: Verify TypeScript compiles**

```bash
cd frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6.4: Lint check**

```bash
cd frontend
npm run lint
```

Expected: no new errors.

- [ ] **Step 6.5: Commit frontend**

```bash
git add frontend/lib/api.ts \
        frontend/app/\(app\)/projects/\[id\]/estimation/page.tsx
git commit -m "feat(ui): add Export CSV / XLSX buttons to Estimation page"
```

---

## Task 7: Final smoke test

- [ ] **Step 7.1: Start backend and verify endpoints exist**

```bash
cd backend
uvicorn app.main:app --port 8000 &
curl -s http://localhost:8000/api/v1/projects/1/export/estimate?format=csv \
  -o /dev/null -w "%{http_code}\n"
```

Expected: `200` (if project 1 exists and is at estimation phase) or `409` (if phase guard fires). Either confirms the endpoint is registered. `404` means registration failed.

- [ ] **Step 7.2: Run full backend test suite one final time**

```bash
cd backend
pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 7.3: Kill dev server**

```bash
pkill -f "uvicorn app.main"
```
