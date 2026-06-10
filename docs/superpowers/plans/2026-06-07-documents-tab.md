# Documents Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent Documents page at `/projects/[id]/documents` listing uploaded requirements docs and generated proposals, with download, metadata preview, and delete actions.

**Architecture:** Two new backend endpoints (list + delete per type) + one new frontend page. The sidebar already auto-detects `projectId` from the URL — just add the nav entry. No new DB tables; uses existing `documents` and `proposals` tables.

**Tech Stack:** FastAPI (backend), Next.js 16.2 App Router, TanStack Query, Tailwind v4, openapi-fetch

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/routers/projects.py` | Modify | Add 4 endpoints: list-docs, download-uploaded, delete-document, delete-proposal |
| `backend/app/schemas/document.py` | Modify | Add `ProjectDocumentItem` response schema |
| `frontend/app/(app)/projects/[id]/documents/page.tsx` | Create | Documents page — two-section list UI |
| `frontend/components/app-sidebar.tsx` | Modify | Add Documents nav item to `buildProjectNav` |
| `frontend/lib/api.ts` | Modify | Add `listProjectDocuments`, `downloadDocument`, `deleteDocument`, `deleteProposal` |
| `frontend/lib/api.types.ts` | Modify | Add `ProjectDocumentItem` type (or use inline) |

---

## Task 1: Backend — list endpoint + schemas

**Files:**
- Modify: `backend/app/schemas/document.py`
- Modify: `backend/app/routers/projects.py`

- [ ] **Step 1: Add `ProjectDocumentItem` schema to `document.py`**

Open `backend/app/schemas/document.py` and append:

```python
from typing import Literal

class ProjectDocumentItem(BaseModel):
    id: str
    doc_type: Literal["uploaded", "generated"]
    filename: str
    status: str
    size_bytes: int | None
    created_at: str
    download_url: str
```

- [ ] **Step 2: Add `GET /projects/{id}/documents-list` endpoint**

In `backend/app/routers/projects.py`, add after the existing `upload_document` endpoint (around line 145):

```python
@router.get(
    "/projects/{project_id}/documents-list",
    response_model=list[ProjectDocumentItem],
)
def list_project_documents(
    project_id: str,
    db: Session = Depends(get_db),
) -> list[ProjectDocumentItem]:
    """Return all uploaded docs + generated proposals for a project."""
    from app.schemas.document import ProjectDocumentItem

    project = _get_project_or_404(project_id, db)
    items: list[ProjectDocumentItem] = []

    for doc in db.query(Document).filter(Document.project_id == project.id).all():
        file_path = f"documents/{project.id}_{doc.filename}"
        size = None
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
        items.append(ProjectDocumentItem(
            id=str(doc.id),
            doc_type="uploaded",
            filename=doc.filename,
            status=doc.status.value,
            size_bytes=size,
            created_at=doc.upload_ts.isoformat(),
            download_url=f"/api/v1/projects/{project_id}/documents/{doc.id}/download",
        ))

    for proposal in (
        db.query(Proposal)
        .filter(Proposal.project_id == project.id)
        .order_by(Proposal.created_at.desc())
        .all()
    ):
        size = None
        if os.path.exists(proposal.content_path):
            size = os.path.getsize(proposal.content_path)
        items.append(ProjectDocumentItem(
            id=str(proposal.id),
            doc_type="generated",
            filename=os.path.basename(proposal.content_path),
            status="ready",
            size_bytes=size,
            created_at=proposal.created_at.isoformat(),
            download_url=f"/api/v1/projects/{project_id}/export/proposal",
        ))

    return sorted(items, key=lambda x: x.created_at, reverse=True)
```

Also add `ProjectDocumentItem` to the import from `app.schemas.document` at the top of `projects.py`:

```python
from app.schemas.document import (
    DocumentResponse,
    ProjectDocumentItem,
    RedactionDecisionResponse,
    RedactionDecisionsUpdate,
    RedactionSummaryResponse,
)
```

- [ ] **Step 3: Add `GET /projects/{id}/documents/{doc_id}/download` endpoint**

In `backend/app/routers/projects.py`, add after the list endpoint:

```python
@router.get("/projects/{project_id}/documents/{doc_id}/download")
def download_document(
    project_id: str,
    doc_id: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Download the original uploaded requirements document."""
    _get_project_or_404(project_id, db)
    doc = db.query(Document).filter(
        Document.id == int(doc_id),
        Document.project_id == int(project_id),
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = f"documents/{project_id}_{doc.filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={doc.filename}"},
    )
```

- [ ] **Step 4: Add `DELETE /projects/{id}/documents/{doc_id}` endpoint**

```python
@router.delete("/projects/{project_id}/documents/{doc_id}", status_code=204)
def delete_document(
    project_id: str,
    doc_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Delete an uploaded document record and its file on disk."""
    _get_project_or_404(project_id, db)
    doc = db.query(Document).filter(
        Document.id == int(doc_id),
        Document.project_id == int(project_id),
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = f"documents/{project_id}_{doc.filename}"
    if os.path.exists(file_path):
        os.remove(file_path)
    db.delete(doc)
    db.commit()
```

- [ ] **Step 5: Add `DELETE /projects/{id}/proposals/{proposal_id}` endpoint**

```python
@router.delete("/projects/{project_id}/proposals/{proposal_id}", status_code=204)
def delete_proposal(
    project_id: str,
    proposal_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Delete a generated proposal record and its DOCX file on disk."""
    _get_project_or_404(project_id, db)
    proposal = db.query(Proposal).filter(
        Proposal.id == int(proposal_id),
        Proposal.project_id == int(project_id),
    ).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if os.path.exists(proposal.content_path):
        os.remove(proposal.content_path)
    db.delete(proposal)
    db.commit()
```

- [ ] **Step 6: Verify backend starts cleanly**

```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000 --reload
```

Expected: no import errors. Check `http://localhost:8000/docs` — new endpoints appear under projects.

- [ ] **Step 7: Smoke test list endpoint**

```bash
curl -s http://localhost:8000/api/v1/projects/9/documents-list | python3 -m json.tool
```

Expected: JSON array with `doc_type: "uploaded"` and/or `"generated"` entries.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/document.py backend/app/routers/projects.py
git commit -m "feat: add documents list, download, and delete endpoints"
```

---

## Task 2: Frontend API client

**Files:**
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Add API functions**

Append to `frontend/lib/api.ts`:

```typescript
export const listProjectDocuments = (projectId: string) =>
  apiClient.GET("/api/v1/projects/{project_id}/documents-list" as never, {
    params: { path: { project_id: projectId } },
  } as never) as Promise<{ data?: Array<{
    id: string;
    doc_type: "uploaded" | "generated";
    filename: string;
    status: string;
    size_bytes: number | null;
    created_at: string;
    download_url: string;
  }>; error?: unknown }>

export const deleteDocument = (projectId: string, docId: string) =>
  fetch(
    `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/projects/${projectId}/documents/${docId}`,
    { method: "DELETE" }
  )

export const deleteProposal = (projectId: string, proposalId: string) =>
  fetch(
    `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/projects/${projectId}/proposals/${proposalId}`,
    { method: "DELETE" }
  )
```

> Note: `listProjectDocuments` uses a cast because the auto-generated `api.types.ts` doesn't yet have this path. The endpoint is type-safe at the server — adding a proper openapi type is post-MVP cleanup.

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat: add documents API client functions"
```

---

## Task 3: Documents page

**Files:**
- Create: `frontend/app/(app)/projects/[id]/documents/page.tsx`

- [ ] **Step 1: Create the page**

```tsx
"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { listProjectDocuments, deleteDocument, deleteProposal } from "@/lib/api";
import { cn } from "@/lib/utils";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function DocTypeBadge({ type }: { type: "uploaded" | "generated" }) {
  return (
    <span className={cn(
      "text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full",
      type === "uploaded"
        ? "bg-accent-subtle text-accent border border-accent/20"
        : "bg-warning-subtle text-warning border border-warning/20"
    )}>
      {type === "uploaded" ? "Uploaded" : "Generated"}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color = status === "ready" ? "bg-success-subtle text-success border-success/20"
    : status === "anonymising" ? "bg-warning-subtle text-warning border-warning/20"
    : "bg-muted text-text-muted border-border";
  return (
    <span className={cn("text-[10px] font-medium px-1.5 py-0.5 rounded border", color)}>
      {status}
    </span>
  );
}

export default function DocumentsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: projectId } = use(params);
  const queryClient = useQueryClient();
  const [deleting, setDeleting] = useState<string | null>(null);

  const { data: docs, isLoading } = useQuery({
    queryKey: ["project-documents", projectId],
    queryFn: async () => {
      const result = await listProjectDocuments(projectId);
      if (result.error) throw new Error(String(result.error));
      return result.data ?? [];
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  async function handleDelete(doc: { id: string; doc_type: "uploaded" | "generated" }) {
    setDeleting(doc.id);
    try {
      if (doc.doc_type === "uploaded") {
        await deleteDocument(projectId, doc.id);
      } else {
        await deleteProposal(projectId, doc.id);
      }
      queryClient.invalidateQueries({ queryKey: ["project-documents", projectId] });
    } finally {
      setDeleting(null);
    }
  }

  const uploaded = docs?.filter((d) => d.doc_type === "uploaded") ?? [];
  const generated = docs?.filter((d) => d.doc_type === "generated") ?? [];

  return (
    <div className="px-6 py-8 max-w-3xl mx-auto flex flex-col gap-8">
      <div>
        <h1 className="text-base font-semibold text-foreground">Documents</h1>
        <p className="text-xs text-text-muted mt-0.5">
          Uploaded requirements documents and generated proposals for this project.
        </p>
      </div>

      {isLoading && (
        <p className="text-sm text-text-muted">Loading…</p>
      )}

      {[
        { label: "Requirements Documents", items: uploaded },
        { label: "Generated Documents", items: generated },
      ].map(({ label, items }) => (
        <section key={label} className="flex flex-col gap-3">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-text-muted">
            {label}
          </h2>
          {items.length === 0 ? (
            <p className="text-sm text-text-muted italic">None yet.</p>
          ) : (
            <div className="bg-card border border-border rounded-xl overflow-hidden divide-y divide-border">
              {items.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center gap-3 px-4 py-3"
                >
                  {/* File icon */}
                  <div className="shrink-0 w-8 h-8 rounded-lg bg-accent-subtle flex items-center justify-center">
                    <svg className="w-4 h-4 text-accent" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={1.75}>
                      <path d="M4 2h6l3 3v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z" />
                      <path d="M10 2v3h3" />
                    </svg>
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-foreground truncate">
                        {doc.filename}
                      </span>
                      <DocTypeBadge type={doc.doc_type} />
                      <StatusBadge status={doc.status} />
                    </div>
                    <div className="flex items-center gap-3 mt-0.5">
                      <span className="text-[11px] text-text-muted">{formatDate(doc.created_at)}</span>
                      <span className="text-[11px] text-text-muted">{formatBytes(doc.size_bytes)}</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1 shrink-0">
                    <a
                      href={`${apiBase}${doc.download_url}`}
                      download
                      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium bg-muted text-foreground hover:bg-accent-subtle transition-colors"
                    >
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2}>
                        <path d="M6 1v7M3 5l3 3 3-3" strokeLinecap="round" strokeLinejoin="round" />
                        <path d="M1 10h10" strokeLinecap="round" />
                      </svg>
                      Download
                    </a>
                    <button
                      onClick={() => handleDelete(doc)}
                      disabled={deleting === doc.id}
                      className="flex items-center justify-center w-7 h-7 rounded-md text-text-muted hover:bg-destructive-subtle hover:text-destructive transition-colors disabled:opacity-50"
                      title="Delete"
                    >
                      {deleting === doc.id ? (
                        <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                          <path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" />
                        </svg>
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                          <path d="M3 4h10M6 4V3h4v1M5 4v8h6V4" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add "frontend/app/(app)/projects/[id]/documents/page.tsx"
git commit -m "feat: add documents page with list, download, and delete"
```

---

## Task 4: Add Documents to sidebar nav

**Files:**
- Modify: `frontend/components/app-sidebar.tsx`

- [ ] **Step 1: Add IconDocument SVG and nav entry**

In `app-sidebar.tsx`, add the icon function before `buildProjectNav`:

```tsx
function IconDocument() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={1.75}>
      <path d="M4 2h6l3 3v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z" />
      <path d="M10 2v3h3" />
      <path d="M5 8h6M5 11h4" strokeLinecap="round" />
    </svg>
  );
}
```

Then in `buildProjectNav`, add after the metrics entry:

```tsx
{ key: "documents", label: "Documents", href: `${base}/documents`, icon: <IconDocument />, phase: null },
```

- [ ] **Step 2: Verify sidebar renders Documents link for any project route**

Start frontend: `cd frontend && npm run dev`  
Navigate to `http://localhost:3000/projects/9/chat` — "Documents" appears in sidebar under "Current Project".

- [ ] **Step 3: Commit**

```bash
git add frontend/components/app-sidebar.tsx
git commit -m "feat: add Documents nav item to project sidebar"
```

---

## Task 5: End-to-end verification

- [ ] **Step 1: Navigate to `/projects/9/documents`**

Verify:
- Both sections render ("Requirements Documents", "Generated Documents")
- Each row shows filename, type badge, status badge, date, file size
- Download link works (browser downloads the file)

- [ ] **Step 2: Test delete**

Click trash icon on a generated document.
Verify: row disappears without page reload, spinner shows during request.

- [ ] **Step 3: Check empty states**

Navigate to a project with no proposals. Verify "None yet." appears in the Generated Documents section.

- [ ] **Step 4: Final commit and PR**

```bash
git push -u origin feat/documents-tab
gh pr create --title "feat: add Documents tab to project sidebar" --body "..."
```
