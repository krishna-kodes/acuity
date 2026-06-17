# Auth, RBAC & Multi-User Design Document

**Project:** AI-Driven Project Management Tool (Acuity)
**Status:** Planned — post-MVP. Tracks the authentication, authorization, and multi-tenancy work layered on top of the single-user MVP.
**Last updated:** 2026-06-13

> **Scope.** This document specifies how Acuity moves from its current single-user, no-auth MVP to a multi-user system with authentication, role-based access control (RBAC), and per-user tenancy. Where it conflicts with the v2 design doc, **this document wins** for the features it covers. Related backlog item: CLAUDE.md §14 "Multi-user support with RBAC".

---

## 1. Motivation

The MVP has **zero authentication and zero ownership**. Every project-scoped route depends only on `get_db` — no `current_user`, no owner column on `Project`. Any caller can read or mutate any project. This is acceptable for a single-PM capstone demo but blocks any shared or hosted deployment.

This document closes the **identity → authorization → isolation** gap so multiple PMs can use one Acuity instance without seeing or corrupting each other's work.

---

## 2. Current State (what exists today)

| Concern | Current state |
|---------|---------------|
| Authentication | None. No `users` table, no login, no token. |
| Project ownership | None. `Project` has no `owner_id`. |
| Route protection | None. All routes use bare `Depends(get_db)` (~30 call sites in `app/routers/projects.py`). |
| App DB concurrency | SQLite WAL, `check_same_thread=False`. Single writer; concurrent reads OK. |
| Workflow concurrency | One global compiled graph + one shared `_aiosqlite_conn` (`workflow.py:981`). Per-project isolation via `thread_id = project_id`. Writes serialize through the single connection. |
| GitHub credentials | Single global `GITHUB_TOKEN` / `GITHUB_OWNER` / `GITHUB_REPO` in `.env`. All syncs use one identity to one repo. |

---

## 3. What Breaks Under Multi-User

1. **No tenancy.** `GET /projects/{id}` has no owner check — User B reads User A's document, proposal, and metrics.
2. **SQLite write contention.** `app.db` is single-writer. WAL allows concurrent reads but writes serialize. Fine for a small cohort (~dozens of users); not for hundreds.
3. **Workflow checkpoint funnel.** All users' phase-runs pass through one global `_aiosqlite_conn` and one singleton graph. No state-bleed (thread_id isolation holds), but a throughput ceiling.
4. **Global GitHub credentials.** All users sync to the *same* repo as the *same* identity. Multi-user requires per-user or per-project credentials.
5. **Same-project race.** Two users acting on one shared project can both call `run_phase` concurrently → last-write-wins on `aupdate_state`. No guard exists.

---

## 4. Target Design

### 4.1 Schema changes

```sql
users (
  id            INTEGER PRIMARY KEY,
  email         VARCHAR UNIQUE NOT NULL,
  hashed_password VARCHAR NOT NULL,
  role          VARCHAR NOT NULL DEFAULT 'pm',  -- 'admin' | 'pm' | 'viewer'
  created_at    DATETIME NOT NULL
)

-- new column on existing table
projects.owner_id  INTEGER  FK -> users.id
```

- Alembic migration adds `users` table + `projects.owner_id`.
- Backfill: assign all existing `projects` rows to a seeded default owner (e.g. admin user) so the non-null constraint is safe.

### 4.2 Authentication layer

- JWT bearer tokens. Use `fastapi-users` or a hand-rolled `OAuth2PasswordBearer` + `python-jose` + `passlib[bcrypt]`.
- New dependency `get_current_user` resolves the bearer token → `User`.
- Inject alongside `get_db` on every protected route: `user: User = Depends(get_current_user)`.
- New routes: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`. All under the existing `/api/v1/` prefix (non-negotiable rule #4).

### 4.3 RBAC enforcement — two layers

**Role gate** (coarse): a `require_role("pm")` dependency rejects `viewer` from mutating endpoints (`POST /epics`, `/sync`, `/clarifications`, `/proposal`, etc.).

| Role | Permissions |
|------|-------------|
| `admin` | All projects, all actions, user management. |
| `pm` | CRUD on own projects; run all phases; sync. |
| `viewer` | Read-only on projects shared with them. |

**Row ownership** (fine — the real protection): a `get_project_or_404(id, user, db)` helper replaces raw `db.get(Project, id)` at every project-scoped route. It filters:

```python
WHERE projects.id == :id
  AND (projects.owner_id == :user_id OR :user_role == 'admin')
```

Role alone is insufficient — without the ownership filter a `pm` could still read another `pm`'s project. Ownership check is mandatory on every project route.

### 4.4 Concurrency under load

- Per-project isolation (thread_id) is already correct → parallel runs across *distinct* projects are safe.
- Bottleneck = SQLite writes + single checkpoint connection. Path:
  - **Short term:** keep WAL, accept write serialization. Holds for a small cohort.
  - **Real fix:** migrate `app.db` and `project_state.db` to **Postgres**. LangGraph ships `AsyncPostgresSaver` — drop-in for `AsyncSqliteSaver`. Removes the single-writer ceiling and gives true concurrent checkpoint writes.
- **Per-project run lock:** within one shared project, concurrent `run_phase` calls race. Add an advisory lock keyed by `project_id` (or a `projects.lock_status` guard row) so two users cannot double-run a phase. Required once a project can have >1 user (viewer + pm, or shared pm).

### 4.5 GitHub multi-tenancy

- Move credentials out of global `.env` → per-user OAuth token or a per-project config row.
- Encrypt stored tokens with the existing Fernet key (`PII_ENCRYPTION_KEY`) — reuse the PII encryption pattern already in the codebase (non-negotiable rule #7).

---

## 5. Implementation Order (minimal viable path)

1. `users` table + `projects.owner_id` (Alembic migration + default-owner backfill).
2. JWT auth: `get_current_user`, register/login/me routes, password hashing.
3. `get_project_or_404(id, user, db)` ownership-filter helper; swap in at all project routes.
4. `require_role` gate on mutating endpoints.
5. Per-project run lock in `run_phase`.
6. Defer Postgres migration until load demands it — SQLite WAL holds for a small cohort.
7. Per-project/per-user GitHub credentials (Fernet-encrypted) — deferrable until shared-repo conflict is real.

---

## 6. Open Questions

| Item | Status |
|------|--------|
| Project sharing model — single owner vs. collaborator list | Open. MVP-of-this: single `owner_id`. Collaborators need a join table. |
| `viewer` role — read access scope (which projects shared) | Open — depends on sharing model. |
| Postgres migration trigger — what load threshold | Open. Defer until measured contention. |
| GitHub identity — per-user OAuth vs per-project token | Open. Per-project token simplest; per-user OAuth cleaner. |
| Session/token lifetime + refresh strategy | Open. |
