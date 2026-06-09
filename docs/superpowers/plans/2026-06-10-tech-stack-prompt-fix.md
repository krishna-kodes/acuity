# Tech Stack Prompt Strictness + Approved Technology Tags Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the LLM hallucinating unapproved technologies by tightening the prompt constraint, add rich use-case/scale tags to approved technologies so the LLM can make project-appropriate choices, backfill existing DB records via seeder upsert, fix silent exception swallowing, and remove a misleading hardcoded UI badge.

**Architecture:** Four targeted file edits, no schema changes. Seeder becomes an upsert so re-running `POST /factory/seed-technologies` backfills tags on existing records. The same prompt string change applies to both the LangGraph node and the streaming router endpoint. Error logging is added to the previously silent except block.

**Tech Stack:** Python/FastAPI backend, SQLAlchemy ORM, pytest, Next.js/TypeScript frontend.

---

## File Map

| File | Change |
|------|--------|
| `backend/app/services/seeder.py` | `_APPROVED_TECHS` → 3-tuples with tags; `seed_technologies` → upsert (update tags if name exists) |
| `backend/app/services/workflow.py` | Stricter prompt in `_phase_3_stack_node`; `except Exception: pass` → `record_error` + set phase complete |
| `backend/app/routers/projects.py` | Stricter prompt in `suggest_stack_stream` |
| `frontend/app/(app)/projects/[id]/techstack/page.tsx` | Replace hardcoded `"All approved ✓"` badge with neutral count string |
| `backend/tests/test_e5t6.py` | Add test: second seed run backfills tags on existing records |
| `backend/tests/test_workflow.py` | Update phase_3 status assertion from `"in_progress"` to `"complete"` (fallback path now sets complete) |

---

## Task 1: Seeder — rich tags + upsert

**Files:**
- Modify: `backend/app/services/seeder.py`
- Modify: `backend/tests/test_e5t6.py`

### Context

`_APPROVED_TECHS` is currently a list of 2-tuples `(name, category)`. All 22 `ApprovedTechnology` records in the DB have `tags = NULL`. `seed_technologies` skips existing records (`if exists: continue`), so calling it again won't backfill tags.

- [ ] **Step 1: Write a failing test for upsert tag backfill**

Add to `backend/tests/test_e5t6.py` after the existing `test_seed_technologies_returns_count`:

```python
def test_seed_technologies_backfills_tags_on_second_run(client, db_session):
    from app.models.reference import ApprovedTechnology

    # First run: inserts records (tags may be empty for legacy data — simulate by clearing)
    client.post("/api/v1/factory/seed-technologies")
    # Wipe tags to simulate pre-existing tag-less records
    db_session.query(ApprovedTechnology).update({"tags": None})
    db_session.commit()

    # Second run: should upsert and restore tags
    resp = client.post("/api/v1/factory/seed-technologies")
    assert resp.status_code == 200

    next_js = db_session.query(ApprovedTechnology).filter_by(name="Next.js").first()
    assert next_js is not None
    assert next_js.tags is not None
    assert "SPA" in next_js.tags

    sqlite = db_session.query(ApprovedTechnology).filter_by(name="SQLite").first()
    assert sqlite is not None
    assert "prototyping" in sqlite.tags

    postgres = db_session.query(ApprovedTechnology).filter_by(name="PostgreSQL").first()
    assert postgres is not None
    assert "high-scale" in postgres.tags
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd backend && source .venv/bin/activate
pytest tests/test_e5t6.py::test_seed_technologies_backfills_tags_on_second_run -v
```

Expected: FAIL — `AssertionError` because `next_js.tags` is `None` (seeder skips existing records).

- [ ] **Step 3: Update `_APPROVED_TECHS` to 3-tuples and `seed_technologies` to upsert**

Replace the entire `_APPROVED_TECHS` list and `seed_technologies` function in `backend/app/services/seeder.py`:

```python
_APPROVED_TECHS = [
    # (name, category, tags)
    ("Next.js",       "frontend", "SPA,SSR,TypeScript-first,prototyping,production"),
    ("React",         "frontend", "SPA,component-library,flexible,prototyping,production"),
    ("Vue.js",        "frontend", "SPA,lightweight,progressive,prototyping"),
    ("TypeScript",    "frontend", "typed,compile-time-safety,large-team"),
    ("Tailwind CSS",  "frontend", "utility-CSS,rapid-prototyping,design-system"),
    ("FastAPI",       "backend",  "REST,async,Python,ML-friendly,prototyping,production"),
    ("Django",        "backend",  "REST,batteries-included,ORM,Python,high-scale"),
    ("Node.js",       "backend",  "REST,event-driven,JavaScript,high-scale"),
    ("Go",            "backend",  "REST,high-performance,compiled,high-scale"),
    ("Rust",          "backend",  "systems,high-performance,compiled,high-scale"),
    ("PostgreSQL",    "database", "relational,ACID,production,high-scale"),
    ("SQLite",        "database", "relational,embedded,prototyping,low-scale"),
    ("MongoDB",       "database", "NoSQL,flexible-schema,document-store,high-scale"),
    ("Redis",         "database", "cache,pub-sub,session-store,high-scale"),
    ("Elasticsearch", "database", "search,full-text,analytics,high-scale"),
    ("Docker",        "infra",    "containerization,local-dev,portable"),
    ("Kubernetes",    "infra",    "orchestration,high-scale,complex-ops,production"),
    ("Railway",       "infra",    "PaaS,simple-deploy,low-ops,prototyping"),
    ("AWS Lambda",    "infra",    "serverless,event-driven,high-scale,pay-per-use"),
    ("Terraform",     "infra",    "IaC,cloud-provisioning,production"),
    ("LangChain",     "ai",       "LLM-orchestration,RAG,agents,Python"),
    ("ChromaDB",      "ai",       "vector-store,embeddings,RAG,local-dev"),
]
```

Replace `seed_technologies`:

```python
def seed_technologies(db: Session, count: int | None = None) -> int:
    if count is None:
        count = settings.seed_technology_count
    seeded = 0
    for name, category, tags in _APPROVED_TECHS[:count]:
        existing = db.query(ApprovedTechnology).filter(ApprovedTechnology.name == name).first()
        if existing:
            existing.tags = tags
        else:
            db.add(ApprovedTechnology(name=name, category=category, tags=tags))
        seeded += 1
    db.commit()
    return seeded
```

- [ ] **Step 4: Run all seeder tests**

```bash
pytest tests/test_e5t6.py -v
```

Expected: All pass. Verify these specific tests pass:
- `test_seed_technologies_returns_count` — still expects `seeded == 22` ✓ (upsert always increments)
- `test_seed_technologies_backfills_tags_on_second_run` — now passes
- `test_seed_all_total` — still expects 22 `ApprovedTechnology` records ✓

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/seeder.py backend/tests/test_e5t6.py
git commit -m "feat(seeder): add rich use-case tags to approved techs, upsert on re-seed"
```

---

## Task 2: workflow.py — stricter prompt + error logging

**Files:**
- Modify: `backend/app/services/workflow.py`
- Modify: `backend/tests/test_workflow.py`

### Context

`_phase_3_stack_node` at line ~499 has two problems:
1. Prompt uses weak "Select the most appropriate" wording — LLM ignores the constraint
2. `except Exception: pass` silently returns `_FALLBACK_STACK` with no log, and leaves `ps["phase_3"]` as `"in_progress"` instead of setting it to `"complete"`

The existing test `test_phase_3_stack_node_returns_tech_stack` asserts `phase_status["phase_3"] == "in_progress"` — this is actually testing the fallback path (LLM fails in test env with no API key). After our fix, the fallback path will set `phase_3 = "complete"`, so the test needs updating.

- [ ] **Step 1: Update the existing phase_3 test to assert "complete"**

In `backend/tests/test_workflow.py`, find `test_phase_3_stack_node_returns_tech_stack` and change the assertion:

```python
@pytest.mark.asyncio
async def test_phase_3_stack_node_returns_tech_stack():
    state: ProjectState = {
        **_EMPTY_STATE,
        "phase_status": {"phase_1": "complete", "phase_2": "complete"},
    }
    result = await _phase_3_stack_node(state)
    assert "tech_stack" in result
    assert "frontend" in result["tech_stack"]
    assert result["phase_status"]["phase_3"] == "complete"
```

- [ ] **Step 2: Add a test for error logging on LLM failure**

Add after the existing phase_3 tests in `backend/tests/test_workflow.py`:

```python
@pytest.mark.asyncio
async def test_phase_3_stack_node_logs_error_on_llm_failure(db_session):
    from unittest.mock import patch
    from app.models.observability import ErrorLog
    from app.database import SessionLocal

    state: ProjectState = {
        **_EMPTY_STATE,
        "phase_status": {"phase_1": "complete", "phase_2": "complete"},
    }

    with patch("app.services.workflow.get_llm") as mock_llm:
        mock_llm.return_value.with_structured_output.side_effect = RuntimeError("API key invalid")
        result = await _phase_3_stack_node(state)

    # Fallback stack returned
    assert result["tech_stack"]["frontend"] == ["Next.js"]
    assert result["phase_status"]["phase_3"] == "complete"

    # Error logged to DB
    db = SessionLocal()
    try:
        log = db.query(ErrorLog).filter_by(
            project_id=int(state["project_id"]), phase="phase_3"
        ).first()
        assert log is not None
        assert log.error_type == "RuntimeError"
    finally:
        db.close()
```

- [ ] **Step 3: Run both tests to confirm they fail**

```bash
pytest tests/test_workflow.py::test_phase_3_stack_node_returns_tech_stack tests/test_workflow.py::test_phase_3_stack_node_logs_error_on_llm_failure -v
```

Expected:
- `test_phase_3_stack_node_returns_tech_stack`: FAIL — asserts `"complete"` but gets `"in_progress"`
- `test_phase_3_stack_node_logs_error_on_llm_failure`: FAIL — no `ErrorLog` row created

- [ ] **Step 4: Apply prompt fix + error logging to `_phase_3_stack_node`**

In `backend/app/services/workflow.py`, find the `_llm_raw.invoke(...)` call (around line 503) and replace the prompt string and the except block:

```python
        _raw_result = _llm_raw.invoke(
            f"Given this project proposal:\n{proposal_summary}\n\n"
            "Select technologies ONLY from the approved list below. "
            "Do not suggest any technology not present in this list. Use EXACT names as written.\n\n"
            f"{tech_descriptions}\n\n"
            "Choose 1-3 per category (frontend, backend, database, infra). "
            "Use the tags to match project needs — e.g. prefer 'prototyping' tags for MVPs, "
            "'high-scale' for enterprise. Return your selections and a brief rationale "
            "explaining why each choice fits this project."
        )
```

Replace the except block (currently `except Exception:\n    tech_stack = _FALLBACK_STACK`):

```python
    except Exception as exc:
        record_error(int(state["project_id"]), "phase_3", type(exc).__name__, str(exc))
        tech_stack = _FALLBACK_STACK
        ps["phase_3"] = "complete"
```

- [ ] **Step 5: Run updated tests**

```bash
pytest tests/test_workflow.py::test_phase_3_stack_node_returns_tech_stack tests/test_workflow.py::test_phase_3_stack_node_logs_error_on_llm_failure -v
```

Expected: Both PASS.

- [ ] **Step 6: Run full workflow test suite**

```bash
pytest tests/test_workflow.py -v
```

Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/workflow.py backend/tests/test_workflow.py
git commit -m "fix(phase3): strict approved-list prompt, log errors instead of silent fallback"
```

---

## Task 3: projects.py — stricter prompt in streaming endpoint

**Files:**
- Modify: `backend/app/routers/projects.py`

### Context

`suggest_stack_stream` (around line 1574) has its own copy of the prompt with the same weak wording. It also asks the LLM to return raw JSON (not structured output), so the constraint must be especially clear.

- [ ] **Step 1: Replace the prompt in `suggest_stack_stream`**

In `backend/app/routers/projects.py`, find the `prompt = (...)` block starting at line ~1574 and replace it:

```python
    prompt = (
        f"Given this project proposal:\n{proposal_summary}\n\n"
        "Select technologies ONLY from the approved list below. "
        "Do not suggest any technology not present in this list. Use EXACT names as written.\n\n"
        f"{tech_descriptions}\n\n"
        "Choose 1-3 per category (frontend, backend, database, infra). "
        "Use the tags to match project needs — e.g. prefer 'prototyping' tags for MVPs, "
        "'high-scale' for enterprise. "
        "Respond ONLY with valid JSON (no markdown, no explanation outside the JSON):\n"
        '{"frontend": [...], "backend": [...], "database": [...], "infra": [...], "rationale": "..."}'
    )
```

- [ ] **Step 2: Run existing stack stream tests**

```bash
pytest tests/test_routes.py::test_stack_stream_returns_event_stream_cached tests/test_routes.py::test_stack_stream_returns_409_when_modules_not_done -v
```

Expected: Both pass (these test caching/gating logic, not prompt content).

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/projects.py
git commit -m "fix(phase3): strict approved-list prompt in stack stream endpoint"
```

---

## Task 4: Frontend — remove misleading "All approved ✓" badge

**Files:**
- Modify: `frontend/app/(app)/projects/[id]/techstack/page.tsx`

### Context

The table header in `techstack/page.tsx` (around line 233–237) shows:

```tsx
<span className="text-xs font-semibold text-text-muted uppercase tracking-wide">
  {items.length} technolog{items.length !== 1 ? "ies" : "y"} recommended
</span>
<span className="text-xs text-success font-medium">All approved ✓</span>
```

"All approved ✓" is always rendered regardless of whether the LLM actually respected the approved list. Replace it with a neutral label that makes no claim about compliance.

- [ ] **Step 1: Replace the hardcoded badge**

Find the line containing `"All approved ✓"` in `frontend/app/(app)/projects/[id]/techstack/page.tsx` and replace just that `<span>`:

```tsx
<span className="text-xs text-text-muted font-medium">From approved list</span>
```

- [ ] **Step 2: Type-check frontend**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/(app)/projects/[id]/techstack/page.tsx
git commit -m "fix(ui): replace hardcoded approved badge with neutral label on stack page"
```

---

## Task 5: Backfill existing DB tags

This is an operational step to apply tags to any already-running database. Run once after deploying.

- [ ] **Step 1: Backfill tags on existing records**

```bash
curl -X POST http://localhost:8000/api/v1/factory/seed-technologies
```

Expected response:
```json
{"status": "ok", "seeded": 22}
```

- [ ] **Step 2: Verify tags in DB**

```bash
cd backend && source .venv/bin/activate
python -c "
from app.database import SessionLocal
from app.models.reference import ApprovedTechnology
db = SessionLocal()
rows = db.query(ApprovedTechnology).all()
for r in rows:
    print(f'{r.name}: {r.tags}')
db.close()
"
```

Expected: All 22 rows print non-null tags. Example:
```
Next.js: SPA,SSR,TypeScript-first,prototyping,production
SQLite: relational,embedded,prototyping,low-scale
PostgreSQL: relational,ACID,production,high-scale
...
```

- [ ] **Step 3: Run full backend test suite**

```bash
cd backend && pytest -v
```

Expected: All tests pass.
