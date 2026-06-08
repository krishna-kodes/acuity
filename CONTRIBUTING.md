# Contributing to Acuity

## Team

| Dev | GitHub | Owns |
|-----|--------|------|
| Krishna | [@krishna-kodes](https://github.com/krishna-kodes) | Frontend (Epics 0–3) |
| Augment | [@krishna-augment](https://github.com/krishna-augment) | Backend (Epics 4–5) |
| Both | — | Integration (Epic 6) |

**Project board:** https://github.com/users/krishna-kodes/projects/1

---

## Branch strategy

- `main` — always shippable; direct pushes blocked
- One branch per task, merged before the next begins: `feat/<slug>` or `feat/epic{N}-task{N}-{slug}`
- Examples: `feat/modules-backend`, `feat/epic5-task2-chromadb-ingestion`
- No long-lived branches — tasks should be ≤ 2 days of work
- Sequential: backend branch → PR → merge → frontend branch → PR → merge

---

## Pre-task checklist

Before writing any code:

- [ ] **Correct versions?** Run `python3 --version` (expect 3.11.14) and `node --version` (expect 22.17.0). Use `pyenv` and `nvm` — both read the pinned files (`.python-version`, `.nvmrc`).
- [ ] **Dependency merged?** Confirm the blocking epic's issues are merged to `main` (see dependency map below). If not, add `blocked` label and wait.
- [ ] **Pull latest main** and create your branch:
  ```bash
  git checkout main && git pull origin main
  git checkout -b feat/epic{N}-task{N}-{slug}
  ```
- [ ] **Assign yourself** to the GitHub issue if not already assigned
- [ ] **Move the card** → `In Progress` on the [project board](https://github.com/users/krishna-kodes/projects/1)
- [ ] **Check for conflicts** with any open PRs touching the same files
- [ ] **Sync point check:** Before starting Epic 4 T4–T5 (#33–34) or Epic 6 (#41–45), confirm verbally with the other dev that the blocking epic is stable — don't rely on GitHub alone

---

## Post-task checklist

When your task is complete:

- [ ] **Self-review your diff** — read every line before opening a PR
- [ ] **Run type check and lint**
  - Frontend: `npx tsc --noEmit && npm run lint`
  - Backend: `ruff check . && mypy . && pytest`
- [ ] **Open a PR** targeting `main`
  - Title: `[E{N}-T{N}] Short description`
  - Body must include `Closes #<issue-number>`
  - Describe what changed and any setup steps needed
- [ ] **Move the card** → `In Review` on the project board
- [ ] **Request review** from the other dev
- [ ] **After merge:** pull latest `main` and delete your branch
  ```bash
  git checkout main && git pull origin main
  git branch -d feat/epic{N}-task{N}-{slug}
  ```

---

## Epic dependencies and parallel work

```
Epic 0  krishna-kodes   design system + component library
Epic 1  krishna-kodes   frontend scaffolding
  │
  ├── Epic 4 T1–T3  krishna-augment  ← can start in parallel with Epic 0/1
  │   (API contracts, FastAPI scaffold, stub responses — surface is in CLAUDE.md)
  │
Epic 2  krishna-kodes   frontend pages
  │
  ├── Epic 4 T4–T5  krishna-augment  ← needs Epic 1 routes (#13 merged)
  │   (OpenAPI docs, fetch wrapper)
  │
Epic 3  krishna-kodes   frontend polish
Epic 5  krishna-augment backend implementation
Epic 6  both            integration + QA
```

| Epic | Blocked until |
|------|--------------|
| Epic 1 | Epic 0 merged |
| Epic 2 | Epic 1 merged |
| Epic 3 | Epic 2 merged |
| Epic 4 T1–T3 | Epic 0 started (can run in parallel) |
| Epic 4 T4–T5 | Epic 1 merged (#13) |
| Epic 5 | Epic 4 merged |
| Epic 6 | Epics 3 + 5 merged |

---

## Pull request guidelines

- Scope to one task — no bundling multiple issues
- Squash merge to keep `main` history clean
- Reviewer approves → author merges (not reviewer)
- PRs open > 24 hours without review: ping in PR comments
- Use the PR template (`.github/pull_request_template.md`)

---

## Issues and labels

| Label | Meaning |
|-------|---------|
| `frontend` | Dev A work |
| `backend` | Dev B work |
| `integration` | Both devs |
| `in-progress` | Actively being worked on |
| `blocked` | Waiting on dependency |

Issue naming: `[En-Tx] Description` — e.g. `[E0-T1] Extract design tokens`
Move issue → `In Progress` when you start; it auto-closes on PR merge via `Closes #XX`.

---

## Code conventions

- **Frontend:** TypeScript, Next.js App Router, Tailwind CSS, shadcn/ui — see `CLAUDE.md`
- **Backend:** FastAPI, all routes prefixed `/api/v1/` — see `CLAUDE.md`
- No `console.log` in committed code
- No hardcoded provider names (`google`, `anthropic`) — always use env vars

---

## Design and API references

- Design file: https://claude.ai/design/p/01159eb0-0c4b-4129-9342-c1bfa04efae0
- API contract: `/docs` (FastAPI OpenAPI) — source of truth for frontend ↔ backend contract
- Design tokens and handoff notes: `DESIGN_HANDOFF.md`
- Architecture decisions: `CLAUDE.md` §4

---

## Communication

- Implementation questions → PR comments on the relevant issue
- Contract disagreements → comment on Epic 4 API contract issue (#30)
- Blockers → add `blocked` label and tag the other dev in the issue
