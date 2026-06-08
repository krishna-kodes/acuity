# Backend Gap Analysis — Discovered During Frontend Build

> Originally generated during Epic 3 UI scaffolding (June 2026).  
> **Status as of June 2026 (post-Epic 5):** All P0 blockers resolved. All endpoints live.  
> New endpoints added beyond original spec are documented below.

---

## Implementation Status (June 2026 — current)

All original P0 blockers from Epic 3 are resolved:

| Gap | Status |
|-----|--------|
| `GET /api/v1/projects` dashboard list | ✅ Implemented |
| `POST /api/v1/projects/{id}/chat` SSE RAG loop | ✅ Implemented (SSE streaming) |
| `PATCH /api/v1/projects/{id}/redaction-decisions` | ✅ Implemented |
| Phase-start routes | ✅ Resolved via approve endpoints per phase |

**New endpoints added beyond original spec (all live):**

| Endpoint | Added | Purpose |
|----------|-------|---------|
| `POST /projects/{id}/proposal/retry` | June 2026 | Regenerate proposal with PM feedback |
| `POST /projects/{id}/proposal/approve` | June 2026 | Approve proposal → advance to Modules phase |
| `POST /projects/{id}/pii-llm-filter` | June 2026 | LLM quality gate for NER false positives |
| `GET /projects/{id}/document-status` | June 2026 | Poll ingestion completion before phase advance |
| `POST /projects/{id}/modules` | June 2026 | LLM-extract work modules from proposal |
| `GET /projects/{id}/modules` | June 2026 | Retrieve stored modules |
| `PATCH /projects/{id}/modules` | June 2026 | Save PM edits to modules |
| `POST /projects/{id}/modules/approve` | June 2026 | Approve modules → advance to Tech Stack |
| `GET /projects/{id}/documents-list` | June 2026 | Documents tab: list uploaded + generated files |
| `DELETE /projects/{id}/documents/{doc_id}` | June 2026 | Delete uploaded document |
| `DELETE /projects/{id}/proposals/{proposal_id}` | June 2026 | Delete generated proposal |
| `GET /projects/{id}/sync-config` | June 2026 | Retrieve sync provider config |
| `PATCH /projects/{id}/sync-config` | June 2026 | Update sync provider (github / jira) |
| `GET /admin/employees` | June 2026 | Admin: list employees with skills |
| `GET /admin/skills` | June 2026 | Admin: list all skills |

---

## Phase gating — current implementation

Phase advancement uses dedicated `approve` endpoints rather than `POST /phases/{n}/start`:

| From phase | Advance via |
|-----------|-------------|
| chat → modules | `POST /projects/{id}/proposal/approve` |
| modules → techstack | `POST /projects/{id}/modules/approve` |
| techstack → team | Frontend navigates directly (stack runs synchronously) |
| team → estimation | Frontend navigates after `PUT /projects/{id}/team` |
| estimation → epics | Frontend navigates after estimation renders; backend 409s if phase_5 not complete |

Backend enforces ordering via `_POST_*_PHASES` sets — returns HTTP 409 if prior phase incomplete.

---

## Historical gap detail (resolved — kept for reference)

All items below were originally open gaps. They are now implemented.

### Endpoints (all ✅ resolved)

| Method | Endpoint | Resolution |
|--------|----------|------------|
| GET | `/api/v1/projects` | Implemented — returns project list with phase + sync status |
| PATCH | `/api/v1/projects/{id}/redaction-decisions` | Implemented — triggers `complete_ingestion()` as background task |
| POST | `/api/v1/projects/{id}/chat` | Implemented — SSE streaming, LangGraph RAG loop |
| POST | `/api/v1/projects/{id}/phases/{n}/start` | Resolved — phase advancement via approve endpoints per phase |
| GET | `/api/v1/projects/{id}/stack` (GET variant) | Not implemented; `POST /stack` runs and returns data synchronously |
| GET | `/api/v1/projects/{id}/estimate` (GET variant) | Not implemented; `POST /estimate` runs and returns data |
| GET | `/api/v1/projects/{id}/epics` | Implemented — returns epics with tasks, sync status, tracker URLs |
| GET | `/api/v1/projects/{id}/export/proposal` | Implemented — streams DOCX with `Content-Disposition: attachment` |

### Chat endpoint — resolved as SSE

`POST /api/v1/projects/{id}/chat` resolved as Server-Sent Events. Frontend uses `fetch` + `ReadableStream` to consume the stream. Format:

```
data: {"type": "token", "content": "..."}
data: {"type": "done", "proceed": false}
```

### Redaction decisions — resolved shape

```typescript
// PATCH request
{ decisions: [{ detection_id: number; confirmed: boolean }] }
// Response
{ updated: number }
```

### Modules endpoint — new (added June 2026)

```typescript
// GET/POST/PATCH /api/v1/projects/{id}/modules
// Response
{
  modules: [{
    id: string;         // uuid4
    title: string;
    label: string;      // "frontend" | "backend" | "devops" | "QA" | "PM" | "design" | "data" | "infra"
    description: string;
  }]
}
```

---

## 8. Error response contract

All endpoints must return consistent error shapes so the frontend `ErrorBanner` can display them:
```typescript
// 4xx / 5xx responses
{ detail: string }   // FastAPI default — matches frontend usage
```

---

## 9. Phase-gating enforcement

Phase gating is enforced via `_POST_*_PHASES` sets in `backend/app/routers/projects.py`. Returns HTTP 409 if prior phase not complete.
