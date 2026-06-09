# Modules Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the synchronous module extraction endpoint with an SSE streaming endpoint that emits `status → module → done` events, and update the UI to show a progress bar with per-module fade-in animation.

**Architecture:** Backend adds `POST /projects/{id}/modules/stream` — a `StreamingResponse` that streams LLM tokens via `astream()`, extracts flat `{...}` module objects via regex as they form, and emits each as an SSE event. Frontend adds `extractModulesStream` to `api.ts` (same SSE reader pattern as `generateProposalStream`), then updates `modules/page.tsx` with extraction status state, a progress bar, and CSS fade-in on new module rows.

**Tech Stack:** FastAPI `StreamingResponse`, `text/event-stream`, Python `re.finditer`, `langchain` `astream()`, React `useState`, Tailwind CSS, CSS `@keyframes`

---

## File Map

| File | Change |
|---|---|
| `backend/app/routers/projects.py` | Add `extract_modules_stream` endpoint after line ~1009 |
| `backend/tests/test_routes_coverage.py` | Add streaming endpoint tests |
| `frontend/lib/api.ts` | Add `extractModulesStream` after `extractModules` |
| `frontend/app/(app)/projects/[id]/modules/page.tsx` | Add state, progress bar, animation, rewire `runExtraction` |
| `frontend/app/globals.css` | Add `@keyframes moduleAppear` + `.module-row-appear` |

---

## Task 1: Backend — streaming endpoint

**Files:**
- Modify: `backend/app/routers/projects.py` (after the `extract_modules` function, ~line 1009)

- [ ] **Step 1: Add the streaming endpoint**

Open `backend/app/routers/projects.py`. After the closing of `extract_modules` (the `return ModulesResponse(...)` line), insert the following new endpoint:

```python
@router.post("/projects/{project_id}/modules/stream")
async def extract_modules_stream(
    project_id: str,
    db: Session = Depends(get_db),
):
    """SSE stream: emits status → module events → done for module extraction."""
    import uuid as _uuid
    from app.services.llm_factory import get_llm

    project = _get_project_or_404(project_id, db)

    proposal = (
        db.query(Proposal)
        .filter(Proposal.project_id == project.id)
        .order_by(Proposal.created_at.desc())
        .first()
    )

    sections_text = ""
    if proposal and proposal.content_json:
        try:
            raw = json.loads(proposal.content_json)
            sections = raw.get("sections", [])
            sections_text = "\n\n".join(
                f"## {s['heading']}\n{s['body']}" for s in sections
            )
        except Exception:
            pass

    prompt = (
        "You are a project analyst. Given this proposal, extract ALL discrete work modules.\n"
        "For each module output: title (concise noun phrase), label (one of: frontend, backend, "
        "devops, QA, PM, design, data, infra), description (one sentence).\n\n"
        f"Proposal sections:\n{sections_text}\n\n"
        'Respond ONLY with valid JSON:\n'
        '{"modules": [{"id": "<uuid4>", "title": "...", "label": "...", "description": "..."}, ...]}'
    )

    llm = get_llm()

    async def _generate():
        yield f'data: {json.dumps({"type": "status", "status": "started"})}\n\n'

        buffer = ""
        seen_ids: set[str] = set()
        modules: list[dict] = []

        if sections_text:
            async for chunk in llm.astream(prompt):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                buffer += token
                matches = list(re.finditer(r'\{[^{}]+\}', buffer))
                for match in matches:
                    try:
                        m = json.loads(match.group())
                        if {"title", "label"} <= m.keys() and m.get("title"):
                            mid = m.get("id") or str(_uuid.uuid4())
                            if mid not in seen_ids:
                                seen_ids.add(mid)
                                module = {
                                    "id": mid,
                                    "title": str(m["title"]),
                                    "label": str(m.get("label", "backend")),
                                    "description": str(m.get("description", "")),
                                }
                                modules.append(module)
                                yield f'data: {json.dumps({"type": "module", "module": module})}\n\n'
                    except (json.JSONDecodeError, KeyError):
                        pass
                if matches:
                    buffer = buffer[matches[-1].end():]

        project.modules_json = json.dumps(modules)
        db.commit()
        yield f'data: {json.dumps({"type": "done", "modules": modules, "count": len(modules)})}\n\n'

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 2: Verify the server starts without error**

```bash
cd backend && source .venv/bin/activate && python -c "from app.main import app; print('OK')"
```

Expected output: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/projects.py
git commit -m "feat(backend): add SSE streaming endpoint for module extraction"
```

---

## Task 2: Backend — test the streaming endpoint

**Files:**
- Modify: `backend/tests/test_routes_coverage.py`

- [ ] **Step 1: Write the failing test**

Add to the end of `backend/tests/test_routes_coverage.py`:

```python
# ---------------------------------------------------------------------------
# POST /projects/{id}/modules/stream — SSE streaming
# ---------------------------------------------------------------------------

import json
from unittest.mock import AsyncMock, MagicMock, patch


def test_extract_modules_stream_emits_sse_events(client, project_id, db_session):
    """Streaming endpoint emits started, one+ module events, and done."""
    from app.models.project import Proposal as _Proposal

    proposal = db_session.query(_Proposal).filter(_Proposal.project_id == int(project_id)).first()
    if not proposal:
        proposal = _Proposal(
            project_id=int(project_id),
            document_id=0,
            content_path="documents/stub.docx",
        )
        db_session.add(proposal)
    proposal.content_json = json.dumps({
        "sections": [{"heading": "Overview", "body": "Build an e-commerce platform."}]
    })
    db_session.commit()

    # Simulate LLM streaming tokens that form two flat module objects
    chunks = [
        MagicMock(content='{"modules": ['),
        MagicMock(content='{"id": "m-1", "title": "Auth Service", "label": "backend", "description": "Handles login."}'),
        MagicMock(content=', {"id": "m-2", "title": "Product UI", "label": "frontend", "description": "Product pages."}'),
        MagicMock(content="]}"),
    ]

    async def _astream(prompt):
        for c in chunks:
            yield c

    mock_llm = MagicMock()
    mock_llm.astream = _astream

    with patch("app.services.llm_factory.get_llm", return_value=mock_llm):
        resp = client.post(f"/api/v1/projects/{project_id}/modules/stream")

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = [
        json.loads(line[6:])
        for line in resp.text.splitlines()
        if line.startswith("data: ")
    ]

    assert events[0] == {"type": "status", "status": "started"}

    module_events = [e for e in events if e["type"] == "module"]
    assert len(module_events) == 2
    assert module_events[0]["module"]["title"] == "Auth Service"
    assert module_events[0]["module"]["label"] == "backend"
    assert module_events[1]["module"]["title"] == "Product UI"

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["count"] == 2
    assert len(done_events[0]["modules"]) == 2


def test_extract_modules_stream_empty_proposal(client, project_id, db_session):
    """Streaming endpoint emits started+done with no modules when proposal has no content."""
    from app.models.project import Proposal as _Proposal

    proposal = db_session.query(_Proposal).filter(_Proposal.project_id == int(project_id)).first()
    if not proposal:
        proposal = _Proposal(
            project_id=int(project_id),
            document_id=0,
            content_path="documents/stub.docx",
        )
        db_session.add(proposal)
    proposal.content_json = None
    db_session.commit()

    resp = client.post(f"/api/v1/projects/{project_id}/modules/stream")

    assert resp.status_code == 200
    events = [
        json.loads(line[6:])
        for line in resp.text.splitlines()
        if line.startswith("data: ")
    ]
    assert events[0] == {"type": "status", "status": "started"}
    assert events[-1]["type"] == "done"
    assert events[-1]["count"] == 0
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_routes_coverage.py::test_extract_modules_stream_emits_sse_events tests/test_routes_coverage.py::test_extract_modules_stream_empty_proposal -v
```

Expected: both tests PASS. The endpoint was added in Task 1 and the patch targets `app.services.llm_factory.get_llm` — the right source since `get_llm` is imported at call time inside the endpoint function body.

- [ ] **Step 3: Run full backend test suite to catch regressions**

```bash
cd backend && source .venv/bin/activate && pytest --tb=short -q
```

Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_routes_coverage.py
git commit -m "test(backend): add SSE streaming tests for modules extraction endpoint"
```

---

## Task 3: Frontend — `extractModulesStream` in `api.ts`

**Files:**
- Modify: `frontend/lib/api.ts` (after `extractModules`, ~line 476)

- [ ] **Step 1: Add `extractModulesStream` after `extractModules`**

In `frontend/lib/api.ts`, after the `extractModules` function, add:

```ts
export async function extractModulesStream(
  projectId: string,
  onStatus: (status: string) => void,
  onModule: (module: Module) => void,
  onDone: (result: { modules: Module[]; count: number }) => void,
): Promise<void> {
  const res = await fetch(
    `${_apiBase()}/api/v1/projects/${projectId}/modules/stream`,
    { method: "POST" },
  )
  if (!res.ok) throw new Error(`Extract modules stream failed: ${res.status}`)

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split("\n")
    buffer = lines.pop() ?? ""
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue
      const data = line.slice(6).trim()
      if (!data) continue
      try {
        const event = JSON.parse(data)
        if (event.type === "status") onStatus(event.status as string)
        else if (event.type === "module") onModule(event.module as Module)
        else if (event.type === "done")
          onDone({ modules: event.modules as Module[], count: event.count as number })
      } catch { /* skip malformed SSE line */ }
    }
  }
}
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat(frontend): add extractModulesStream SSE client function"
```

---

## Task 4: Frontend — progress bar, streaming state, row animation

**Files:**
- Modify: `frontend/app/(app)/projects/[id]/modules/page.tsx`
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Add CSS animation to `globals.css`**

Open `frontend/app/globals.css`. Append at the end of the file:

```css
@keyframes moduleAppear {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.module-row-appear {
  animation: moduleAppear 0.25s ease-out forwards;
}
```

- [ ] **Step 2: Update the import in `modules/page.tsx`**

Change the import at the top of the file from:

```ts
import {
  extractModules,
  getModules,
  saveModules,
  approveModules,
} from "@/lib/api";
```

to:

```ts
import {
  extractModulesStream,
  getModules,
  saveModules,
  approveModules,
} from "@/lib/api";
```

- [ ] **Step 3: Add `ExtractionStatus` type and two new state variables**

After the existing state declarations (after the `extractionFiredRef` line), add:

```ts
type ExtractionStatus = "idle" | "started" | "generating" | "done"
const [extractionStatus, setExtractionStatus] = useState<ExtractionStatus>("idle")
const [extractionTotal, setExtractionTotal] = useState(0)
```

- [ ] **Step 4: Replace `runExtraction` with the streaming version**

Replace the entire `runExtraction` function with:

```ts
async function runExtraction(isCancelled?: () => boolean) {
  setExtracting(true)
  setExtractionStatus("started")
  setModules([])
  setExtractionTotal(0)
  try {
    await extractModulesStream(
      id,
      (status) => {
        if (!isCancelled?.()) setExtractionStatus(status as ExtractionStatus)
      },
      (module) => {
        if (!isCancelled?.()) {
          setModules((prev) => [...prev, module])
          setExtractionStatus("generating")
        }
      },
      (done) => {
        if (!isCancelled?.()) {
          setModules(done.modules)
          setExtractionTotal(done.count)
          setExtractionStatus("done")
          setIsDirty(false)
        }
      },
    )
  } catch {
    if (!isCancelled?.()) toast.error("Extraction failed — add modules manually")
  } finally {
    setExtracting(false)
  }
}
```

- [ ] **Step 5: Add the progress bar between the header and the module list**

In the JSX, locate the `{/* Loading state */}` comment block. Replace the entire `{extracting && modules.length === 0 ? ... : <>...</>}` conditional with the following (the progress bar is now separate from the loading state; modules appear incrementally):

```tsx
{/* Progress bar — visible during and after extraction */}
{extractionStatus !== "idle" && (
  <div className="flex flex-col gap-2 bg-card border border-border rounded-xl px-4 py-3">
    <div className="flex items-center justify-between">
      <span
        className={cn(
          "text-xs font-medium",
          extractionStatus === "started" && "text-amber-600",
          extractionStatus === "generating" && "text-blue-600 animate-pulse",
          extractionStatus === "done" && "text-green-600",
        )}
      >
        {extractionStatus === "started" && "Analyzing proposal…"}
        {extractionStatus === "generating" &&
          `Generating modules… (${modules.length} found)`}
        {extractionStatus === "done" &&
          `${modules.length} module${modules.length !== 1 ? "s" : ""} extracted ✓`}
      </span>
      {extractionStatus === "done" && (
        <svg
          className="w-4 h-4 text-green-500"
          fill="none"
          viewBox="0 0 16 16"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path d="M3 8l4 4 6-7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
    </div>
    <div className="w-full h-1.5 bg-border rounded-full overflow-hidden">
      <div
        className={cn(
          "h-full rounded-full transition-all duration-500",
          extractionStatus === "done" ? "bg-green-500" : "bg-primary",
        )}
        style={{
          width:
            extractionStatus === "started"
              ? "5%"
              : extractionStatus === "done"
                ? "100%"
                : `${Math.min(
                    95,
                    Math.round(
                      (modules.length / Math.max(modules.length, extractionTotal || 10)) * 100,
                    ),
                  )}%`,
        }}
      />
    </div>
  </div>
)}

{/* Module groups */}
{[...labelOrder, ...otherLabels].length === 0 && extractionStatus === "idle" ? (
  <div className="bg-card border border-border rounded-xl py-10 flex flex-col items-center gap-2 text-center">
    <p className="text-sm text-text-muted">
      No modules yet — add one below or re-extract from the proposal.
    </p>
  </div>
) : (
  <>
    {[...labelOrder, ...otherLabels].length > 0 && (
      <div className="flex flex-col gap-3">
        {[...labelOrder, ...otherLabels].map((label) => (
          <div key={label} className="bg-card border border-border rounded-xl overflow-hidden">
            {/* Group header */}
            <div className="px-4 py-2.5 border-b border-border bg-surface-subtle/50 flex items-center gap-2">
              <span
                className={cn(
                  "text-[11px] font-semibold px-2 py-0.5 rounded-full border",
                  labelStyle(label),
                )}
              >
                {label}
              </span>
              <span className="text-[11px] text-text-muted">
                {grouped[label].length} module{grouped[label].length !== 1 ? "s" : ""}
              </span>
            </div>

            {/* Module rows */}
            <div className="divide-y divide-border">
              {grouped[label].map((m) => (
                <div
                  key={m.id}
                  className={cn(
                    "flex items-center gap-3 px-4 py-2.5 group",
                    extractionStatus === "generating" && "module-row-appear",
                  )}
                >
                  {editingId === m.id ? (
                    <input
                      autoFocus
                      value={editingTitle}
                      onChange={(e) => setEditingTitle(e.target.value)}
                      onBlur={() => commitEdit(m.id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitEdit(m.id)
                        if (e.key === "Escape") setEditingId(null)
                      }}
                      className="flex-1 min-w-0 text-sm bg-transparent border-b border-primary outline-none py-0.5"
                    />
                  ) : (
                    <span
                      className="flex-1 min-w-0 text-sm text-foreground cursor-text truncate"
                      onClick={() => startEdit(m)}
                      title="Click to edit"
                    >
                      {m.title}
                    </span>
                  )}
                  <button
                    onClick={() => deleteModule(m.id)}
                    className="shrink-0 w-5 h-5 flex items-center justify-center rounded text-text-muted hover:text-destructive hover:bg-destructive-subtle opacity-0 group-hover:opacity-100 transition-all"
                    aria-label={`Delete ${m.title}`}
                  >
                    <svg
                      className="w-3.5 h-3.5"
                      fill="none"
                      viewBox="0 0 14 14"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path d="M2 2l10 10M12 2L2 12" strokeLinecap="round" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    )}

    {/* Manual add row */}
    <div className="bg-card border border-border rounded-xl px-4 py-3 flex items-center gap-2 flex-wrap">
      <input
        type="text"
        value={newTitle}
        onChange={(e) => setNewTitle(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") addModule()
        }}
        placeholder="Module title…"
        className="flex-1 min-w-[160px] text-sm bg-transparent outline-none placeholder:text-text-muted"
      />
      <select
        value={newLabel}
        onChange={(e) => setNewLabel(e.target.value as Label)}
        className="text-xs border border-border rounded-md px-2 py-1.5 bg-surface-subtle text-text-secondary outline-none cursor-pointer"
      >
        {LABELS.map((l) => (
          <option key={l} value={l}>
            {l}
          </option>
        ))}
      </select>
      <button
        onClick={addModule}
        disabled={!newTitle.trim()}
        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium bg-primary text-primary-foreground hover:bg-accent-hover transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <svg
          className="w-3 h-3"
          fill="none"
          viewBox="0 0 12 12"
          stroke="currentColor"
          strokeWidth={2.5}
        >
          <path d="M6 1v10M1 6h10" strokeLinecap="round" />
        </svg>
        Add
      </button>
    </div>
  </>
)}
```

> **Note on the empty-state condition:** The original code showed an empty-state message when no modules exist. The new version only shows it when `extractionStatus === "idle"` (i.e., no extraction has been triggered yet — modules have loaded from DB and there are none). During extraction, the progress bar provides all the feedback needed; the empty-state would be visually confusing.

- [ ] **Step 6: Type-check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors

- [ ] **Step 7: Run the app and verify the streaming UI**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000/projects/21/modules` in a browser. If modules exist in the DB, delete them via the backend (`PATCH /api/v1/projects/21/modules` with `{"modules": []}`) to force re-extraction, then refresh.

Expected:
1. Progress bar appears immediately with amber "Analyzing proposal…" at ~5% width
2. Module rows appear one-by-one with a subtle slide-in animation; bar grows with each one; status chip reads "Generating modules… (N found)" in blue
3. On completion, bar fills to 100% green, chip reads "N modules extracted ✓" with a checkmark

- [ ] **Step 8: Commit**

```bash
git add frontend/app/\(app\)/projects/\[id\]/modules/page.tsx frontend/app/globals.css
git commit -m "feat(ui): streaming progress bar and per-module animation on modules page"
```
