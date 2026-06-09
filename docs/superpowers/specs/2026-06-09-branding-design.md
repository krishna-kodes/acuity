# Branding Feature Design

**Date:** 2026-06-09  
**Status:** Approved  
**Scope:** Global branding settings applied to DOCX proposal exports and surfaced via admin UI

---

## Overview

Adds a global branding configuration (company name, two brand colors, PM name) stored in SQLite with env var fallbacks. Brand colors replace hardcoded values in the DOCX exporter. PM configures settings via a new `/admin/branding` page.

---

## Data Layer

### New table: `branding_settings`

```sql
CREATE TABLE branding_settings (
    id INTEGER PRIMARY KEY DEFAULT 1,
    company_name VARCHAR NOT NULL DEFAULT '',
    primary_color VARCHAR(7) NOT NULL DEFAULT '#2E5FA3',
    secondary_color VARCHAR(7) NOT NULL DEFAULT '#1A3A6B',
    prepared_by VARCHAR NOT NULL DEFAULT '',
    updated_at DATETIME NOT NULL
);
```

Singleton row — always read/write `id=1`. Upsert on `PUT`.

### Env var fallbacks (added to `config.py` / `.env`)

```bash
BRANDING_COMPANY_NAME=
BRANDING_PRIMARY_COLOR=#2E5FA3
BRANDING_SECONDARY_COLOR=#1A3A6B
BRANDING_PREPARED_BY=
```

### Resolution order

`GET /api/v1/admin/branding` returns merged values:
1. DB row (if exists and field non-empty)
2. Env var default
3. Hardcoded fallback (`#2E5FA3` / `#1A3A6B` / empty string)

---

## API Layer

New endpoints in `backend/app/routers/admin.py`:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/admin/branding` | Returns merged branding settings |
| `PUT` | `/api/v1/admin/branding` | Partial update — upserts DB row |

### Schemas (`backend/app/schemas/branding.py`)

```python
class BrandingSettingsResponse(BaseModel):
    company_name: str
    primary_color: str    # #RRGGBB
    secondary_color: str  # #RRGGBB
    prepared_by: str
    updated_at: datetime | None

class BrandingSettingsUpdate(BaseModel):
    company_name: str | None = None
    primary_color: str | None = None   # validated: ^#[0-9A-Fa-f]{6}$
    secondary_color: str | None = None
    prepared_by: str | None = None
```

`PUT` validates hex color fields with regex — returns HTTP 422 if invalid format.

---

## DOCX Exporter

`generate_proposal_docx` gains optional `branding: BrandingSettingsResponse | None = None` parameter. When `None`, behavior is identical to today (no regression).

### Styled elements when branding provided

| Element | Before | After |
|---------|--------|-------|
| Table header background | `#2E5FA3` (hardcoded) | `branding.primary_color` |
| Table header text | White | White (always) |
| H1 / H2 heading text color | Word default (black) | `branding.secondary_color` |
| H3 / H4 heading text color | Word default (black) | Word default (unchanged) |
| Cover page subtitle line | Date only | "Prepared by: {prepared_by} · {company_name}" |
| Cover page title rule | None | Thin bottom border in `primary_color` |

### Affected functions

- `_style_table_header(table, primary_color: str)` — accepts color param instead of module-level constant
- `_add_markdown_body(doc, text, secondary_color: str | None)` — applies secondary color to H1/H2 runs
- `_add_cover_page(doc, title, company_name: str, prepared_by: str, primary_color: str)` — adds attribution line and title rule
- `generate_proposal_docx(...)` — passes branding fields through to all helpers

### Caller change (`backend/app/routers/projects.py`)

Before calling `generate_proposal_docx`, load branding:

```python
from app.services.branding import get_branding
branding = get_branding(db)
generate_proposal_docx(..., branding=branding)
```

`get_branding(db)` encapsulates DB read + env merge logic.

---

## Frontend

### New page: `/admin/branding`

File: `frontend/app/(app)/admin/branding/page.tsx`

- Fetches `GET /api/v1/admin/branding` on mount
- Form fields:
  - Company Name (text input)
  - Prepared By (text input, PM name)
  - Primary Color (native `<input type="color">` + hex text input, live swatch preview)
  - Secondary Color (same pattern)
- Save button → `PUT /api/v1/admin/branding`, success/error toast
- No new npm dependencies — shadcn `Input`, `Button`, `Card` + native color picker

### API client additions (`frontend/lib/api.ts`)

```typescript
export interface BrandingSettings {
  company_name: string;
  primary_color: string;
  secondary_color: string;
  prepared_by: string;
  updated_at: string | null;
}

export async function getBranding(): Promise<BrandingSettings> { ... }
export async function updateBranding(data: Partial<BrandingSettings>): Promise<BrandingSettings> { ... }
```

### Navigation

Add "Branding" link to admin nav alongside Employees and Skills.

---

## File Changelist

| File | Change |
|------|--------|
| `backend/app/models/branding.py` | New — `BrandingSettings` SQLAlchemy model |
| `backend/app/schemas/branding.py` | New — Pydantic request/response schemas |
| `backend/app/services/branding.py` | New — `get_branding(db)` merge logic |
| `backend/app/routers/admin.py` | Add `GET` + `PUT` branding endpoints |
| `backend/app/config.py` | Add 4 `branding_*` env var fields |
| `backend/alembic/versions/xxxx_add_branding_settings.py` | New migration |
| `backend/app/services/exporter.py` | Accept `branding` param, replace hardcoded colors |
| `backend/app/routers/projects.py` | Load + pass branding to `generate_proposal_docx` |
| `frontend/app/(app)/admin/branding/page.tsx` | New admin page |
| `frontend/lib/api.ts` | Add branding API functions + types |
| `frontend/app/(app)/admin/` | Nav link for Branding |

---

## Out of Scope

- Logo image upload (post-MVP)
- Per-project branding overrides (post-MVP)
- Font family configuration
- DOCX theme/style XML manipulation (using run-level color, not document theme)
