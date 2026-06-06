# Epic 0: Design System & Component Library — Spec

**Goal:** Scaffold the Next.js frontend, configure the design system from the Claude Design file, and implement the 10 core reusable components before any page work begins.

**Approach:** shadcn/ui-first — design tokens as CSS variables, shadcn primitives as the base for all custom components.

**Design file:** `/Users/krishna/Projects/acuity/docs/AI PM Tool (standalone).html`

---

## Project Structure

```
acuity/
├── frontend/
│   ├── app/
│   │   ├── layout.tsx                  # root layout, fonts, AppSidebar
│   │   ├── page.tsx                    # dashboard stub (/)
│   │   ├── design-system/
│   │   │   └── page.tsx                # component preview (dev only)
│   │   └── projects/
│   │       ├── new/page.tsx
│   │       └── [id]/
│   │           ├── redaction/page.tsx
│   │           ├── chat/page.tsx
│   │           ├── techstack/page.tsx
│   │           ├── team/page.tsx
│   │           ├── estimation/page.tsx
│   │           ├── epics/page.tsx
│   │           └── metrics/page.tsx
│   ├── components/
│   │   ├── ui/                         # shadcn auto-generated primitives
│   │   └── acuity/                     # 10 custom product components
│   │       ├── phase-progress-stepper.tsx
│   │       ├── app-sidebar.tsx
│   │       ├── project-card.tsx
│   │       ├── chat-thread.tsx
│   │       ├── tbd-clarification-widget.tsx
│   │       ├── redaction-highlight.tsx
│   │       ├── sync-status-badge.tsx
│   │       ├── epic-task-list-item.tsx
│   │       ├── metrics-stat-card.tsx
│   │       ├── metrics-charts.tsx
│   │       └── index.ts                # re-exports all 10
│   ├── lib/
│   │   └── utils.ts                    # shadcn cn() helper
│   ├── styles/
│   │   └── globals.css                 # CSS variables (design tokens)
│   ├── tailwind.config.ts
│   ├── components.json
│   └── package.json
├── backend/                            # empty for now
└── docs/
    └── AI PM Tool (standalone).html    # design source of truth
```

Route pages in Epic 0 are **stubs only** — they render a `<PageTitle>` and a placeholder message. Page content is implemented in Epics 1–3.

---

## Design Tokens

Defined as CSS variables in `frontend/styles/globals.css`, extended into `tailwind.config.ts` as named utilities. shadcn's built-in variables (`--background`, `--foreground`, `--primary`, `--radius`) map to these same values.

### Colour palette (from design file)

```css
:root {
  /* Brand */
  --color-brand:        #D97757;
  --color-brand-muted:  #CC785C;

  /* Backgrounds */
  --color-bg:           #faf9f5;
  --color-surface:      #F9F8F6;
  --color-surface-2:    #F3F2EF;

  /* Borders */
  --color-border:       #ECEAE5;
  --color-border-muted: #E8E6E1;

  /* Text */
  --color-text:         #1A1A19;
  --color-text-muted:   #8A8580;
  --color-text-faint:   #A09D96;

  /* Accents */
  --color-purple:       #7A5AE0;
  --color-blue:         #2A6FDB;

  /* Semantic */
  --color-success:      #2D6A4F;
  --color-success-bg:   #EAF4EF;
  --color-warning:      #92600A;
  --color-warning-bg:   #FEF3E2;
  --color-error:        #C0392B;
  --color-error-bg:     #FDECEA;

  /* Sync status aliases */
  --color-synced:       var(--color-success);
  --color-synced-bg:    var(--color-success-bg);
  --color-pending:      var(--color-warning);
  --color-pending-bg:   var(--color-warning-bg);
  --color-failed:       var(--color-error);
  --color-failed-bg:    var(--color-error-bg);
  --color-skipped:      var(--color-text-muted);
  --color-skipped-bg:   var(--color-surface-2);

  /* Radius */
  --radius-sm:   6px;
  --radius-md:   8px;
  --radius-lg:   12px;
  --radius-pill: 999px;

  /* Typography */
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
```

### Type scale

| Token | Size | Weight | Use |
|-------|------|--------|-----|
| `text-xs` | 11px | 600 | labels, captions |
| `text-sm` | 12px | 400/600 | secondary body |
| `text-base` | 13px | 400 | primary body |
| `text-md` | 14px | 600 | subheadings |
| `text-lg` | 16px | 600 | section headings |
| `text-xl` | 18px | 700 | page titles |
| `text-2xl` | 24px | 700 | stat card numbers |
| `text-3xl` | 28px | 700 | hero numbers |

### shadcn/ui theming mapping

```css
/* shadcn variable → design token */
--background:       var(--color-bg);
--foreground:       var(--color-text);
--primary:          var(--color-brand);
--primary-foreground: #ffffff;
--card:             var(--color-surface);
--card-foreground:  var(--color-text);
--border:           var(--color-border);
--muted:            var(--color-surface-2);
--muted-foreground: var(--color-text-muted);
--radius:           var(--radius-md);
```

---

## shadcn/ui Primitives to Install

Run `npx shadcn@latest add <name>` for each:

`button` `badge` `card` `input` `textarea` `tooltip` `scroll-area` `collapsible` `tabs` `separator`

---

## Component Specifications

All components in `frontend/components/acuity/`. All accept a `className?: string` prop for Tailwind overrides.

---

### 1. `<PhaseProgressStepper>`

**File:** `phase-progress-stepper.tsx`

```typescript
type PhaseStatus = 'complete' | 'in_progress' | 'locked'

interface Phase {
  number: number          // 1–6
  label: string
  status: PhaseStatus
}

interface PhaseProgressStepperProps {
  phases: Phase[]
  canProceed: boolean       // true when current phase backend work is done; enables the Proceed button
  onProceed: () => void
  onRerun: (phaseNumber: number) => void
  className?: string
}
```

- Horizontal row of 6 numbered circles connected by lines
- `complete`: filled brand colour + checkmark icon
- `in_progress`: brand colour outline + pulsing indicator
- `locked`: muted grey, non-interactive
- "Proceed" button (brand colour) shown below the current `in_progress` phase; disabled until phase is complete
- "Re-run Phase" text link shown below any `complete` phase on hover
- *Composes:* shadcn `Button`

---

### 2. `<AppSidebar>`

**File:** `app-sidebar.tsx`

```typescript
interface NavItem {
  label: string
  href: string
  phaseNumber?: number    // 1–6, shown as a small label
}

interface AppSidebarProps {
  projectId?: string      // undefined = dashboard, no phase nav shown
  activeHref: string
  className?: string
}
```

- Fixed left sidebar, `w-56` (224px), `bg-surface-2`
- Top: app logo/name ("Acuity")
- Middle: project nav links for all 9 routes when `projectId` is set; dashboard link only when unset
- Active link: brand colour left border + subtle bg tint
- Bottom: metrics link, user avatar placeholder
- Collapses to `w-12` icon-only on `< lg` breakpoint
- *Composes:* shadcn `Button`, Next.js `Link`

---

### 3. `<ProjectCard>`

**File:** `project-card.tsx`

```typescript
interface ProjectCardProps {
  id: string
  name: string
  currentPhase: number    // 1–6
  status: 'active' | 'complete' | 'draft'
  updatedAt: string       // ISO date string
  className?: string
}
```

- shadcn `Card` with `p-4`, `rounded-lg`, hover shadow
- Project name as `text-md font-semibold`
- Phase shown as `Phase {n}` badge (brand colour, pill)
- Status badge using semantic colours
- Formatted relative timestamp ("2 hours ago")
- Full card is a Next.js `Link` to `/projects/{id}/chat`
- *Composes:* shadcn `Card`, `Badge`

---

### 4. `<ChatThread>`

**File:** `chat-thread.tsx`

```typescript
interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

interface ChatThreadProps {
  messages: Message[]
  onSend: (content: string) => void
  isLoading?: boolean
  className?: string
}
```

- `ScrollArea` fills available height; new messages scroll to bottom
- User bubbles: right-aligned, brand colour bg, white text
- Assistant bubbles: left-aligned, `bg-surface`, border, dark text
- Input row: fixed at bottom, `Input` + send `Button`
- `isLoading` shows a typing indicator (3 animated dots) as the last message
- *Composes:* shadcn `Button`, `Input`, `ScrollArea`

---

### 5. `<TBDClarificationWidget>`

**File:** `tbd-clarification-widget.tsx`

```typescript
type TBDAction = 'answer' | 'tbd' | 'out_of_scope' | null

interface TBDItem {
  id: string
  question: string
  action: TBDAction
  answer?: string
}

interface TBDClarificationWidgetProps {
  items: TBDItem[]
  onAction: (id: string, action: TBDAction, answer?: string) => void
  className?: string
}
```

- Header: "X of Y resolved" count with progress bar
- Each item shows question text and three buttons: **Answer**, **TBD**, **Out-of-Scope**
- Selecting **Answer** expands an inline `Textarea` + confirm button
- Selected action is highlighted; selection can be changed
- Resolved items visually dimmed but still editable
- *Composes:* shadcn `Button`, `Badge`, `Textarea`

---

### 6. `<RedactionHighlight>`

**File:** `redaction-highlight.tsx`

```typescript
interface PIISpan {
  id: string
  text: string              // original PII text
  replacement: string       // anonymised replacement
  type: 'regex' | 'ner'
  confirmed: boolean        // true = keep redaction, false = override
}

interface RedactionHighlightProps {
  documentText: string      // full document with PII replaced
  spans: PIISpan[]
  onConfirm: (id: string) => void
  onOverride: (id: string) => void
  className?: string
}
```

- Renders document text with PII replacement tokens highlighted in amber (`warning-bg`)
- Clicking a highlight opens a `Tooltip`-style popover showing: original text, replacement, type badge, **Confirm** and **Override** buttons
- Confirmed spans: green tint; overridden spans: strikethrough + original text restored
- Summary bar at top: "N confirmed, M overridden, K pending"
- *Composes:* shadcn `Button`, `Badge`, `Tooltip`

---

### 7. `<SyncStatusBadge>`

**File:** `sync-status-badge.tsx`

```typescript
type SyncStatus = 'pending' | 'synced' | 'skipped' | 'failed'

interface SyncStatusBadgeProps {
  status: SyncStatus
  className?: string
}
```

- Pill badge using CSS variable colour pairs per status
- Icons: `pending` → clock, `synced` → check, `skipped` → dash, `failed` → x
- *Composes:* shadcn `Badge`

---

### 8. `<EpicTaskListItem>`

**File:** `epic-task-list-item.tsx`

```typescript
interface TaskItem {
  id: string
  title: string
  estimatedPoints: number
  syncStatus: SyncStatus
}

interface EpicTaskListItemProps {
  id: string
  title: string
  estimatedPoints: number
  syncStatus: SyncStatus
  tasks?: TaskItem[]        // if provided, renders as collapsible epic
  onToggleSkip: (id: string) => void   // toggles between skipped and pending
  className?: string
}
```

- Single row: title, estimated points pill, `<SyncStatusBadge>`, "Skip" toggle
- When `tasks` is provided: renders as a collapsible epic with chevron; tasks render as indented rows
- Skipped items are visually dimmed
- *Composes:* shadcn `Collapsible`, `Button`; uses `<SyncStatusBadge>`

---

### 9. `<MetricsStatCard>`

**File:** `metrics-stat-card.tsx`

```typescript
interface MetricsStatCardProps {
  label: string
  value: string | number
  delta?: {
    value: number           // positive = up, negative = down
    label: string           // e.g. "vs last run"
  }
  className?: string
}
```

- shadcn `Card` with label (`text-sm text-muted`), large value (`text-3xl font-bold`), optional delta row with up/down arrow in semantic colour
- *Composes:* shadcn `Card`

---

### 10. `<MetricsLineChart>` + `<MetricsBarChart>`

**File:** `metrics-charts.tsx`

```typescript
interface ChartDataPoint {
  label: string
  [key: string]: string | number
}

interface MetricsLineChartProps {
  data: ChartDataPoint[]
  dataKeys: string[]        // one line per key
  className?: string
}

interface MetricsBarChartProps {
  data: ChartDataPoint[]
  dataKey: string
  className?: string
}
```

- Both use Recharts `ResponsiveContainer` at `w-full h-full`
- Colours drawn from design tokens: primary series = `--color-brand`, secondary = `--color-blue`, tertiary = `--color-purple`
- Consistent axis style: muted text, no border, subtle grid lines
- *Uses:* Recharts `LineChart`, `BarChart`, `XAxis`, `YAxis`, `Tooltip`, `ResponsiveContainer`

---

## Component Index

`frontend/components/acuity/index.ts` re-exports all 10 components:

```typescript
export { PhaseProgressStepper } from './phase-progress-stepper'
export { AppSidebar } from './app-sidebar'
export { ProjectCard } from './project-card'
export { ChatThread } from './chat-thread'
export { TBDClarificationWidget } from './tbd-clarification-widget'
export { RedactionHighlight } from './redaction-highlight'
export { SyncStatusBadge } from './sync-status-badge'
export { EpicTaskListItem } from './epic-task-list-item'
export { MetricsStatCard } from './metrics-stat-card'
export { MetricsLineChart, MetricsBarChart } from './metrics-charts'
```

---

## Design System Preview Page

`frontend/app/design-system/page.tsx` renders every component in all relevant states with static mock data. Not linked in the app nav. Serves as a smoke-test that all components render without error and all token values are applied correctly.

Sections:
1. Colour palette swatches (all CSS variables)
2. Typography scale
3. `<PhaseProgressStepper>` — all 3 phase states
4. `<AppSidebar>` — with and without projectId
5. `<ProjectCard>` — active, complete, draft
6. `<ChatThread>` — static messages + loading state
7. `<TBDClarificationWidget>` — mix of answered, pending, out-of-scope items
8. `<RedactionHighlight>` — confirmed, overridden, pending spans
9. `<SyncStatusBadge>` — all 4 statuses
10. `<EpicTaskListItem>` — epic with tasks, skipped state
11. `<MetricsStatCard>` — with and without delta
12. `<MetricsLineChart>` and `<MetricsBarChart>`

---

## Scaffold Steps

1. `cd acuity && npx create-next-app@latest frontend --typescript --tailwind --app --src-dir no --import-alias "@/*"`
2. `cd frontend && npx shadcn@latest init` — select custom theme, confirm CSS variables
3. Install shadcn primitives: `npx shadcn@latest add button badge card input textarea tooltip scroll-area collapsible tabs separator`
4. Install Recharts: `npm install recharts`
5. Replace `globals.css` with design token CSS variables
6. Update `tailwind.config.ts` to extend theme with token names
7. Update `components.json` with correct paths
8. Create stub route pages (layout + empty pages for all 9 routes)

---

## Definition of Done

- `npm run dev` starts without errors
- `npx tsc --noEmit` passes with zero errors
- `npm run lint` passes
- All 10 components render in `app/design-system/page.tsx` in all specified states
- Token colours visually match the Claude Design file
- No Jira references anywhere in the codebase
