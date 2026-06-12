"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { listProjectDocuments, deleteDocument, deleteProposal, _apiBase } from "@/lib/api";
import { cn } from "@/lib/utils";

const apiBase = _apiBase();

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
        ? "bg-accent-subtle text-accent border border-accent/30"
        : "bg-warning-subtle text-warning border border-warning/20"
    )}>
      {type === "uploaded" ? "Uploaded" : "Generated"}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "ready"
      ? "bg-success-subtle text-success border-success/20"
      : status === "anonymising"
      ? "bg-warning-subtle text-warning border-warning/20"
      : "bg-surface-subtle text-text-muted border-border";
  return (
    <span className={cn("text-[10px] font-medium px-1.5 py-0.5 rounded border", color)}>
      {status}
    </span>
  );
}

type DocItem = {
  id: string;
  doc_type: "uploaded" | "generated";
  filename: string;
  status: string;
  size_bytes: number | null;
  created_at: string;
  download_url: string;
};

export default function DocumentsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: projectId } = use(params);
  const queryClient = useQueryClient();
  const [deleting, setDeleting] = useState<string | null>(null);

  const { data: docs, isLoading, isError } = useQuery({
    queryKey: ["project-documents", projectId],
    queryFn: async () => {
      const result = await listProjectDocuments(projectId);
      if (result.error) throw new Error(String(result.error));
      return result.data ?? [];
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  async function handleDelete(doc: DocItem) {
    setDeleting(doc.id);
    try {
      const res =
        doc.doc_type === "uploaded"
          ? await deleteDocument(projectId, doc.id)
          : await deleteProposal(projectId, doc.id);
      if (res.ok) {
        queryClient.invalidateQueries({ queryKey: ["project-documents", projectId] });
      }
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

      {isError && (
        <p className="text-sm text-destructive">Failed to load documents. Please refresh.</p>
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
                  <div className="shrink-0 w-8 h-8 rounded-lg bg-accent-subtle flex items-center justify-center">
                    <svg className="w-4 h-4 text-accent" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={1.75}>
                      <path d="M4 2h6l3 3v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z" />
                      <path d="M10 2v3h3" />
                    </svg>
                  </div>

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

                  <div className="flex items-center gap-1 shrink-0">
                    <a
                      href={`${apiBase}${doc.download_url}`}
                      download
                      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium bg-surface-subtle text-foreground hover:bg-accent-subtle transition-colors"
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
