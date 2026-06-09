# Estimation Phase Streaming & Progress Bar

**Date:** 2026-06-09  
**Status:** Approved

## Context

The effort estimation phase (Phase 5) currently uses a blocking `POST /estimate` endpoint backed by a full LangGraph ReAct agent (`_phase_5_estimate_node`). The frontend fires this on mount and renders nothing until the full response arrives. The tech stack page already implements SSE streaming with a progress bar — this design mirrors that exact pattern for estimation.

The streaming path **bypasses the ReAct loop** and calls the underlying tools directly (same technique used by `stack/stream` vs `_phase_3_stack_node`). Estimation is deterministic (one `get_historical_projects` DB read + one structured LLM call), so the ReAct retry loop provides no meaningful value for the streaming path.

## Architecture

### Backend — 1 new route

**`POST /api/v1/projects/{project_id}/estimate/stream`**

SSE endpoint. Event sequence:

| Event | Payload |
|-------|---------|
| `status` | `{"type": "status", "message": "Fetching historical projects..."}` |
| `status` | `{"type": "status", "message": "Analyzing requirements and computing estimates..."}` |
| `epic` ×N | `{"type": "epic", "title": "...", "estimated_points": N}` |
| `summary` | `{"type": "summary", "total_points": N, "total_weeks": N, "confidence": 0.X, "reasoning": "..."}` |
| `done` | `{"type": "done", "epics": [...], "total_points": N, "total_weeks": N}` |

**If cached** (`project.effort_estimates` populated and no `?force=true`): replay all events immediately from stored data, no LLM call.

**If not cached**: new async generator `estimate_effort_stream(project_id, db)` in `backend/app/services/workflow.py`:

1. Call `get_historical_projects()` DB helper directly — emit first `status` event
2. Build same prompt as `_phase_5_estimate_node`
3. Emit second `status` event
4. Call `llm.astream(messages)` (not `with_structured_output`) — stream tokens into a buffer
5. Use buffer detection to emit `epic` events as each `breakdown` entry closes:
   - Detect `"breakdown": {` opening
   - Regex `r'"([^"]+)":\s*(\d+)'` within breakdown block to emit per-entry as they parse
6. Extract `total_weeks`, `total_points`, `confidence`, `reasoning` from full buffer — emit `summary`
7. Emit `done` with full normalized result
8. Full-buffer fallback parse at end (same pattern as `stack/stream`)
9. Save to `project.effort_estimates` + advance phase in `finally` block

**Phase gate:** Require `project.phase in _POST_TEAM_PHASES` (team suggestion complete) before allowing stream.

Files to modify:
- `backend/app/routers/projects.py` — add 1 route after existing `estimate_effort` endpoint (~line 1683)
- `backend/app/services/workflow.py` — add `estimate_effort_stream()` async generator

No changes to `_phase_5_estimate_node` or the existing `/estimate` endpoint.

### Frontend — `lib/api.ts`

Add 1 function alongside existing `estimateEffort`:

```typescript
export async function estimateEffortStream(
  projectId: string,
  callbacks: {
    onStatus: (message: string) => void
    onEpic: (epic: { title: string; estimated_points: number }) => void
    onSummary: (data: { total_points: number; total_weeks: number; confidence: number; reasoning: string }) => void
    onDone: (data: EffortData) => void
  },
  force?: boolean,
): Promise<void>
```

Uses the same `ReadableStream` + `TextDecoder` chunked parsing pattern as `suggestStackStream` (lines 569–607 in `api.ts`). Fetches `POST /api/v1/projects/{id}/estimate/stream?force={force}`.

### Frontend — `estimation/page.tsx`

Replace `estimateEffort()` call with `estimateEffortStream()`. New state:

```typescript
type EstimateStatus = "idle" | "fetching" | "computing" | "done";
const [estimateStatus, setEstimateStatus] = useState<EstimateStatus>("idle");
const [completedCount, setCompletedCount] = useState(0);   // epics parsed so far
const [streamedEpics, setStreamedEpics] = useState<EpicEstimate[]>([]);
const estimateFiredRef = useRef(false);  // StrictMode double-fire guard
```

**Mount logic** (mirrors techstack page):
```
useEffect → estimateFiredRef guard → estimateEffortStream()
```

**Callback wiring:**
- `onStatus("Fetching...")` → `setEstimateStatus("fetching")`
- `onStatus("Analyzing...")` → `setEstimateStatus("computing")`
- `onEpic(epic)` → append to `streamedEpics` (title + estimated_points only), `setCompletedCount(n+1)`
- `onSummary(data)` → update stat cards (total_points, total_weeks, confidence)
- `onDone(data)` → `setEstimateStatus("done")`, replace streamedEpics with canonical list

**Epics table** renders `streamedEpics` progressively — rows append as `onEpic` fires. No flicker.

## Progress Bar UI

Rendered when `estimateStatus !== "idle"`. Mirrors techstack page structure:

```
fetching   → 10% width  · amber  · "Fetching historical projects..."
computing  → min(10 + completedCount*8, 90)%  · blue+pulse  · "Estimating epics… ({completedCount} found)"
done       → 100%       · green  · "{total_points} story points across {n} epics ✓"
```

`completedCount * 8` gives ~90% at ~10 epics, caps before `done` snaps it to 100%. No total needed upfront.

Add "Re-run Estimation" button — calls `estimateEffortStream(..., force=true)`, resets all state. Mirrors techstack "Regenerate" button.

## Documentation Updates

After implementation, update `CLAUDE.md`:
- Add `POST /projects/{id}/estimate/stream` to the API Surface table
- Update implementation status note to reflect streaming estimation

## Verification

1. Navigate to `/projects/{id}/estimation` on a project with completed team suggestion → progress bar appears, status messages transition, epic rows append in real time, bar reaches 100%
2. Refresh page → cached data replays immediately without LLM call, bar reaches done
3. Click "Re-run Estimation" → streaming restarts, old epics replaced
4. Check DevTools Network tab: SSE events arrive in order (status → status → epic×N → summary → done)
5. Confirm `project.effort_estimates` persisted in DB after stream completes
6. Confirm `project.phase` advances to `estimation` after stream
7. Existing `POST /estimate` endpoint (non-streaming) still works — no regression
