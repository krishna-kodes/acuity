# Backend Gap Analysis — Discovered During Frontend Build

> Generated during Epic 3 UI scaffolding (June 2026).  
> Items marked **NEW** are not in the original CLAUDE.md API table.  
> Items marked **CLARIFICATION** need a contract decision before Epic 4 can wire them up.

---

## 1. API endpoints referenced by the frontend

All routes below are called (or will be called) by the frontend. Cross-checked against CLAUDE.md §7.

| Method | Endpoint | Frontend source | Status |
|--------|----------|-----------------|--------|
| POST | `/api/v1/projects` | `projects/new/page.tsx` | In spec |
| POST | `/api/v1/projects/{id}/documents` | `projects/new/page.tsx` | In spec |
| GET | `/api/v1/projects` | `(app)/page.tsx` (dashboard list) | **NEW** — not in CLAUDE.md |
| GET | `/api/v1/projects/{id}/tbds` | `redaction/page.tsx`, `chat/page.tsx` | In spec |
| PATCH | `/api/v1/projects/{id}/redaction-decisions` | `redaction/page.tsx` | **NEW** — CLAUDE.md has no PATCH route for redaction |
| POST | `/api/v1/projects/{id}/phases/2/start` | `redaction/page.tsx` | **NEW** — phase-start routes not in spec |
| POST | `/api/v1/projects/{id}/chat` | `chat/page.tsx` | **NEW** — no chat message route in spec |
| POST | `/api/v1/projects/{id}/clarifications` | `chat/page.tsx` | In spec |
| POST | `/api/v1/projects/{id}/proposal` | `chat/page.tsx` | In spec |
| GET | `/api/v1/projects/{id}/stack` | `techstack/page.tsx` | **NEW** — spec only has POST |
| POST | `/api/v1/projects/{id}/stack` | `techstack/page.tsx` | In spec (as "run tech stack suggestion") |
| POST | `/api/v1/projects/{id}/phases/4/start` | `techstack/page.tsx` | **NEW** — phase-start routes not in spec |
| GET | `/api/v1/projects/{id}/team` | `team/page.tsx` | **NEW** — spec has no GET team route |
| POST | `/api/v1/projects/{id}/phases/5/start` | `team/page.tsx` | **NEW** — phase-start routes not in spec |
| GET | `/api/v1/projects/{id}/estimate` | `estimation/page.tsx` | **NEW** — spec only has POST |
| POST | `/api/v1/projects/{id}/phases/6/start` | `estimation/page.tsx` | **NEW** — phase-start routes not in spec |
| GET | `/api/v1/projects/{id}/epics` | `epics/page.tsx` | **NEW** — spec has no GET epics route |
| POST | `/api/v1/projects/{id}/sync` | `epics/page.tsx` | In spec |
| GET | `/api/v1/projects/{id}/metrics` | `metrics/page.tsx` | In spec |
| GET | `/api/v1/projects/{id}/export/proposal` | (no UI yet — gap D7) | In spec |

---

## 2. Response shape requirements

### `GET /api/v1/projects` (dashboard)
```typescript
// Array of project summaries
[{
  id: string;
  name: string;
  domain: string;
  phase: string;          // current phase slug: "redaction" | "chat" | ...
  updated: string;        // ISO 8601 or human-readable date string
  syncStatus?: "pending" | "synced" | "skipped" | "failed";
}]
```

### `GET /api/v1/projects/{id}/tbds`
```typescript
[{
  id: string;
  title: string;
  desc: string;
  level: "Explicit TBD" | "Vague statement" | "Missing section" | "Contradiction";
  status: "open" | "answered" | "tbd" | "oos";
}]
```

### `GET /api/v1/projects/{id}/stack`
```typescript
[{
  name: string;
  category: string;
  reason: string;
  approved: boolean;
}]
```

### `GET /api/v1/projects/{id}/team`
```typescript
[{
  name: string;
  role: string;
  skills: string[];
  availability: number;   // 0–100 percent
  matchScore: number;     // 0.0–1.0
}]
```

### `GET /api/v1/projects/{id}/estimate`
```typescript
[{
  area: string;
  low: number;
  mid: number;
  high: number;
  confidence: "high" | "medium" | "low";
  notes: string;
}]
```

### `GET /api/v1/projects/{id}/epics`
```typescript
// IMPORTANT: EpicItem needs description for GitHub body — see gap D3
[{
  id: string;
  title: string;
  description: string;    // GitHub Milestone description
  points: number;
  syncStatus: "pending" | "synced" | "skipped" | "failed";
  syncError?: string;     // per-epic error message — see gap D4
  selected: boolean;
  tasks: [{
    id: string;
    title: string;
    description: string;  // GitHub Issue body
    points: number;
    assignee?: string;
    syncStatus: "pending" | "synced" | "skipped" | "failed";
    syncError?: string;
  }]
}]
```

### `GET /api/v1/projects/{id}/metrics`
```typescript
{
  tokenUsage: {
    totalTokens: number;
    totalCostUsd: number;
    inputTokens: number;
    outputTokens: number;
    byPhase: { phase: string; tokens: number }[];
    trend: { day: string; input: number; output: number; cost: number }[];
  };
  quality: {
    graders: { grader: string; score: number }[];
  };
  retrieval: {
    byQuery: { phase: string; recall: number; relevancy: number }[];
  };
  errors: {
    byPhase: { phase: string; errors: number; retries: number }[];
    recent: { phase: string; code: string; msg: string; ts: string }[];
  };
  latency: {
    byNode: { node: string; p50: number; p95: number }[];
  };
}
```

### `GET /api/v1/projects/{id}/tbds` + `GET /api/v1/projects/{id}/pii_detections`
(used by `redaction/page.tsx` — currently one combined comment but two distinct endpoints)
```typescript
// GET /api/v1/projects/{id}/pii_detections
[{
  id: number;
  original: string;
  type: "Person" | "Email" | "Phone" | "Organization" | "Credit Card" | "Location" | "Date" | "URL" | "Currency";
  method: "NER" | "Regex";
  placeholder: string;
  confidence: number;
  decision?: "confirmed" | "override";
}]
```

---

## 3. Phase-start routes

The frontend calls `POST /api/v1/projects/{id}/phases/{n}/start` when the PM clicks "Proceed" on each page. These are not in the CLAUDE.md route table.

**Clarification needed:** Should phase advancement be a dedicated `/phases/{n}/start` route, or should it be a side-effect of the data-submission route (e.g. `POST /api/v1/projects/{id}/clarifications` implicitly starts phase 2)?

Recommendation: explicit phase-start routes keep the backend transitions auditable (maps to `phase_status` in `ProjectState`) and matches ADR-008 (PM-initiated transitions).

Required routes:
```
POST /api/v1/projects/{id}/phases/2/start   # after redaction review
POST /api/v1/projects/{id}/phases/3/start   # after proposal generation (chat page)
POST /api/v1/projects/{id}/phases/4/start   # after tech stack review
POST /api/v1/projects/{id}/phases/5/start   # after team review
POST /api/v1/projects/{id}/phases/6/start   # after estimation review
```

Response: `{ phase: number; status: "in_progress" }` or `{ error: string }` if Phase N−1 not complete.

---

## 4. Chat endpoint

`POST /api/v1/projects/{id}/chat` is not in CLAUDE.md. Required for Phase 2 RAG conversation loop.

```typescript
// Request
{ message: string }

// Response (streaming preferred, but polling acceptable for MVP)
{
  id: string;
  role: "ai";
  text: string;
  timestamp: string;
}
```

**Clarification needed:** streaming SSE vs. single JSON response? Frontend currently expects a single response (sets `isLoading` state). SSE would require refactoring the chat loop.

---

## 5. Redaction-decisions endpoint

`PATCH /api/v1/projects/{id}/redaction-decisions` is not in CLAUDE.md.

```typescript
// Request
{
  decisions: [{
    id: number;             // pii_detection id
    decision: "confirmed" | "override";
  }]
}

// Response
{ updated: number }
```

---

## 6. Data shape gaps (from design validation D3, D4)

- **`EpicItem.description`** — missing from current mock data and `EpicItem` TypeScript interface. Backend must return `description` (becomes GitHub Milestone description) and each task must return `description` (becomes GitHub Issue body).
- **`EpicItem.syncError`** — needed for inline per-epic error display (design gap D4). Backend should return per-epic `syncError: string | null` after a partial sync failure.

---

## 7. Export endpoint

`GET /api/v1/projects/{id}/export/proposal` — in spec, not yet wired in UI (design gap D7).

**Required:** backend must return `Content-Disposition: attachment; filename="proposal-{name}.docx"` with `application/vnd.openxmlformats-officedocument.wordprocessingml.document` content type. Frontend download via `<a href="...">` or `window.location.assign(url)`.

---

## 8. Error response contract

All endpoints must return consistent error shapes so the frontend `ErrorBanner` can display them:
```typescript
// 4xx / 5xx responses
{ detail: string }   // FastAPI default — matches frontend usage
```

---

## 9. Phase-gating enforcement

ADR-008 says Phase N cannot start until Phase N−1 `phase_status = "complete"`. The frontend enforces this visually (locked state in stepper, Proceed button disabled). The backend must also enforce it — return `HTTP 409` with `{ detail: "Phase N-1 not complete" }` if the client tries to skip ahead.

---

## Summary of NEW endpoints needed

| Endpoint | Priority |
|----------|----------|
| `GET /api/v1/projects` | P0 — dashboard won't load without it |
| `POST /api/v1/projects/{id}/chat` | P0 — Phase 2 RAG loop |
| `PATCH /api/v1/projects/{id}/redaction-decisions` | P0 — Phase 1 completion |
| `POST /api/v1/projects/{id}/phases/{n}/start` (×5) | P0 — phase transitions |
| `GET /api/v1/projects/{id}/stack` | P1 — tech stack display |
| `GET /api/v1/projects/{id}/team` | P1 — team display |
| `GET /api/v1/projects/{id}/estimate` | P1 — estimation display |
| `GET /api/v1/projects/{id}/epics` | P1 — epics display |
