# Team Selection & Resourcing — Improvements Design Document

**Project:** AI-Driven Project Management Tool (Acuity)
**Status:** Living document — tracks improvements to Phase 4 (Team Suggestion) and the employee/resource data layer
**Last updated:** 2026-06-13
**Related:** `improvements_design_document.md` (SDLC loop), `CLAUDE.md` (Phase 4), `capstone_project_design_document_v2.md`

> **Scope.** This document covers two things: (1) functional improvements to the Team Suggestion phase, and (2) the architecture for replacing the locally-seeded employee database with a real company source (HRIS / data warehouse). It does not duplicate the SDLC-loop features tracked in `improvements_design_document.md`.

---

## 1. Current State

### 1.1 How Team Suggestion works today

Phase 4 (`_phase_4_team_node` in `backend/app/services/workflow.py:619`) runs as a **direct DB query**, not an LLM agent (the prior LLM-agent approach was removed — it failed when the tech stack was empty and the message extraction was fragile).

Flow:

1. Read `state["tech_stack"]` — flatten `frontend + backend + database + infra` lists into tech names (regex strips `" (category): tags"` suffixes).
2. `get_employees(skills)` (`workflow.py:148`) — `SELECT … FROM employees JOIN employee_skills JOIN skills WHERE skills.name IN (:skills)`.
3. Score each candidate: `match_score = |employee_skills ∩ required_techs| / |required_techs|`.
4. Annotate `active_projects_count` (count of non-complete projects whose `team_suggestion.members` include this employee).
5. Sort by `match_score` desc; persist to `project.team_suggestion`.

Frontend (`frontend/app/(app)/projects/[id]/team/page.tsx`):

- Candidate cards with checkbox multi-select (`selected` Set) + a separate manual-add list (`manualAdds`).
- Search by **name or skill** over all employees (`listAdminEmployees`).
- Client-side multi-key sort (match / availability / active projects).
- `effectiveAvailability = max(0, availability_pct − active_projects_count × 20)` — computed **client-side only**, with a hardcoded `20`.

### 1.2 Employee data access surface

Employee data is touched in only four places — a small, cleanly-refactorable surface:

| Site | File:line | Use |
|------|-----------|-----|
| Admin list | `backend/app/routers/admin.py:38` | `GET /employees` — powers frontend search |
| Phase 4 tool | `backend/app/services/workflow.py:148` | `get_employees(skills)` |
| Phase 4 fallback | `backend/app/services/workflow.py:650` | all-employees when no tech stack |
| `suggest_team_direct` fallback | `backend/app/services/workflow.py:735` | same, non-LangGraph path |
| Seeder | `backend/app/services/seeder.py:219` | Faker seed data |

### 1.3 Data model

`backend/app/models/employee.py`:

- `Employee(id, name, email, seniority, availability_pct, joined_at, status)`
- `Skill(id, name UNIQUE, category)`
- `EmployeeSkill(employee_id, skill_id)` — bare join table, **no proficiency level**.

---

## 2. Functional Improvements (Phase 4 logic)

Ranked by value.

### IMP-T1 — Requirements/scope drives role mix & headcount  *(highest value)*

**Problem.** Phase 4 considers the **tech stack only**. The requirements document, proposal sections, TBDs, and effort estimate never reach it. The tool returns *every* employee with any matching skill, ranked — it never says "this project needs ~5 people: 2 backend, 1 frontend, 1 DevOps, 1 QA." The PM selects blind against no target.

**Fix.** Derive a target team composition from the proposal + effort estimate:

- Use the effort estimate (story points / duration) + proposal scope to recommend headcount and a role breakdown.
- Surface "target vs selected" in the UI (e.g. "Backend: 1/2 selected").
- Keep it advisory — PM still confirms manually.

**Touches:** `workflow.py` Phase 4 node (pass proposal + estimate into the node), new role-target helper, `team/page.tsx` (target panel).

### IMP-T2 — Fairer `match_score` (per-category weighting)

**Problem.** `match_score` divides by **all** required techs across every category. A backend specialist on a frontend-heavy project scores low even though they are exactly right for the backend work.

**Fix.** Score per category (use `Skill.category`, currently unused for matching) and weight by how much of the stack falls in each category, or score a candidate against their relevant category only.

### IMP-T3 — Apply availability filtering/scoring in the backend

**Problem.** `CLAUDE.md` lists an "availability filter" for Phase 4, but the backend applies none — employees at 0% availability are still returned. `effectiveAvailability` lives only in the frontend with a magic `× 20`, not persisted, not used in ranking.

**Fix.** Move effective-availability into the backend; factor it into ranking; expose the per-project load weighting as config instead of a hardcoded `20`. Optionally filter out fully-unavailable staff (or flag them).

### IMP-T4 — Factor seniority into ranking

**Problem.** `seniority` is stored and displayed but never weighted. A senior and a junior with identical skill overlap rank identically.

**Fix.** Add a seniority weight to the score (and/or let the role target in IMP-T1 request seniority mix, e.g. "1 senior backend").

### IMP-T5 — Robust skill matching (alias / normalization)

**Problem.** `get_employees` uses exact equality (`Skill.name.in_(skills)`). Tech names extracted from the tech stack must exactly equal DB skill names. `"React.js"` / `"ReactJS"` vs `"React"`, `"Postgres"` vs `"PostgreSQL"` → silent misses.

**Fix.** Introduce a skill-alias / normalization table applied at match time (and at sync time — see §3). Normalize both sides to a canonical form before comparison.

### IMP-T6 — Skill proficiency model

**Problem.** `EmployeeSkill` is a bare join — "knows React" cannot distinguish expert from touched-once.

**Fix.** Add `proficiency` (e.g. 1–5 or enum) to `EmployeeSkill`; weight `match_score` by proficiency. Requires migration + seed update + a real source for the value (§3.3).

### IMP-T7 — Bulk multi-add in the search dropdown

**Problem.** Manual add is one-at-a-time (dropdown capped at 8, click "Add" each).

**Fix.** Allow multi-select in the search results and an "Add selected" action. Small UI change.

---

## 3. Architecture: Real Company Database

### 3.1 Principle

Employee data is **reference data the app does not own.** In production it lives in an HRIS (Workday / BambooHR / SAP SuccessFactors), an identity provider (AD / Okta), and/or a data warehouse. The app must be a **read-only consumer** and never the source of truth. This mirrors the existing `VectorStoreAdapter` guidance in `CLAUDE.md` (treat the store as swappable) and the `SYNC_PROVIDER` factory pattern.

### 3.2 Repository seam (do this first — non-breaking)

Collapse the four access sites (§1.2) behind one interface, selected by env var (same playbook as `SYNC_PROVIDER` → `sync_factory.py`):

```python
class EmployeeRepository(Protocol):
    def list_all(self) -> list[EmployeeDTO]: ...
    def find_by_skills(self, skills: list[str]) -> list[EmployeeDTO]: ...

# implementations
class SqliteEmployeeRepo(EmployeeRepository): ...     # today: seeded local
class HrisEmployeeRepo(EmployeeRepository): ...        # live HRIS API
class WarehouseEmployeeRepo(EmployeeRepository): ...   # read replica / Snowflake
```

Selected via `EMPLOYEE_SOURCE=sqlite|hris|warehouse`. Replace raw `db.query(Employee)` in `workflow.py` and `admin.py` with `repo.find_by_skills(...)` / `repo.list_all()`. No behavior change for the default `sqlite` path; tests/evals stay green.

```
Phase 4 node ─┐
admin router ─┼─→ EmployeeRepository ─┬─ SqliteEmployeeRepo (seeded — dev/eval)
              │                       ├─ HrisEmployeeRepo  (live API)
              │                       └─ WarehouseEmployeeRepo (mirror)
```

### 3.3 Integration mode: live API vs sync/mirror

| Mode | How | When |
|------|-----|------|
| **Live API** | `HrisEmployeeRepo` calls the HRIS REST API per query | Small org, low call volume, freshness critical |
| **Sync / mirror** *(recommended)* | Scheduled job pulls HRIS → upserts the local `employees`/`skills` tables → app keeps reading the local DB | Real systems — decouples HRIS uptime/rate-limits from the app |

**Recommend sync/mirror.** HRIS APIs are slow, rate-limited, and have downtime; Phase 4 issues many skill queries and needs joins/filtering the HRIS does not expose. Keep the local DB as a refreshed cache (e.g. nightly). The seeded SQLite stays the dev/eval fixture forever.

### 3.4 The hard parts (the mapping, not the swap)

1. **Skill taxonomy — the real problem.** Seeded skills are clean canonical strings. Real HRIS skill data is free-text, inconsistent, or **absent** (most HRIS do not track granular tech skills). This breaks `match_score` worse than the exact-match issue (IMP-T5). Options: map job titles/roles → skill sets; pull skills from a system that actually has them (skills matrix, Lattice/competency tool, GitHub/Jira activity); normalize via the alias table at sync time.
2. **Stable identity.** Local autoincrement `id` will not survive. Add `external_id` (HRIS employee ID) as the stable upsert key.
3. **Availability source.** `availability_pct` is faked. Real availability lives in a resource-management / PSA tool (Float, Kantata, Tempo), not the HRIS — a separate integration, or stays PM-entered.
4. **PII + auth.** Real names/emails bring the resource pool into scope for the PII layer and access control. HRIS credentials go in a secrets manager, never committed `.env`. Audit who may read the pool.
5. **Read-only.** Never write back to the HRIS. Guard/disable the seed factory in production (extend the existing `EXPOSE_FACTORY_IN_DOCS` flag).

### 3.5 Migration path

1. Add `EmployeeRepository` + `SqliteEmployeeRepo` wrapping current queries. No behavior change.
2. Add `external_id` + skill-alias table (+ `proficiency` if doing IMP-T6).
3. Build `HrisSyncService` — one connector (e.g. BambooHR) → upsert mirror, scheduled.
4. Flip `EMPLOYEE_SOURCE` in prod; keep `sqlite` + seed for dev/evals.

---

## 4. Suggested Sequencing

| Order | Item | Why first |
|-------|------|-----------|
| 1 | §3.2 Repository seam | Non-breaking; unlocks everything else; cleanest while surface is small |
| 2 | IMP-T5 + IMP-T1 | Skill matching robustness + requirements-driven role mix — biggest functional gaps |
| 3 | IMP-T2, IMP-T3, IMP-T4 | Scoring quality (category weighting, availability, seniority) |
| 4 | §3.3–3.5 HRIS sync | The production integration once the seam exists |
| 5 | IMP-T6, IMP-T7 | Proficiency model + bulk-add UX |

---

## 5. Open Questions

- Which HRIS is the real target (Workday / BambooHR / other)? Determines the first connector.
- Is there an existing skills matrix, or must skills be inferred from roles/activity?
- Where does real availability come from — a PSA tool, or PM-entered?
- Proficiency scale: numeric 1–5 or enum (none/working/expert)?
