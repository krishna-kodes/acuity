# Contributing to Acuity

## Branch strategy

```
main   ← protected; production-ready code only
dev    ← integration branch; all PRs merge here first

epic/0-design-system       (krishna-kodes)
epic/1-frontend-scaffold   (krishna-kodes)
epic/2-frontend-pages      (krishna-kodes)
epic/3-frontend-polish     (krishna-kodes)
epic/4-api-contracts       (krishna-augment)
epic/5-backend-impl        (krishna-augment)
epic/6-integration         (both)
```

- One branch per epic, not per task. All tasks for an epic commit directly to that epic branch.
- Branch from `dev`. PR back to `dev` when the epic's definition of done is met.
- `dev` → `main` merges happen at integration milestones (end of Epic 3, end of Epic 6).
- Branch names must match the pattern above exactly — CI and PR templates reference them.

## Workflow

1. Branch from `dev`: `git checkout dev && git pull && git checkout -b epic/<n>-<name>`
2. Commit often within the epic branch; keep commit messages descriptive.
3. Open a PR to `dev` when the epic is complete and all checks pass.
4. Request review from the other developer before merging.
5. Delete the epic branch after merge.

## Epic dependencies and parallel work

The epic order is sequential by default, but `krishna-augment` can start backend work early:

```
Epic 0  krishna-kodes   design system + scaffold
Epic 1  krishna-kodes   frontend scaffolding
  │
  ├── Epic 4 T1–T3  krishna-augment  ← can start in parallel with Epic 0/1
  │   (define contracts, scaffold FastAPI, add stubs — API surface is in CLAUDE.md)
  │
Epic 2  krishna-kodes   frontend pages
  │
  ├── Epic 4 T4–T5  krishna-augment  ← needs frontend routes to exist
  │   (OpenAPI docs, fetch wrapper)
  │
Epic 3  krishna-kodes   frontend polish
Epic 5  krishna-augment backend implementation
Epic 6  both            integration + QA
```

**Rule:** `krishna-augment` may open `epic/4-api-contracts` and work on issues #30–32 as soon as Epic 0 begins. Issues #33–34 must wait until Epic 1 is merged to `dev`.

## Pull request guidelines

- Title: `[Epic N] Short description of what the epic delivers`
- Body: use the PR template (`.github/pull_request_template.md`)
- Reference all epic issues in the PR body: `Closes #30, #31, #32`
- Keep PRs scoped to one epic — do not bundle multiple epics into one PR
- All checks (type check, lint) must pass before requesting review

## Issues and tasks

- Each task maps to a GitHub issue tagged with its epic milestone
- Issue naming: `[En-Tx] Description` (e.g. `[E0-T1] Extract design tokens`)
- Label issues `frontend`, `backend`, or `integration`
- Move an issue to `In Progress` when you start it; close it when the commit is on the epic branch

## Code conventions

- **Frontend:** TypeScript, Next.js App Router, Tailwind CSS, shadcn/ui — see `CLAUDE.md`
- **Backend:** FastAPI, all routes prefixed `/api/v1/` — see `CLAUDE.md`
- No `console.log` in committed code
- Run `npx tsc --noEmit` and `npm run lint` before pushing frontend changes
- Run `pytest` before pushing backend changes
