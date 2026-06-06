# Epic 6 (T2): API Contract Validation — Spec

**Goal:** Regenerate `api.types.ts` from the live Epic 5 backend, add helpers for the ~10 new endpoints, and verify zero TypeScript errors.

**Issue:** #42

**Branch:** `feat/epic6-task2-contract-validation`

---

## What changes

```
frontend/
└── lib/
    ├── api.types.ts    ← regenerated (delete old, run gen:api)
    └── api.ts          ← add new helpers; fix any type errors in existing ones
```

No other files change. This is purely a contract alignment task.

---

## How to regenerate

Backend must be running:
```bash
cd backend && source .venv/bin/activate
uvicorn app.main:app --port 8000
```

Then in a second terminal:
```bash
cd frontend
npm run gen:api
```

This overwrites `lib/api.types.ts` with the current OpenAPI spec. Commit the new file — teammates must not need the backend running for normal dev.

---

## New helpers for `frontend/lib/api.ts`

Add these exports after the existing ones, grouped by concern:

```typescript
// ── Project CRUD (new in Epic 5) ─────────────────────────────────────────────

export const getProjects = () =>
  apiClient.GET("/api/v1/projects", {})

export const getProject = (projectId: string) =>
  apiClient.GET("/api/v1/projects/{project_id}", {
    params: { path: { project_id: projectId } },
  })

// ── Redaction / PII review (new in Epic 5) ───────────────────────────────────

export const getRedactionDecisions = (projectId: string) =>
  apiClient.GET("/api/v1/projects/{project_id}/redaction-decisions", {
    params: { path: { project_id: projectId } },
  })

export const patchRedactionDecisions = (
  projectId: string,
  decisions: Record<string, boolean>,
) =>
  apiClient.PATCH("/api/v1/projects/{project_id}/redaction-decisions", {
    params: { path: { project_id: projectId } },
    body: decisions,
  })

// ── Phase triggers (new in Epic 5) ───────────────────────────────────────────

export const startPhase = (projectId: string, phase: number) =>
  apiClient.POST("/api/v1/projects/{project_id}/phases/{phase_number}/start", {
    params: { path: { project_id: projectId, phase_number: phase } },
  })

// ── Phase result GETs (new in Epic 5) ────────────────────────────────────────

export const getStack = (projectId: string) =>
  apiClient.GET("/api/v1/projects/{project_id}/stack", {
    params: { path: { project_id: projectId } },
  })

export const getTeam = (projectId: string) =>
  apiClient.GET("/api/v1/projects/{project_id}/team", {
    params: { path: { project_id: projectId } },
  })

export const getEstimate = (projectId: string) =>
  apiClient.GET("/api/v1/projects/{project_id}/estimate", {
    params: { path: { project_id: projectId } },
  })

export const getEpics = (projectId: string) =>
  apiClient.GET("/api/v1/projects/{project_id}/epics", {
    params: { path: { project_id: projectId } },
  })

// ── DOCX export (binary download — use URL, not apiClient) ───────────────────

export const getProposalExportUrl = (projectId: string): string =>
  `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/projects/${projectId}/export/proposal`
```

The DOCX export returns `Content-Disposition: attachment` (binary). `openapi-fetch` cannot handle binary downloads — the helper returns the URL for use in `<a href={url} download>` or `window.open(url)`.

---

## Fix existing helpers if types change

After regenerating, `tsc --noEmit` will surface any existing helper in `lib/api.ts` whose request/response types no longer match. Fix each error by updating the helper signature to match the new generated type. Do not suppress errors with `// @ts-ignore`.

---

## Verification

```bash
cd frontend

# 1. Regenerate (backend must be running on :8000)
npm run gen:api

# 2. Zero TypeScript errors
npx tsc --noEmit

# 3. Lint clean
npm run lint
```

Both `tsc` and `lint` must exit 0. That is the AC.

---

## Definition of done

- `lib/api.types.ts` regenerated from live Epic 5 backend and committed
- `lib/api.ts` has one typed helper per endpoint (existing + ~10 new)
- `npx tsc --noEmit` exits 0 — zero type errors
- `npm run lint` exits 0
- No `@ts-ignore` or `as any` suppressions introduced
