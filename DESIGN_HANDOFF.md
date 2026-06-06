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
- Stack: Next.js 14+ App Router, TypeScript, Tailwind CSS, shadcn/ui
- Use shadcn/ui for: form controls, buttons, cards, dialogs, badges (sync status), tabs (metrics), stepper (phase progress)
- Use Recharts only on the metrics page
- Keep API integration separate from UI scaffolding until Epic 4 (Backend API Contract) is complete — build with mock/stub data first
- Loading, empty, and error states required on every data-fetching screen

---

## Priority work for frontend
1. Scaffold app shell, global layout, sidebar/navigation, and all 9 routes (Epic 1)
2. Build project dashboard and upload screen (Epic 2)
3. Build chat screen with TBD clarification widget
4. Build redaction review screen
5. Build epic/task review screen with sync status indicators
6. Build metrics dashboard with all 5 tabs and Recharts
7. Add responsive layout — mobile breakpoints TBD (ask Krishna for priority)

---

## Assets and specs
> Extract the following from the Claude Design file before starting implementation:
- Color palette (primary, secondary, neutral, status colors for sync states)
- Typography scale (font family, sizes, weights)
- Spacing and layout grid
- Icon set
- Component-specific specs for the clarification widget and phase stepper

---

## Open questions
- **Mobile breakpoints:** Are there specific breakpoints or device targets to prioritize? (flagged — ask Krishna)
