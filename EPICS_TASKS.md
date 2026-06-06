# Epics and Tasks for Acuity

## Priority note
- Frontend build is the highest priority.
- Backend work should begin only after the frontend app shell, route structure, and primary screens are defined.
- Use this document to drive Claude-generated epics, tasks, and dependencies.

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
- None. This epic must complete before backend contract work begins.

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
