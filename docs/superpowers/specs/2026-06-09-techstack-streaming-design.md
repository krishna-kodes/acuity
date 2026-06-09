# Tech Stack Streaming & Progress Bar

**Date:** 2026-06-09  
**Status:** Approved

## Context

The tech stack phase (Phase 3) currently uses a blocking `POST /stack` endpoint backed by a single synchronous `with_structured_output().invoke()` LLM call. The frontend renders a loading skeleton until the full response arrives. The modules page already implements category-level SSE streaming with a progress bar — this design mirrors that pattern for tech stack.

## Architecture

### Backend — 2 new routes

**1. `GET /api/v1/projects/{project_id}/stack`**

Returns cached `TechStackResponse` if `project.tech_stack` exists and phase is past stack, otherwise HTTP 204 (no content). Used by the frontend mount check to avoid re-running the LLM when data already exists.

**2. `POST /api/v1/projects/{project_id}/stack/stream`**

SSE endpoint. Event sequence:

| Event | Payload |
|-------|---------|
| `status` | `{"type": "status", "message": "Analyzing requirements..."}` |
| `category` ×4 | `{"type": "category", "key": "frontend"\|"backend"\|"database"\|"infra", "items": [...]}` |
| `rationale` | `{"type": "rationale", "text": "..."}` |
| `done` | `{"type": "done", "stack": {frontend, backend, database, infra, rationale}}` |

**If cached** (project.phase in `_POST_STACK_PHASES`): replay all 6 events immediately from `project.tech_stack`, no LLM call.

**If not cached**: call `llm.astream()` (not `with_structured_output`) with the same prompt as `_phase_3_stack_node`. Use regex buffer detection to emit category events as each array closes:
- Categories: `r'"(frontend|backend|database|infra)":\s*(\[[^\]]*\])'`
- Rationale: `r'"rationale":\s*"((?:[^"\\]|\\.)*)"'`

Include full-buffer fallback parse at end (same pattern as modules stream). Save to `project.tech_stack` + advance phase in `finally` block.

Files to modify:
- `backend/app/routers/projects.py` — add 2 routes after the existing `suggest_stack` endpoint
- No changes to `workflow.py` (stream endpoint duplicates only the LLM call + prompt, not the full LangGraph node)

### Frontend — `lib/api.ts`

Add 2 functions:

```typescript
export async function getStack(
  projectId: string,
): Promise<{ data: TechStackData | null; error: string | null }>

export async function suggestStackStream(
  projectId: string,
  onStatus: (message: string) => void,
  onCategory: (key: string, items: string[]) => void,
  onRationale: (text: string) => void,
  onDone: (stack: TechStackData) => void,
): Promise<void>
```

`getStack` calls `GET /api/v1/projects/{id}/stack`, returns `null` on 204.
`suggestStackStream` uses the same `ReadableStream` parsing pattern as `extractModulesStream`.

### Frontend — `techstack/page.tsx`

Replace `useQuery` with manual streaming state:

```typescript
type StackStatus = "idle" | "started" | "generating" | "done";
const [stackStatus, setStackStatus] = useState<StackStatus>("idle");
const [completedCount, setCompletedCount] = useState(0);   // 0–5 (4 categories + rationale)
const [currentCategory, setCurrentCategory] = useState("");
const [stack, setStack] = useState<Partial<TechStackData>>({});
const stackFiredRef = useRef(false);  // StrictMode double-fire guard
```

**Mount logic** (mirrors modules page):
```
useEffect → getStack(id)
  ├─ data present → setStack(data), setStackStatus("done")   // skip LLM
  └─ null/empty   → stackFiredRef guard → runStackGeneration()
```

**`runStackGeneration()`** calls `suggestStackStream` with callbacks:
- `onStatus` → `setStackStatus("started")`
- `onCategory` → append items to `stack`, `setCurrentCategory(key)`, `setCompletedCount(n+1)`, `setStackStatus("generating")`
- `onRationale` → update `stack.rationale`, `setCompletedCount(n+1)`
- `onDone` → `setStack(full)`, `setStackStatus("done")`
- Error → `toast.error(...)`, reset to `"idle"`

## Progress Bar UI

Rendered when `stackStatus !== "idle"`. Identical structure to modules page progress bar:

```
started    → 5% width   · amber   · "Analyzing requirements..."
generating → (completedCount/5)*95% · blue+pulse · "Generating {currentCategory}… ({completedCount}/5)"
done       → 100%       · green   · "{totalCount} technologies selected ✓"
```

`totalCount` = sum of all items across frontend + backend + database + infra arrays.

Add "Regenerate" button (mirrors modules "Re-extract" button) — calls `runStackGeneration()`, resets state.

## Documentation Updates

After implementation, update `CLAUDE.md`:
- Add `GET /projects/{id}/stack` and `POST /projects/{id}/stack/stream` to the API Surface table
- Update implementation status note if needed

## Verification

1. Navigate to `/projects/{id}/techstack` on a project with no cached stack → progress bar appears, 5 category/rationale events stream in, bar reaches 100%
2. Refresh page → cached data loads immediately, progress bar reaches done without LLM call
3. Click "Regenerate" → streaming restarts from scratch
4. Check DevTools Network tab for SSE events in correct order
5. Confirm `project.tech_stack` persisted in DB after stream completes
6. Confirm `project.phase` advances to `techstack` if it was `chat`
