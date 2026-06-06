# Epic 4 (T5): Typed API Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a typed API client in `frontend/lib/api.ts` with one helper per endpoint, backed by auto-generated OpenAPI types and TanStack Query for data fetching.

**Architecture:** `openapi-typescript` generates types from the live backend spec into `lib/api.types.ts` (committed). `openapi-fetch` creates a typed client from those types. `@tanstack/react-query` is set up via `app/providers.tsx` so page components use `useQuery`/`useMutation` hooks instead of raw `fetch`.

**Tech Stack:** TypeScript 5, Next.js 16.2.7 App Router, openapi-fetch, openapi-typescript, @tanstack/react-query

**Spec:** `docs/superpowers/specs/2026-06-06-epic4-api-client-design.md`

---

## File map

```
frontend/
├── package.json                    ← add gen:api script + 3 new deps
├── lib/
│   ├── api.types.ts                ← CREATE: generated from backend OpenAPI spec
│   ├── api.ts                      ← CREATE: typed client + 15 endpoint helpers
│   └── query-client.ts             ← CREATE: singleton QueryClient
├── app/
│   ├── providers.tsx               ← CREATE: QueryClientProvider wrapper
│   └── (app)/
│       └── layout.tsx              ← MODIFY: wrap children with <Providers>
└── .env.local                      ← CREATE: NEXT_PUBLIC_API_URL (not committed)
/.env.example                       ← MODIFY: add NEXT_PUBLIC_API_URL entry
```

---

## Task 1: Install packages, generate types, build API client (Issue #34)

**Branch:** `feat/epic4-task5-api-client`

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/lib/api.types.ts`
- Create: `frontend/lib/api.ts`
- Create: `frontend/lib/query-client.ts`
- Create: `frontend/app/providers.tsx`
- Modify: `frontend/app/(app)/layout.tsx`
- Create: `frontend/.env.local`
- Modify: `.env.example`

---

- [ ] **Step 1: Branch from main**

```bash
cd /path/to/acuity
git checkout main && git pull origin main
git checkout -b feat/epic4-task5-api-client
```

---

- [ ] **Step 2: Write `lib/api.ts` first — this is the failing "test"**

`api.ts` imports from `./api.types` which doesn't exist yet. Creating it first makes `tsc --noEmit` fail — that's the TDD red state.

Create `frontend/lib/api.ts`:

```typescript
import createClient from "openapi-fetch"
import type { paths } from "./api.types"

export const apiClient = createClient<paths>({
  baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
})

// ── Projects ────────────────────────────────────────────────────────────────

export const createProject = (name: string) =>
  apiClient.POST("/api/v1/projects", { body: { name } })

export const uploadDocument = (projectId: string, file: File) => {
  const form = new FormData()
  form.append("file", file)
  return apiClient.POST("/api/v1/projects/{project_id}/documents", {
    params: { path: { project_id: projectId } },
    body: form as never, // openapi-fetch doesn't type FormData bodies; cast required for multipart
  })
}

export const getTBDs = (projectId: string) =>
  apiClient.GET("/api/v1/projects/{project_id}/tbds", {
    params: { path: { project_id: projectId } },
  })

export const submitClarification = (
  projectId: string,
  tbd_id: string,
  action: string,
  answer?: string,
) =>
  apiClient.POST("/api/v1/projects/{project_id}/clarifications", {
    params: { path: { project_id: projectId } },
    body: { tbd_id, action, answer },
  })

export const generateProposal = (projectId: string) =>
  apiClient.POST("/api/v1/projects/{project_id}/proposal", {
    params: { path: { project_id: projectId } },
  })

export const getProposal = (projectId: string) =>
  apiClient.GET("/api/v1/projects/{project_id}/proposal", {
    params: { path: { project_id: projectId } },
  })

export const suggestStack = (projectId: string) =>
  apiClient.POST("/api/v1/projects/{project_id}/stack", {
    params: { path: { project_id: projectId } },
  })

export const estimateEffort = (projectId: string) =>
  apiClient.POST("/api/v1/projects/{project_id}/estimate", {
    params: { path: { project_id: projectId } },
  })

export const syncToGitHub = (projectId: string) =>
  apiClient.POST("/api/v1/projects/{project_id}/sync", {
    params: { path: { project_id: projectId } },
  })

export const getMetrics = (projectId: string) =>
  apiClient.GET("/api/v1/projects/{project_id}/metrics", {
    params: { path: { project_id: projectId } },
  })

// ── Factory ──────────────────────────────────────────────────────────────────

export const seedEmployees = () =>
  apiClient.POST("/api/v1/factory/seed-employees", {})

export const seedProjects = () =>
  apiClient.POST("/api/v1/factory/seed-projects", {})

export const seedTechnologies = () =>
  apiClient.POST("/api/v1/factory/seed-technologies", {})

export const seedAll = () =>
  apiClient.POST("/api/v1/factory/seed-all", {})

export const resetDb = () =>
  apiClient.DELETE("/api/v1/factory/reset-db", {})
```

---

- [ ] **Step 3: Confirm compilation fails (TDD red)**

```bash
cd /path/to/acuity/frontend
npx tsc --noEmit 2>&1 | head -5
```

Expected: error about `Cannot find module './api.types'` or similar. If it passes, `api.types.ts` already exists — skip to Step 6.

---

- [ ] **Step 4: Install packages**

```bash
cd /path/to/acuity/frontend
npm install openapi-fetch @tanstack/react-query
npm install --save-dev openapi-typescript
```

Expected: installs cleanly. `package.json` dependencies updated.

---

- [ ] **Step 5: Add `gen:api` script to `frontend/package.json`**

Open `frontend/package.json` and add the script inside `"scripts"`:

```json
"gen:api": "openapi-typescript http://localhost:8000/openapi.json -o lib/api.types.ts"
```

The scripts section should look like:

```json
"scripts": {
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "lint": "eslint",
  "gen:api": "openapi-typescript http://localhost:8000/openapi.json -o lib/api.types.ts"
}
```

---

- [ ] **Step 6: Start the backend and generate `lib/api.types.ts`**

```bash
# Terminal 1 — start backend (from acuity root)
cd /path/to/acuity/backend
source .venv/bin/activate
uvicorn app.main:app --port 8000

# Terminal 2 — generate types
cd /path/to/acuity/frontend
npm run gen:api
```

Expected: `frontend/lib/api.types.ts` is created. It will be a large file with a `paths` interface covering all 15 routes. Stop the backend server after generation.

---

- [ ] **Step 7: Confirm compilation passes (TDD green)**

```bash
cd /path/to/acuity/frontend
npx tsc --noEmit
```

Expected: exits with 0 errors. If there are errors in `api.ts`, fix them now — they indicate a mismatch between the helper signatures and the generated types.

---

- [ ] **Step 8: Create `frontend/lib/query-client.ts`**

```typescript
import { QueryClient } from "@tanstack/react-query"

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})
```

---

- [ ] **Step 9: Create `frontend/app/providers.tsx`**

```typescript
"use client"

import { QueryClientProvider } from "@tanstack/react-query"
import { queryClient } from "@/lib/query-client"

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}
```

---

- [ ] **Step 10: Wire `Providers` into `frontend/app/(app)/layout.tsx`**

Current content of `frontend/app/(app)/layout.tsx`:
```typescript
import { AppShell } from "@/components/app-shell";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
```

Replace with:
```typescript
import { AppShell } from "@/components/app-shell"
import { Providers } from "@/app/providers"

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <Providers>
      <AppShell>{children}</AppShell>
    </Providers>
  )
}
```

---

- [ ] **Step 11: Add env var to `.env.local` and `.env.example`**

Create `frontend/.env.local` (not committed — already in `.gitignore`):
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Open root `.env.example` and add at the end:
```bash
# Frontend
NEXT_PUBLIC_API_URL=    # backend base URL; defaults to http://localhost:8000
```

---

- [ ] **Step 12: Final compilation and lint check**

```bash
cd /path/to/acuity/frontend
npx tsc --noEmit
npm run lint
```

Expected: both pass with zero errors.

---

- [ ] **Step 13: Verify dev server starts**

```bash
cd /path/to/acuity/frontend
npm run dev
```

Open `http://localhost:3000`. Expected: app loads without console errors. Stop the server (`Ctrl+C`).

---

- [ ] **Step 14: Commit and push**

```bash
cd /path/to/acuity
git add frontend/ .env.example
git commit -m "feat: [E4-T5] typed API client with openapi-fetch and TanStack Query

Closes #34"
git push -u origin feat/epic4-task5-api-client
```

---

- [ ] **Step 15: Open PR**

```bash
gh pr create \
  --repo krishna-kodes/acuity \
  --base main \
  --title "[E4-T5] Typed API client with openapi-fetch and TanStack Query" \
  --body "## Summary
Adds a fully typed API client in \`lib/api.ts\` with one helper per endpoint (15 total), backed by auto-generated OpenAPI types. TanStack Query is set up via \`app/providers.tsx\` so page components use hooks instead of raw fetch.

## Related issues
Closes #34

## Changes
- \`lib/api.types.ts\` — auto-generated from backend OpenAPI spec (committed)
- \`lib/api.ts\` — typed client + 15 endpoint helpers
- \`lib/query-client.ts\` — singleton QueryClient (staleTime 30s, retry 1)
- \`app/providers.tsx\` — QueryClientProvider wrapper
- \`app/(app)/layout.tsx\` — wired Providers
- \`package.json\` — added gen:api script, openapi-fetch, @tanstack/react-query
- \`.env.example\` — added NEXT_PUBLIC_API_URL

## Regenerating types
When Epic 5 changes backend schemas:
\`\`\`bash
cd frontend && npm run gen:api
\`\`\`

## Dependency check
- [x] Epic 1 complete — frontend routes exist
- [x] Epic 4 T1–T4 merged — all 15 endpoints live and documented in /docs
- [x] I pulled latest \`main\` and rebased before opening the PR
- [x] I checked for new issues from the other dev

## Testing
- [x] \`npx tsc --noEmit\` passes
- [x] \`npm run lint\` passes
- [x] \`npm run dev\` starts without errors"
```

---

- [ ] **Step 16: Merge and clean up**

```bash
gh pr merge --repo krishna-kodes/acuity --squash --delete-branch
git checkout main && git pull origin main
git branch -d feat/epic4-task5-api-client 2>/dev/null || true
git fetch --prune
```
