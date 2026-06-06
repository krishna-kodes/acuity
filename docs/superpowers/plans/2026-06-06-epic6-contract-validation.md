# Epic 6 (T2): API Contract Validation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Regenerate `frontend/lib/api.types.ts` from the live Epic 5 backend, add typed helpers for all new endpoints, and achieve zero TypeScript errors.

**Architecture:** Run `npm run gen:api` against the live backend to get current types. Add new helper functions to `lib/api.ts` for the ~10 endpoints added in Epic 5. Let `tsc --noEmit` drive all fixes — any type error is a contract mismatch to resolve.

**Tech Stack:** TypeScript 5, openapi-fetch, openapi-typescript, Next.js 16.2

**Spec:** `docs/superpowers/specs/2026-06-06-epic6-contract-validation-design.md`

---

## File map

```
frontend/
└── lib/
    ├── api.types.ts    ← regenerated (overwrite entirely)
    └── api.ts          ← add new helpers, fix any broken existing ones
```

---

## Task 1: Regenerate types + add new helpers (Issue #42)

**Branch:** `feat/epic6-task2-contract-validation`

**Files:**
- Regenerate: `frontend/lib/api.types.ts`
- Modify: `frontend/lib/api.ts`

---

- [ ] **Step 1: Branch from main**

```bash
cd /path/to/acuity
git checkout main && git pull origin main
git checkout -b feat/epic6-task2-contract-validation
```

---

- [ ] **Step 2: Confirm tsc currently has no errors (baseline)**

```bash
cd /path/to/acuity/frontend
npx tsc --noEmit 2>&1 | tail -5
```

Expected: exits 0. If there are pre-existing errors, note them — they are NOT introduced by this task and must not be fixed here.

---

- [ ] **Step 3: Start the backend**

```bash
# In a separate terminal
cd /path/to/acuity/backend
source .venv/bin/activate
uvicorn app.main:app --port 8000
```

Verify it's running:
```bash
curl -s http://localhost:8000/health
```
Expected: `{"status":"ok"}`

---

- [ ] **Step 4: Regenerate `api.types.ts`**

```bash
cd /path/to/acuity/frontend
npm run gen:api
```

Expected: `frontend/lib/api.types.ts` is overwritten with new types. The file will be larger than before — many new paths will appear (GET /projects, redaction endpoints, phase triggers, etc.).

---

- [ ] **Step 5: Run tsc to see what broke (TDD red)**

```bash
cd /path/to/acuity/frontend
npx tsc --noEmit 2>&1
```

Expected: type errors for existing helpers in `lib/api.ts` whose path strings no longer match, or whose request/response types changed. Note every error before fixing.

---

- [ ] **Step 6: Add new helpers to `frontend/lib/api.ts`**

Open `lib/api.ts`. After the existing exports, add a new section. **Use the exact path strings from the generated `api.types.ts`** — if a path in the generated file differs from what's shown here, use the generated file's version:

```typescript
// ── Project CRUD (Epic 5) ─────────────────────────────────────────────────────

export const getProjects = () =>
  apiClient.GET("/api/v1/projects", {})

export const getProject = (projectId: string) =>
  apiClient.GET("/api/v1/projects/{project_id}", {
    params: { path: { project_id: projectId } },
  })

// ── Redaction / PII review (Epic 5) ──────────────────────────────────────────

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

// ── Phase triggers (Epic 5) ───────────────────────────────────────────────────

export const startPhase = (projectId: string, phase: number) =>
  apiClient.POST("/api/v1/projects/{project_id}/phases/{phase_number}/start", {
    params: { path: { project_id: projectId, phase_number: phase } },
  })

// ── Phase result GETs (Epic 5) ────────────────────────────────────────────────

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

// ── DOCX export (binary — use URL directly) ───────────────────────────────────

export const getProposalExportUrl = (projectId: string): string =>
  `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/projects/${projectId}/export/proposal`
```

---

- [ ] **Step 7: Fix any type errors in existing helpers**

Run `tsc --noEmit` again and fix each remaining error:

```bash
cd /path/to/acuity/frontend
npx tsc --noEmit 2>&1
```

For each error, the fix pattern is: look at the generated `api.types.ts` for the relevant path, update the helper in `api.ts` to match the new request/response shape.

**Do NOT use `// @ts-ignore`, `as any`, or `as unknown` to suppress errors.** Every error must be resolved by correcting the helper signature.

Common fixes needed:
- Path parameter names changed (e.g., `project_id` vs `projectId`)
- Response fields renamed or retyped
- Request body shape changed

---

- [ ] **Step 8: Verify tsc passes (TDD green)**

```bash
cd /path/to/acuity/frontend
npx tsc --noEmit
```

Expected: **exits 0, zero errors.**

If errors remain, go back to Step 7 and fix them.

---

- [ ] **Step 9: Run lint**

```bash
cd /path/to/acuity/frontend
npm run lint
```

Expected: exits 0. Fix any lint errors (unused imports, etc.) before committing.

---

- [ ] **Step 10: Stop the backend server**

```bash
# In the backend terminal
Ctrl+C
```

---

- [ ] **Step 11: Commit and push**

```bash
cd /path/to/acuity
git add frontend/lib/api.types.ts frontend/lib/api.ts
git commit -m "feat: [E6-T2] regenerate API types from Epic 5 backend + new helpers

Closes #42"
git push -u origin feat/epic6-task2-contract-validation
```

---

- [ ] **Step 12: Open PR**

```bash
gh pr create \
  --repo krishna-kodes/acuity \
  --base main \
  --title "[E6-T2] API contract validation — regenerated types + new helpers" \
  --body "## Summary
Regenerates api.types.ts from the live Epic 5 backend and adds typed helpers for all new endpoints (project CRUD, redaction decisions, phase triggers, phase result GETs, DOCX export URL). Zero TypeScript errors.

## Related issues
Closes #42

## Changes
- \`lib/api.types.ts\` — regenerated from Epic 5 backend OpenAPI spec
- \`lib/api.ts\` — added 10 new helpers; fixed any broken existing helpers

## Dependency check
- [x] Epic 5 fully merged — all backend endpoints are real implementations
- [x] Pulled latest main and rebased before opening PR
- [x] Checked for new issues from the other dev

## Testing
- [x] \`npx tsc --noEmit\` — zero errors
- [x] \`npm run lint\` — clean
- [x] No \`@ts-ignore\` or \`as any\` suppressions"
```

---

- [ ] **Step 13: Merge and clean up**

```bash
gh pr merge --repo krishna-kodes/acuity --squash --delete-branch
git checkout main && git pull origin main
git branch -d feat/epic6-task2-contract-validation 2>/dev/null || true
git fetch --prune
```
