# Contributing to Acuity

## Overview
This project is currently in early setup. Use this guide for collaboration, branch strategy, and review process once source code is added.

## Branch strategy
- `main`: production-ready code only.
- `dev`: integration branch for merged feature work.
- Feature branches: `feature/<name>` or `fix/<name>`.

## Workflow
1. Create a branch from `dev` or `main` depending on repo policy.
2. Make changes locally and keep commits focused.
3. Open a pull request targeting `dev` or `main`.
4. Request review from at least one teammate before merging.

## Pull request guidelines
- Use descriptive titles and summaries.
- Reference any related issue or design link.
- List the main changes and any setup steps.
- Keep PRs small and reviewable.

## Issues and tasks
- Create GitHub issues for new frontend or backend work.
- Tag issues with labels such as `frontend`, `backend`, `design`, or `documentation`.
- Link issues to design handoff notes in `DESIGN_HANDOFF.md` when relevant.

## Frontend handoff notes
- The first frontend developer should begin with the app shell, main routes, and design-based page scaffolding.
- Use `Next.js App Router`, `Tailwind CSS`, and `shadcn/ui`.
- Keep UI implementation separate from API wiring until backend endpoints exist.

## Design sharing
- Add design links, exports, and component notes to `DESIGN_HANDOFF.md`.
- Prefer shareable design URLs over embedding large assets in PR descriptions.

## Communication
- Use PR comments for implementation questions.
- Ask the project owner if the Claude Design file or routes need clarification.
