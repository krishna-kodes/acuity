# Modules Streaming — Design Spec

**Date:** 2026-06-09  
**Status:** Approved  
**Scope:** Add SSE streaming + progress bar to the Work Modules extraction page (`/projects/[id]/modules`)

---

## Problem

Module extraction (`POST /api/v1/projects/{id}/modules`) is a synchronous LLM call. The user sees a spinner with no progress feedback until the full JSON response arrives (~3–8 seconds). No indication of how many modules have been found or whether the LLM is making progress.

---

## Approach

Regex-based incremental JSON extraction over an SSE stream. The LLM response is a flat JSON array of module objects (`{id, title, label, description}`). As tokens stream in, completed `{...}` objects are extracted via regex and emitted as individual SSE events. The frontend renders each module as it arrives. A `done` event delivers the authoritative final list.

---

## Backend

### New endpoint

```
POST /api/v1/projects/{project_id}/modules/stream
```

Returns `text/event-stream`. Headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`.

### SSE event sequence

| Event | Payload | When |
|---|---|---|
| `status` | `{"type": "status", "status": "started"}` | Immediately on request |
| `module` | `{"type": "module", "module": {id, title, label, description}}` | Each time a complete module object is parsed from the token stream |
| `done` | `{"type": "done", "modules": [...], "count": n}` | After all tokens consumed and `modules_json` saved to DB |

### Implementation notes

- `get_llm().astream(prompt)` replaces `ainvoke` — same prompt, same model
- Buffer accumulation: tokens appended to `buffer: str`
- Extraction: `re.finditer(r'\{[^{}]+\}', buffer)` — valid for flat module objects
- After each scan pass, buffer is trimmed to `buffer[last_match.end():]` to prevent O(n²) re-scanning
- `seen_ids: set[str]` prevents duplicate emit at token boundaries
- Existing `POST /modules` (non-streaming) is left unchanged — no callers removed

### DB write

`project.modules_json` written from the `modules` list accumulated during streaming (each entry added when its `{...}` object was parsed by regex). Module objects are flat so regex extraction is reliable for this schema. The `done` event delivers this same list.

---

## Frontend

### New API function (`frontend/lib/api.ts`)

```ts
extractModulesStream(
  projectId: string,
  onStatus: (status: string) => void,
  onModule: (module: Module) => void,
  onDone: (result: { modules: Module[]; count: number }) => void,
): Promise<void>
```

Pattern mirrors `generateProposalStream`: `fetch` → `ReadableStream` → `TextDecoder` → SSE line parser.

### State additions (`modules/page.tsx`)

```ts
type ExtractionStatus = "idle" | "started" | "generating" | "done"
const [extractionStatus, setExtractionStatus] = useState<ExtractionStatus>("idle")
const [extractionTotal, setExtractionTotal] = useState(0)
```

`runExtraction()` updated to call `extractModulesStream` instead of `extractModules`. Sets `extractionStatus` on each event. On `onDone`, sets modules to authoritative list and status to `"done"`.

### Progress bar

Rendered between the page header and the module list. Visible when `extractionStatus !== "idle"`.

**Width formula:** `(modules.length / Math.max(modules.length, estimatedTotal)) * 100%`
- `estimatedTotal` starts at `10` (reasonable prior for most proposals)
- Snaps to actual `done.count` on completion

**Status chip colors:**
- `started` → amber (`text-amber-600`)
- `generating` → blue, pulsing (`text-blue-600 animate-pulse`)
- `done` → green (`text-green-600`)

**Label copy:**
- `started` → "Analyzing proposal…"
- `generating` → "Generating modules… (n found)"
- `done` → "n modules extracted ✓"

### Module row animation

Each module row added during streaming gets `opacity-0` → `opacity-100` via `transition-opacity duration-300`. Applied via a CSS class toggled after mount.

### Status transition

```
idle → started (on status event)
     → generating (on first module event)
     → done (on done event)
```

Status resets to `idle` when user navigates away or starts a re-extraction.

---

## Files changed

| File | Change |
|---|---|
| `backend/app/routers/projects.py` | Add `extract_modules_stream` endpoint |
| `frontend/lib/api.ts` | Add `extractModulesStream` function |
| `frontend/app/(app)/projects/[id]/modules/page.tsx` | Add state, progress bar component, update `runExtraction` |

---

## Out of scope

- Token-level text display (raw JSON preview)
- WebSocket transport (SSE sufficient for unidirectional stream)
- Re-extraction streaming when modules already exist (same code path — `runExtraction` always uses stream endpoint)
