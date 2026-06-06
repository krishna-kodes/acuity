# Epics and Tasks for Acuity

## Status (June 2026)

| Epic | Description | Status |
|------|-------------|--------|
| Epic 0 | Design system + component library | ✅ Complete |
| Epic 1 | Frontend scaffolding + app shell | ✅ Complete |
| Epic 2 | Frontend page implementation | ✅ Complete |
| Epic 3 | Frontend polish + validation + backend gap analysis | ✅ Complete |
| Epic 4 | Backend API scaffold + stub endpoints + typed client | ✅ Complete |
| Epic 5 | Backend implementation + data persistence | 🔄 In progress |
| Epic 6 | End-to-end integration + QA | ⏳ Pending |

**Epic 5 remaining:** #37 LangGraph workflow, #38 PII detection, #40 real API endpoints

**Epic 6 blocked until** Epics 3 + 5 are complete.

## Epic 0: Design system and component library (Claude Design → code)

### Description
Translate the Claude Design file into a working component library before any page scaffolding begins. Extracts design tokens, configures Tailwind and shadcn/ui theming, and implements every reusable component referenced in the UI screens.

**Claude Design file:** https://claude.ai/design/p/01159eb0-0c4b-4129-9342-c1bfa04efae0?file=AI+PM+Tool.html&via=share

### Tasks
1. Open the Claude Design file and extract design tokens:
   - Color palette (primary, secondary, neutral, status colors for `pending | synced | skipped | failed`)
   - Typography scale (font family, sizes, line heights, weights)
   - Spacing scale and layout grid
   - Border radius, shadow, and elevation values
   - Icon set used
2. Configure `tailwind.config.ts` with extracted tokens (extend theme, do not override defaults wholesale).
3. Configure shadcn/ui theming (`components.json`, CSS variables in `globals.css`) to match the design tokens.
4. Implement core reusable components (one component per task, each with a usage example):
   - **`<PhaseProgressStepper>`** — 6-step stepper with `complete | in_progress | locked` states and "Proceed" / "Re-run Phase" actions
   - **`<ProjectCard>`** — summary card for the dashboard project list
   - **`<AppSidebar>`** — navigation sidebar with active phase highlight and metrics link
   - **`<ChatThread>`** — message thread with user/assistant bubbles
   - **`<TBDClarificationWidget>`** — per-TBD item with Answer / TBD / Out-of-Scope action selector and resolved/outstanding count
   - **`<RedactionHighlight>`** — inline document viewer with PII spans highlighted and confirm/override controls
   - **`<SyncStatusBadge>`** — status badge for `pending | synced | skipped | failed`
   - **`<EpicTaskListItem>`** — epic or task row with title, estimated points, sync status, and skip control
   - **`<MetricsStatCard>`** — single-value stat card used across all metrics tabs
   - **`<MetricsLineChart>`** and **`<MetricsBarChart>`** — Recharts wrappers themed to design tokens
5. Write a component index at `components/index.ts` that re-exports all of the above.
6. Smoke-test all components in a single `app/design-system/page.tsx` preview route (not shipped to production).

### Dependencies
- Claude Design file must be accessible.
- No backend dependency — all components use static/mock props.

### Definition of done
- All components render without error.
- Design tokens match the Claude Design file (colors, type, spacing).
- `app/design-system/page.tsx` shows every component in all relevant states.
- Epic 1 can begin immediately after.

## Epic 1: Frontend scaffolding and core UI
### Description
Create the main application shell, route structure, navigation, and initial page designs.

### Tasks
1. Initialize the frontend repo with `Next.js App Router`, TypeScript, Tailwind CSS, and `shadcn/ui`.
2. Configure the app shell, global layout, fonts, and theme.
3. Add navigation/sidebar and top-level route scaffolding.
4. Define the main routes from `DESIGN_HANDOFF.md`:
   - `/`
   - `/projects/new`
   - `/projects/[id]/redaction`
   - `/projects/[id]/chat`
   - `/projects/[id]/techstack`
   - `/projects/[id]/team`
   - `/projects/[id]/estimation`
   - `/projects/[id]/epics`
   - `/projects/[id]/metrics`
5. Build the landing/dashboard shell and placeholder widgets.
6. Confirm the design handoff link and asset details in `DESIGN_HANDOFF.md`.

### Dependencies
- Completion of Epic 0 (design system and component library).

## Epic 2: Frontend page implementation
### Description
Implement the key user-facing screens and reusable UI components.

### Tasks
1. Build the project upload/new screen with upload form components.
2. Build the redaction review screen with document preview placeholders.
3. Build the chat/refinement page with message thread UI.
4. Build the tech stack review page.
5. Build the team suggestion page.
6. Build the effort estimation page.
7. Build the epic/task review page.
8. Build the metrics dashboard page with charts and status panels.
9. Add responsive layout support and mobile-friendly breakpoints.

### Dependencies
- Completion of Epic 1.
- Design handoff approval.

## Epic 3: Frontend polish and user validation
### Description
Refine the UI, add real interactions, and validate flows with the design spec.

### Tasks
1. Convert placeholder components into styled cards, tables, and forms.
2. Add loading states, empty states, and error states.
3. Wire basic client-side navigation and state for page transitions.
4. Validate the UI against the Claude Design screens.
5. Document any missing backend requirements discovered during UI work.

### Dependencies
- Completion of Epic 2.

## Epic 4: Backend API contract and stub endpoints
### Description
Define the backend API surface needed for the frontend and implement stub endpoints.

### Tasks
1. Define API route contracts for each frontend page using `/api/v1/` prefix.
2. Create FastAPI app scaffolding and initial route definitions.
3. Add stub responses for frontend integration.
4. Add OpenAPI docs generation and confirm route names.
5. Create a small API client or fetch wrapper for the frontend.

### Dependencies
- Completion of Epic 1.
- Preferably after Epic 2 has clarified page data needs.

## Epic 5: Backend implementation and data persistence
### Description
Build the backend data layer, embeddings, LangGraph workflow state, and GitHub sync.

### Tasks
1. Implement SQLite schema and Alembic migrations.
2. Implement ChromaDB ingestion with `PersistentClient` and `text-embedding-3-small`.
3. Add LangGraph workflow and `SqliteSaver` checkpointer.
4. Implement PII detection, encryption, and ingest guards.
5. Implement GitHub MCP sync tools for milestones and issues.
6. Add API endpoints for projects, phases, exports, and factory seed data.

### Dependencies
- Completion of Epic 4.
- API contracts stabilized by frontend needs.

## Epic 6: End-to-end integration and QA
### Description
Connect frontend and backend, run validation tests, and prepare for first project demo.

### Tasks
1. Connect frontend pages to backend endpoints.
2. Validate the `/api/v1/` contract and fix mismatches.
3. Add basic test coverage for backend routes and frontend integration points.
4. Add documentation updates to `README.md`, `CONTRIBUTING.md`, and `DESIGN_HANDOFF.md`.
5. Conduct a demo of the main workflow from upload to epic/task review.

### Dependencies
- Completion of Epics 1 through 5.
