# Tech Stack Prompt Strictness + Approved Technology Tags

**Date:** 2026-06-10  
**Status:** Approved

---

## Problem

1. The LLM ignores the approved technology list constraint — it hallucinates techs not in the DB (e.g. `Python`, `TailwindCSS` instead of `Tailwind CSS`).
2. All 22 `ApprovedTechnology` records have empty `tags` — the LLM gets no signal for *when* to pick each tech, so it defaults to the same stack for every project type.
3. `_phase_3_stack_node` silently swallows all LLM exceptions (`except Exception: pass`), returning `_FALLBACK_STACK` with no log — impossible to diagnose failures.
4. `"All approved ✓"` badge in `techstack/page.tsx` is hardcoded `true` — misleading when the LLM has hallucinated.

---

## Changes

### 1. Rich tags on `_APPROVED_TECHS` (seeder.py)

Expand `_APPROVED_TECHS` to 3-tuples `(name, category, tags)`. Tags encode use-case hints and complexity/scale signals so the LLM can match project needs to technology.

| Tech | Tags |
|------|------|
| Next.js | SPA, SSR, TypeScript-first, prototyping, production |
| React | SPA, component-library, flexible, prototyping, production |
| Vue.js | SPA, lightweight, progressive, prototyping |
| TypeScript | typed, compile-time-safety, large-team |
| Tailwind CSS | utility-CSS, rapid-prototyping, design-system |
| FastAPI | REST, async, Python, ML-friendly, prototyping, production |
| Django | REST, batteries-included, ORM, Python, high-scale |
| Node.js | REST, event-driven, JavaScript, high-scale |
| Go | REST, high-performance, compiled, high-scale |
| Rust | systems, high-performance, compiled, high-scale |
| PostgreSQL | relational, ACID, production, high-scale |
| SQLite | relational, embedded, prototyping, low-scale |
| MongoDB | NoSQL, flexible-schema, document-store, high-scale |
| Redis | cache, pub-sub, session-store, high-scale |
| Elasticsearch | search, full-text, analytics, high-scale |
| Docker | containerization, local-dev, portable |
| Kubernetes | orchestration, high-scale, complex-ops, production |
| Railway | PaaS, simple-deploy, low-ops, prototyping |
| AWS Lambda | serverless, event-driven, high-scale, pay-per-use |
| Terraform | IaC, cloud-provisioning, production |
| LangChain | LLM-orchestration, RAG, agents, Python |
| ChromaDB | vector-store, embeddings, RAG, local-dev |

### 2. Seeder upsert (seeder.py)

Change `seed_technologies` from insert-only to upsert so existing empty-tag records get backfilled when `POST /factory/seed-technologies` is called.

```python
for name, category, tags in _APPROVED_TECHS[:count]:
    existing = db.query(ApprovedTechnology).filter_by(name=name).first()
    if existing:
        existing.tags = tags
        seeded += 1
    else:
        db.add(ApprovedTechnology(name=name, category=category, tags=tags))
        seeded += 1
db.commit()
```

### 3. Stricter prompt (workflow.py + projects.py)

Two locations get the same updated prompt — `_phase_3_stack_node` and `suggest_stack_stream`:

```
Select technologies ONLY from the approved list below. Do not suggest any technology
not present in this list. Use EXACT names as written.

{tech_descriptions}

Choose 1–3 per category (frontend, backend, database, infra).
Use the tags to match project needs — e.g. prefer 'prototyping' tags for MVPs,
'high-scale' for enterprise. Return your selections and a brief rationale explaining
why each choice fits this project.
```

`tech_descriptions` format already includes tags: `- Next.js (frontend): SPA,SSR,...`

### 4. Error logging on fallback (workflow.py)

Replace silent `except Exception: pass` with:

```python
except Exception as exc:
    record_error(int(state["project_id"]), "phase_3", type(exc).__name__, str(exc))
    tech_stack = _FALLBACK_STACK
    ps["phase_3"] = "complete"
```

### 5. Remove misleading badge (techstack/page.tsx)

Replace hardcoded `"All approved ✓"` with the count only: `"{items.length} technologies selected"`. A proper per-item compliance check requires a new `/approved-technologies` endpoint — out of scope here.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/app/services/seeder.py` | `_APPROVED_TECHS` → 3-tuples, `seed_technologies` → upsert |
| `backend/app/services/workflow.py` | Stricter prompt in `_phase_3_stack_node`, error logging on fallback |
| `backend/app/routers/projects.py` | Stricter prompt in `suggest_stack_stream` |
| `frontend/app/(app)/projects/[id]/techstack/page.tsx` | Remove hardcoded "All approved ✓" badge |

---

## Testing

- Run `POST /factory/seed-technologies` — verify existing records now have tags via DB query
- Run tech stack for a project with a clear domain (e.g. ML pipeline) — verify it picks `FastAPI`/`LangChain` not always `Next.js`/`FastAPI`/`SQLite`/`Railway`
- Simulate LLM failure (bad API key) — verify `error_logs` row created, fallback stack returned, no silent swallow
- Verify hardcoded badge gone from stack page
