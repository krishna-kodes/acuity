# Phase Navigation & Client-Side State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire client-side phase transition state so the sidebar locks future phase links and the "Proceed" button on each phase page permanently advances the project's phase in localStorage.

**Architecture:** A `PhaseProvider` React context wraps the app shell and stores `{ [projectId]: maxPhaseReached }` in both React state and `localStorage`. Each phase page calls `advancePhase(nextPhaseNumber)` before navigating. `AppSidebar` reads `maxPhase` from the context and renders locked (non-clickable) `<span>` elements for phase links beyond `maxPhase`.

**Tech Stack:** React context, `localStorage`, Next.js App Router (`"use client"`), TypeScript. No new dependencies.

---

## File Map

| Action | File |
|--------|------|
| Create | `frontend/lib/phase-store.ts` |
| Create | `frontend/context/phase-context.tsx` |
| Modify | `frontend/app/(app)/layout.tsx` |
| Modify | `frontend/components/app-sidebar.tsx` |
| Modify | `frontend/app/(app)/projects/[id]/redaction/page.tsx` |
| Modify | `frontend/app/(app)/projects/[id]/chat/page.tsx` |
| Modify | `frontend/app/(app)/projects/[id]/techstack/page.tsx` |
| Modify | `frontend/app/(app)/projects/[id]/team/page.tsx` |
| Modify | `frontend/app/(app)/projects/[id]/estimation/page.tsx` |

---

## Task 1: Create `lib/phase-store.ts` — localStorage helpers

**Files:**
- Create: `frontend/lib/phase-store.ts`

Phase numbers: 1 = Redaction, 2 = Chat, 3 = Tech Stack, 4 = Team, 5 = Estimation, 6 = Epics. `maxPhase` is the highest phase the user has *entered* — i.e., advancing to Chat sets `maxPhase = 2`, making Chat and all prior phases accessible.

- [ ] **Step 1: Create the file**

`frontend/lib/phase-store.ts`:
```typescript
const KEY = "acuity:phase-store";

function read(): Record<string, number> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}") as Record<string, number>;
  } catch {
    return {};
  }
}

export function getStoredMaxPhase(projectId: string): number {
  return read()[projectId] ?? 1;
}

export function storeMaxPhase(projectId: string, phase: number): void {
  const store = read();
  store[projectId] = Math.max(store[projectId] ?? 1, phase);
  localStorage.setItem(KEY, JSON.stringify(store));
}
```

- [ ] **Step 2: Run type check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git checkout -b feat/epic3-task3-phase-navigation
git add frontend/lib/phase-store.ts
git commit -m "feat(e3-t3): add phase-store localStorage helpers"
```

---

## Task 2: Create `context/phase-context.tsx` — PhaseProvider and hook

**Files:**
- Create: `frontend/context/phase-context.tsx`

- [ ] **Step 1: Create the context file**

`frontend/context/phase-context.tsx`:
```typescript
"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { getStoredMaxPhase, storeMaxPhase } from "@/lib/phase-store";

interface PhaseContextValue {
  maxPhaseFor: (projectId: string) => number;
  advancePhase: (projectId: string, phase: number) => void;
}

const PhaseContext = createContext<PhaseContextValue>({
  maxPhaseFor: () => 1,
  advancePhase: () => undefined,
});

export function PhaseProvider({ children }: { children: React.ReactNode }) {
  const [store, setStore] = useState<Record<string, number>>({});

  useEffect(() => {
    const raw = localStorage.getItem("acuity:phase-store");
    if (raw) {
      try {
        setStore(JSON.parse(raw) as Record<string, number>);
      } catch {
        // malformed storage — start fresh
      }
    }
  }, []);

  const maxPhaseFor = useCallback(
    (projectId: string) => store[projectId] ?? 1,
    [store],
  );

  const advancePhase = useCallback((projectId: string, phase: number) => {
    setStore((prev) => {
      const next = { ...prev, [projectId]: Math.max(prev[projectId] ?? 1, phase) };
      storeMaxPhase(projectId, phase);
      return next;
    });
  }, []);

  return (
    <PhaseContext.Provider value={{ maxPhaseFor, advancePhase }}>
      {children}
    </PhaseContext.Provider>
  );
}

export function useProjectPhase(projectId: string) {
  const { maxPhaseFor, advancePhase } = useContext(PhaseContext);
  return {
    maxPhase: maxPhaseFor(projectId),
    advancePhase: (phase: number) => advancePhase(projectId, phase),
  };
}
```

- [ ] **Step 2: Run type check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/context/phase-context.tsx
git commit -m "feat(e3-t3): add PhaseProvider context and useProjectPhase hook"
```

---

## Task 3: Wire `PhaseProvider` into the app layout

**Files:**
- Modify: `frontend/app/(app)/layout.tsx`

The `(app)` route group layout wraps all project screens. Adding `PhaseProvider` here makes the context available to every phase page and the sidebar.

- [ ] **Step 1: Update the layout**

Replace the full contents of `frontend/app/(app)/layout.tsx` with:
```typescript
import { AppShell } from "@/components/app-shell";
import { PhaseProvider } from "@/context/phase-context";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <PhaseProvider>
      <AppShell>{children}</AppShell>
    </PhaseProvider>
  );
}
```

- [ ] **Step 2: Run type check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(app\)/layout.tsx
git commit -m "feat(e3-t3): wire PhaseProvider into app layout"
```

---

## Task 4: Lock sidebar links for unreachable phases

**Files:**
- Modify: `frontend/components/app-sidebar.tsx`

Phases beyond `maxPhase` render as `<span>` (non-clickable) with muted styling. Phases at or below `maxPhase` remain as `<Link>`.

- [ ] **Step 1: Add `phaseNumber` to `NavItem` and update `buildProjectNav`**

In `frontend/components/app-sidebar.tsx`, change the `NavItem` interface from:
```typescript
export interface NavItem {
  key: string;
  label: string;
  href: string;
  icon: React.ReactNode;
  phase?: string | null;
}
```
to:
```typescript
export interface NavItem {
  key: string;
  label: string;
  href: string;
  icon: React.ReactNode;
  phase?: string | null;
  phaseNumber?: number;
}
```

- [ ] **Step 2: Add `phaseNumber` to each project nav item in `buildProjectNav`**

Replace the `buildProjectNav` function body:
```typescript
function buildProjectNav(projectId: string) {
  const base = `/projects/${projectId}`;
  return [
    { key: "redaction",  label: "Redaction Review", href: `${base}/redaction`,  icon: <IconShield />,     phase: "redaction",  phaseNumber: 1 },
    { key: "chat",       label: "Chat & Refine",     href: `${base}/chat`,       icon: <IconChat />,       phase: "chat",       phaseNumber: 2 },
    { key: "tech-stack", label: "Tech Stack",         href: `${base}/techstack`,  icon: <IconLayers />,     phase: "tech-stack", phaseNumber: 3 },
    { key: "team",       label: "Team",               href: `${base}/team`,       icon: <IconUsers />,      phase: "team",       phaseNumber: 4 },
    { key: "estimation", label: "Estimation",         href: `${base}/estimation`, icon: <IconCalculator />, phase: "estimation", phaseNumber: 5 },
    { key: "epics",      label: "Epics & Tasks",      href: `${base}/epics`,      icon: <IconList />,       phase: "epics",      phaseNumber: 6 },
    { key: "metrics",    label: "Metrics",             href: `${base}/metrics`,    icon: <IconChart />,      phase: null                          },
  ];
}
```

- [ ] **Step 3: Update `NavLink` to render locked items as a `<span>`**

Replace the `NavLink` function:
```typescript
function NavLink({
  item,
  activePhase,
  locked,
}: {
  item: NavItem;
  activePhase?: string | null;
  locked?: boolean;
}) {
  const pathname = usePathname();
  const isActive =
    (item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)) ||
    (item.phase != null && activePhase === item.phase);

  if (locked) {
    return (
      <span
        className="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-text-muted opacity-40 cursor-not-allowed select-none"
        aria-disabled="true"
      >
        {item.icon}
        {item.label}
      </span>
    );
  }

  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors",
        isActive
          ? "bg-accent text-accent-foreground font-medium ring-1 ring-inset ring-accent-foreground/10"
          : "text-text-secondary hover:bg-sidebar-hover hover:text-foreground",
      )}
    >
      {item.icon}
      {item.label}
    </Link>
  );
}
```

- [ ] **Step 4: Read `maxPhase` in `AppSidebar` and pass `locked` to each nav item**

Add the import at the top of the file (after the existing imports):
```typescript
import { useProjectPhase } from "@/context/phase-context";
```

Replace the `AppSidebar` function body's nav section. Find the line:
```typescript
  const projectId = projectIdProp ?? pathname.match(/\/projects\/([^/]+)/)?.[1];
  const projectNav = projectId ? buildProjectNav(projectId) : [];
```
Change it to:
```typescript
  const projectId = projectIdProp ?? pathname.match(/\/projects\/([^/]+)/)?.[1];
  const projectNav = projectId ? buildProjectNav(projectId) : [];
  const { maxPhase } = useProjectPhase(projectId ?? "");
```

Then in the JSX where project nav items are rendered, replace:
```typescript
            {projectNav.map((item) => (
              <NavLink key={item.key} item={item} activePhase={activePhase} />
            ))}
```
with:
```typescript
            {projectNav.map((item) => (
              <NavLink
                key={item.key}
                item={item}
                activePhase={activePhase}
                locked={item.phaseNumber !== undefined && item.phaseNumber > maxPhase}
              />
            ))}
```

- [ ] **Step 5: Run type check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/app-sidebar.tsx
git commit -m "feat(e3-t3): lock sidebar phase links beyond maxPhase"
```

---

## Task 5: Wire `advancePhase` into each phase page's Proceed handler

**Files:**
- Modify: `frontend/app/(app)/projects/[id]/redaction/page.tsx`
- Modify: `frontend/app/(app)/projects/[id]/chat/page.tsx`
- Modify: `frontend/app/(app)/projects/[id]/techstack/page.tsx`
- Modify: `frontend/app/(app)/projects/[id]/team/page.tsx`
- Modify: `frontend/app/(app)/projects/[id]/estimation/page.tsx`

Phase number to advance to when "Proceed" is clicked:
- Redaction proceeds → Chat: advance to **2**
- Chat proceeds → Tech Stack: advance to **3**
- Tech Stack proceeds → Team: advance to **4**
- Team proceeds → Estimation: advance to **5**
- Estimation proceeds → Epics: advance to **6**

---

### 5a — `redaction/page.tsx`

- [ ] **Step 1: Add `useProjectPhase` import**

At the top of `frontend/app/(app)/projects/[id]/redaction/page.tsx`, add after existing imports:
```typescript
import { useProjectPhase } from "@/context/phase-context";
```

- [ ] **Step 2: Call the hook inside the component**

Inside `RedactionPage`, after `const router = useRouter();`, add:
```typescript
  const { advancePhase } = useProjectPhase(params.id);
```

- [ ] **Step 3: Advance phase before navigation in `handleProceed`**

Replace the `handleProceed` function:
```typescript
  async function handleProceed() {
    setProceeding(true);
    // TODO (Epic 4): PATCH /api/v1/projects/{id}/redaction-decisions then POST /api/v1/projects/{id}/phases/2/start
    await new Promise((res) => setTimeout(res, 800));
    advancePhase(2);
    router.push(`/projects/${params.id}/chat`);
  }
```

---

### 5b — `chat/page.tsx`

- [ ] **Step 1: Add `useProjectPhase` import**

At the top of `frontend/app/(app)/projects/[id]/chat/page.tsx`, add after existing imports:
```typescript
import { useProjectPhase } from "@/context/phase-context";
```

- [ ] **Step 2: Call the hook inside the component**

Inside `ChatPage`, after `const router = useRouter();`, add:
```typescript
  const { advancePhase } = useProjectPhase(params.id);
```

- [ ] **Step 3: Advance phase before navigation in `handleGenerateProposal`**

Replace the `handleGenerateProposal` function:
```typescript
  async function handleGenerateProposal() {
    setGenerating(true);
    // TODO (Epic 4): POST /api/v1/projects/{id}/proposal
    await new Promise((res) => setTimeout(res, 1500));
    advancePhase(3);
    router.push(`/projects/${params.id}/techstack`);
  }
```

---

### 5c — `techstack/page.tsx`

- [ ] **Step 1: Add `useProjectPhase` import**

At the top of `frontend/app/(app)/projects/[id]/techstack/page.tsx`, add after existing imports:
```typescript
import { useProjectPhase } from "@/context/phase-context";
```

- [ ] **Step 2: Call the hook inside the component**

Inside `TechStackPage`, after `const router = useRouter();`, add:
```typescript
  const { advancePhase } = useProjectPhase(params.id);
```

- [ ] **Step 3: Advance phase before navigation in `handleProceed`**

Replace the `handleProceed` function:
```typescript
  async function handleProceed() {
    setProceeding(true);
    // TODO (Epic 4): POST /api/v1/projects/{id}/phases/4/start
    await new Promise((res) => setTimeout(res, 800));
    advancePhase(4);
    router.push(getNextPhaseRoute("techstack", params.id));
  }
```

---

### 5d — `team/page.tsx`

- [ ] **Step 1: Add `useProjectPhase` import**

At the top of `frontend/app/(app)/projects/[id]/team/page.tsx`, add after existing imports:
```typescript
import { useProjectPhase } from "@/context/phase-context";
```

- [ ] **Step 2: Call the hook inside the component**

Inside `TeamPage`, after `const router = useRouter();`, add:
```typescript
  const { advancePhase } = useProjectPhase(params.id);
```

- [ ] **Step 3: Advance phase before navigation in `handleProceed`**

Replace the `handleProceed` function:
```typescript
  async function handleProceed() {
    setProceeding(true);
    // TODO (Epic 4): POST /api/v1/projects/{id}/phases/5/start
    await new Promise((res) => setTimeout(res, 800));
    advancePhase(5);
    router.push(getNextPhaseRoute("team", params.id));
  }
```

---

### 5e — `estimation/page.tsx`

- [ ] **Step 1: Add `useProjectPhase` import**

At the top of `frontend/app/(app)/projects/[id]/estimation/page.tsx`, add after existing imports:
```typescript
import { useProjectPhase } from "@/context/phase-context";
```

- [ ] **Step 2: Call the hook inside the component**

Inside `EstimationPage`, after `const router = useRouter();`, add:
```typescript
  const { advancePhase } = useProjectPhase(params.id);
```

- [ ] **Step 3: Advance phase before navigation in `handleProceed`**

Replace the `handleProceed` function:
```typescript
  async function handleProceed() {
    setProceeding(true);
    // TODO (Epic 4): POST /api/v1/projects/{id}/phases/6/start
    await new Promise((res) => setTimeout(res, 800));
    advancePhase(6);
    router.push(getNextPhaseRoute("estimation", params.id));
  }
```

- [ ] **Step 4: Run type check across all modified pages**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 5: Commit all page changes**

```bash
git add \
  frontend/app/\(app\)/projects/\[id\]/redaction/page.tsx \
  frontend/app/\(app\)/projects/\[id\]/chat/page.tsx \
  frontend/app/\(app\)/projects/\[id\]/techstack/page.tsx \
  frontend/app/\(app\)/projects/\[id\]/team/page.tsx \
  frontend/app/\(app\)/projects/\[id\]/estimation/page.tsx
git commit -m "feat(e3-t3): wire advancePhase into all phase page Proceed handlers"
```

---

## Task 6: Smoke test and open PR

- [ ] **Step 1: Start the dev server**

```bash
cd frontend && npm run dev
```

- [ ] **Step 2: Manual flow — verify gate enforcement**

1. Open `http://localhost:3000`
2. Click any project card → lands on `/projects/{id}/redaction`
3. Verify sidebar shows: Redaction (clickable), Chat (locked/greyed), Tech Stack (locked), Team (locked), Estimation (locked), Epics & Tasks (locked)
4. Confirm all PII detections → click "Proceed to Refinement"
5. Verify sidebar now shows: Redaction (clickable), Chat (clickable, active), Tech Stack (locked), ...
6. Reload the page — verify sidebar state is preserved (localStorage)
7. Click back to Redaction — verify it's accessible, stepper shows Phase 1 as "complete"
8. Navigate back to Chat — verify locked phases are still locked

- [ ] **Step 3: Final type check**

```bash
cd frontend && npx tsc --noEmit && npm run lint
```
Expected: no errors or warnings.

- [ ] **Step 4: Open PR**

```bash
gh pr create \
  --title "[E3-T3] Wire client-side phase navigation state" \
  --body "$(cat <<'EOF'
## Summary
- Adds `lib/phase-store.ts`: localStorage read/write for per-project `maxPhase`
- Adds `context/phase-context.tsx`: `PhaseProvider` + `useProjectPhase` hook
- Updates `AppSidebar` to lock phase nav links beyond `maxPhase`
- Wires `advancePhase` into Proceed handlers on all 5 phase pages
- Phase state persists across page reloads via localStorage

## Test plan
- [ ] Navigate to any project → sidebar shows only Redaction as clickable
- [ ] Click Proceed on Redaction → Chat becomes unlocked in sidebar
- [ ] Reload — sidebar state preserved
- [ ] Cannot navigate to locked phase by clicking sidebar link (rendered as `<span>`)
- [ ] Can still navigate backward to completed phases freely
- [ ] `npx tsc --noEmit` passes with no errors

Closes #27
EOF
)"
```
