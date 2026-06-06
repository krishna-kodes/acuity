# AI Agent Instructions for Acuity

## Purpose
This file is for AI coding agents to understand the current project and make productive, low-risk contributions.

## Current workspace state
- The repository currently contains only `CLAUDE.md`.
- `CLAUDE.md` is the primary source of truth for architecture, design decisions, env vars, and the MVP implementation plan.
- There is no application source code present in the workspace yet.

## What agents should do
- Use `CLAUDE.md` as the reference for architecture and conventions.
- Do not make assumptions about missing source files or implementation details.
- Before implementing features, ask the user for the actual code files or repo contents if they are not available.

## Key project facts
- Full-stack AI-driven project management tool.
- Backend: FastAPI + Uvicorn, SQLite + SQLAlchemy/Alembic, ChromaDB, LangGraph.
- Frontend: Next.js App Router, Tailwind CSS, shadcn/ui.
- GitHub is the integration target; Jira was intentionally replaced.
- Embeddings must use `text-embedding-3-small` with `1536` dimensions.
- LangGraph checkpointer must use `SqliteSaver`, never `MemorySaver`.
- All API routes are prefixed `/api/v1/`.

## Agent behavior guidance
- Preserve existing documentation and link to it rather than duplicating it.
- Keep changes minimal and aligned with the plan in `CLAUDE.md`.
- When asked to implement code, verify that source files exist before editing.
- If asked to create project scaffolding, request confirmation on stack and repo layout.

## Next steps for this repo
- Add `.github/copilot-instructions.md` or additional agent customization files once source code exists.
- Add a real `README.md` and `CONTRIBUTING.md` when the project repository structure is established.
- When frontend work begins, prioritize the design handoff in `DESIGN_HANDOFF.md`.
- For frontend ownership, track route and screen mapping clearly so the first developer can start with page scaffolding and UI components.
