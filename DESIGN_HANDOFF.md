# Design Handoff

## Claude Design link
- [AI PM Tool — Claude Design file](https://claude.ai/design/p/01159eb0-0c4b-4129-9342-c1bfa04efae0?file=AI+PM+Tool.html&via=share)

## Overview
- **Product:** AI-driven project management tool for engineering PMs
- **Target user:** A PM who uploads a requirements document (PDF/DOCX), refines it through an AI chat interface, and exports structured epics/tasks to GitHub
- **Core flow:** Upload → PII redaction review → Chat & clarification → Proposal generation → Tech stack review → Team suggestion → Effort estimation → Epic/task review → GitHub sync
- **Phase model:** Six phases, each PM-initiated via a "Proceed" button. Phase N is locked until Phase N−1 is complete. PMs can navigate backward to review but not re-run a completed phase without an explicit "Re-run Phase" action.

---

## Screens and routes

| Route | Screen | Phase |
|-------|--------|-------|
| `/` | Project dashboard — list of all projects with status | — |
| `/projects/new` | Upload requirements document | Phase 1 |
| `/projects/[id]/redaction` | PII redaction review — confirm or override anonymization | Phase 1 |
| `/projects/[id]/chat` | Chat & refinement + TBD clarification widget | Phase 2 |
| `/projects/[id]/techstack` | Tech stack suggestion review | Phase 3 |
| `/projects/[id]/team` | Team suggestion review | Phase 4 |
| `/projects/[id]/estimation` | Effort estimation review | Phase 5 |
| `/projects/[id]/epics` | Epic & task review + GitHub sync controls | Phase 6 |
| `/projects/[id]/metrics` | Metrics dashboard (5 tabs) | All phases |

---

## Key components

### Phase progress indicator
- Stepper or breadcrumb showing phases 1–6 with status: `complete | in_progress | locked`
- "Proceed" button advances to the next phase; disabled until current phase is complete
- "Re-run Phase" action available on completed phases (requires explicit click)

### Redaction review (`/projects/[id]/redaction`)
- Shows the original document with detected PII highlighted (names, orgs, emails, phone numbers, etc.)
- PM can confirm or override each anonymization decision before chunking begins
- Two detection types surfaced: regex matches (structured PII) and NER matches (contextual PII)

### Chat & refinement (`/projects/[id]/chat`)
- Standard message thread UI (user/assistant bubbles)
- **TBD clarification widget:** For each TBD item surfaced by the AI, the PM selects one of three actions:
  - **Answer** — provide the missing information inline
  - **TBD** — acknowledge and leave unresolved
  - **Out-of-Scope** — mark as not applicable to this project
- Each clarification is persisted; the widget shows resolved vs. outstanding TBDs
- "Generate Proposal" button appears once the PM is satisfied with the refinement — triggers proposal generation (not inline editing of the original document)

### Epic & task review (`/projects/[id]/epics`)
- List of epics (GitHub Milestones) with nested tasks (GitHub Issues)
- Each item shows: title, description, estimated points, sync status (`pending | synced | skipped | failed`)
- "Sync to GitHub" button triggers the FastMCP sync; individual items can be skipped
- Sync errors displayed inline per item

### Metrics dashboard (`/projects/[id]/metrics`)
Five tabs, all scoped to the current project:

| Tab | Content |
|-----|---------|
| Token Usage & Cost | Token count and USD cost per LLM call; running session total |
| AI Quality | DeepEval pass rates for proposal completeness and tech stack rationale |
| Retrieval | RAG context recall and answer relevancy scores; TBD detection precision/recall across clarification rounds |
| Error Handling | Error rates and retry counts per phase; failed GitHub sync attempts |
| Latency | P50/P95 latency per LangGraph agent node |

Charts: Recharts (line charts for trends, bar charts for per-phase breakdown, stat cards for current values).

### Navigation / sidebar
- Project list or breadcrumb navigation
- Active phase highlighted
- Link to metrics from any project screen

---

## Frontend implementation notes
- Stack: Next.js **16.2.7** App Router, TypeScript, Tailwind CSS **v4**, shadcn/ui v4.10.0
- Tailwind v4: CSS-based `@theme` config in `globals.css` — no `tailwind.config.ts`
- Use shadcn/ui for: form controls, buttons, cards, dialogs, badges, tabs (metrics)
- Custom components (no shadcn): PhaseProgressStepper, SyncStatusBadge, EpicTaskListItem, ChatThread, TBDClarificationWidget, RedactionHighlight, MetricsStatCard, MetricsLineChart, MetricsBarChart
- Use Recharts only on the metrics page
- Keep API integration separate from UI scaffolding until Epic 4 is complete — build with mock/stub data first
- Loading, empty, and error states required on every data-fetching screen
- Icons: inline SVG only — no external icon library

---

## Implementation status

| Epic | Tasks | Status |
|------|-------|--------|
| Epic 0 — Design System | Tokens, theming, all 10 base components, barrel index, design-system preview route | ✅ Complete |
| Epic 1 — App Shell | Root layout, (app) route group, sidebar + topbar, all 9 route stubs, project dashboard | ✅ Complete |
| Epic 2 — Upload screen | `/projects/new` drag-drop upload | ✅ Complete |
| Epic 3 — Phase screens | All 7 phase pages + phase transition lib | ✅ Complete |
| Epic 4 — API integration | Fetch wrapper (`openapi-fetch`), typed API client, TanStack Query wiring | ✅ Complete |
| Epic 5 — Backend implementation | T5 GitHub MCP sync tools done; T1 DB schema + T2 ChromaDB in progress (krishna-augment) | 🔄 In Progress |
| W11 — Evals | 15 test cases, 18 graders, harness, CI gate (`eval_suite.py`) | ✅ Complete |
| Epic 6 — E2E integration | Blocked on Epic 5 completion | ⏳ Pending |

---

## Design validation (E3-T4) — June 2026

Audit of implemented screens against design spec. Each finding is tagged **MINOR** (cosmetic/label), **GAP** (missing feature needed for Epic 4 wiring), or **POST-MVP** (out of scope).

### Confirmed matches ✅
- **Phase stepper** — 6 phases, complete/in_progress/locked states, connector lines, `onRerun` prop available on the component
- **TBD widget** — 3 actions (Answer / Keep TBD / Out of Scope), expand/collapse per item, outstanding/resolved counts
- **RedactionHighlight** — per-row confirm/override, "Redact all" batch, confidence badge, type colour coding
- **Chat layout** — two-column desktop (chat + TBD panel), stacked mobile, generate-proposal gate requires all TBDs resolved
- **Metrics** — 5 tabs, stat cards, Recharts line and bar charts, all tab content wired to mock data
- **EpicTaskListItem** — checkbox skip toggle, task expand, per-item sync status badge
- **Mobile responsive** — sidebar overlay + hamburger, estimation table `overflow-x-auto`, chat panel stacks on `<lg`

### Discrepancies and gaps

| # | Screen | Issue | Severity |
|---|--------|-------|----------|
| D1 | TBD widget | Button label "Keep TBD" should be "TBD" per design spec | MINOR |
| D2 | Phase stepper | `onRerun` prop exists on `PhaseProgressStepper` but no page passes it — "Re-run Phase" is never rendered | GAP |
| D3 | Epics page | `EpicItem` and `TaskItem` have no `description` field; GitHub Issues require a `body`; Epic 4 sync will need this | GAP |
| D4 | Epics page | Sync error state is global (`ErrorBanner`) — design specifies inline error per epic row | GAP |
| D5 | Redaction page | Shows a flat list of PII spans, not inline highlights within the document text — acceptable for mock; Epic 4 needs a document text field or a separate inline-view component | GAP |
| D6 | Dashboard | `ProjectCard` shows current phase name only; design shows phase progress fraction (e.g. "3 / 6") | MINOR |
| D7 | All screens | No "Export DOCX" button — `GET /api/v1/projects/{id}/export/proposal` is in API spec but has no UI entry point | GAP |
| D8 | Chat page | TBD action "oos" label is "Out of Scope" (no hyphen) vs design "Out-of-Scope" | MINOR |

### Epic 4 action items derived from this audit
- **D2** Wire `onRerun` on each page by passing `handleRerun` to `PhaseProgressStepper` (requires `POST /api/v1/projects/{id}/phases/{n}/rerun`)
- **D3** Add `description?: string` to `EpicItem` and `TaskItem`; populate from API response; render as collapsed sub-text under title
- **D4** Add `syncError?: string` to `EpicItem`; render inline below task list when set
- **D5** Persist anonymized document text in backend response; add scrollable document view alongside the span list
- **D7** Add "Export Proposal" button on the proposal/review screen (or sidebar); call `GET /api/v1/projects/{id}/export/proposal` with `Content-Disposition: attachment`

---

## Assets and specs
> Extracted from Claude Design file and implemented in `frontend/app/globals.css` and `frontend/components/`:

- **Color palette:** Full token set in `globals.css` `:root` — primary (`#3A6EA5`), surfaces, status colors (success/warning/destructive), sidebar tokens, chart palette
- **Typography:** Inter (sans), JetBrains Mono (mono) via `next/font/google`
- **Spacing / layout:** `--height-topbar: 56px`, `--width-sidebar: 220px`, border radius scale xs→full
- **Icons:** Inline SVG in `AppSidebar` — dashboard, upload, shield, chat, layers, users, calculator, list, chart
- **Component specs:** PhaseProgressStepper (6 phases, complete/in_progress/locked), TBDClarificationWidget (answered/tbd/oos), RedactionHighlight (confirmed/override)
- **Preview route:** `http://localhost:3000/design-system` renders all Epic 0 components

---

## Open questions
- **Mobile breakpoints:** Are there specific breakpoints or device targets to prioritize? (flagged — ask Krishna)
- **Auth / user identity:** No auth screen in scope for MVP — confirm with Krishna
