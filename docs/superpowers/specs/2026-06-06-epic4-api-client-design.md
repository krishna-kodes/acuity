# Epic 4 (T5): Typed API Client — Spec

**Goal:** Build a typed API client in `frontend/lib/api.ts` covering all 15 `/api/v1/` endpoints, backed by auto-generated OpenAPI types and TanStack Query for data fetching in components.

**Issue:** #34

**Branch:** `feat/epic4-task5-api-client`

---

## Packages

| Package | Type | Purpose |
|---------|------|---------|
| `openapi-typescript` | devDependency | Generates `lib/api.types.ts` from live `/openapi.json` |
| `openapi-fetch` | dependency | Typed `fetch` client using generated types; zero runtime overhead |
| `@tanstack/react-query` | dependency | Caching, loading, error, stale states for data-fetching screens |

Install:
```bash
cd frontend
npm install openapi-fetch @tanstack/react-query
npm install --save-dev openapi-typescript
```

---

## File structure

```
frontend/
├── lib/
│   ├── api.types.ts       # auto-generated — never edit by hand
│   ├── api.ts             # typed client + per-endpoint helpers
│   └── query-client.ts    # singleton QueryClient
└── app/
    └── providers.tsx      # QueryClientProvider for App Router
```

---

## `package.json` scripts addition

```json
"gen:api": "openapi-typescript http://localhost:8000/openapi.json -o lib/api.types.ts"
```

Regenerate `api.types.ts` whenever the backend schema changes (e.g., after Epic 5 replaces stubs):
```bash
cd frontend && npm run gen:api
```

`api.types.ts` is committed to the repo — `krishna-kodes` does not need the backend running for normal dev.

---

## `frontend/lib/api.ts`

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

## `frontend/lib/query-client.ts`

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

## `frontend/app/providers.tsx`

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

Wire into `frontend/app/(app)/layout.tsx` by wrapping children:
```typescript
import { Providers } from "@/app/providers"
// ...
<Providers>{children}</Providers>
```

---

## Environment

Add to `frontend/.env.local` (not committed):
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Add to root `.env.example`:
```bash
NEXT_PUBLIC_API_URL=    # backend URL; defaults to http://localhost:8000
```

---

## Usage pattern in page components

```typescript
import { useQuery } from "@tanstack/react-query"
import { getTBDs } from "@/lib/api"

export function TBDsPanel({ projectId }: { projectId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["tbds", projectId],
    queryFn: () => getTBDs(projectId),
  })

  if (isLoading) return <Skeleton />
  if (error) return <ErrorState />
  return <TBDList items={data?.data ?? []} />
}
```

No raw `fetch` calls in components — always use a helper from `lib/api.ts`.

---

## Verification

```bash
cd frontend
npx tsc --noEmit   # all types must compile clean
npm run lint       # no raw fetch calls in components
```

---

## Definition of done

- `npm install` succeeds with new packages
- `npm run gen:api` generates `lib/api.types.ts` from the running backend
- `api.types.ts` committed to repo
- `lib/api.ts` exports one typed helper per endpoint (15 total)
- `lib/query-client.ts` and `app/providers.tsx` created
- `Providers` wired into root layout
- `NEXT_PUBLIC_API_URL` added to root `.env.example`
- `npx tsc --noEmit` passes
- `npm run lint` passes
