# Acuity

## Project status
- This repository currently contains the project plan and architecture handover in `CLAUDE.md`.
- Application source code has not yet been added.

## Tech stack (planned)
- Frontend: Next.js App Router, Tailwind CSS, shadcn/ui
- Backend: FastAPI + Uvicorn
- Database: SQLite + SQLAlchemy + Alembic
- Vector DB: ChromaDB with `PersistentClient`
- Orchestration: LangGraph with `SqliteSaver`
- Embeddings: `text-embedding-3-small` (1536 dims)

## Collaboration
- Use feature branches for all work.
- Create pull requests for review before merging into `main`.
- The first frontend developer should focus on scaffold, routing, and initial UI screens.

## Design handoff
- Add the Claude Design share link, assets, and notes to `DESIGN_HANDOFF.md`.
- Map the design screens to `app/` routes and prioritize the main user flows.

## Next steps
1. Add frontend source code and initial page scaffolding.
2. Add backend source code and API route definitions.
3. Use `CONTRIBUTING.md` for branch, PR, and issue conventions.
4. Use `EPICS_TASKS.md` to guide prioritized work and dependencies.
