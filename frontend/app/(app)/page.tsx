"use client";

import Link from "next/link";
import { useState, useRef, useEffect } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { MetricsStatCard } from "@/components/metrics-stat-card";
import { DashboardSkeleton, ErrorBanner, EmptyState } from "@/components/page-states";
import { listAllProjects, archiveProject, unarchiveProject, type ProjectListItem } from "@/lib/api";
import { cn } from "@/lib/utils";

const PHASE_ROUTES: Record<number, string> = {
  1: "redaction", 2: "chat", 3: "modules", 4: "techstack",
  5: "team", 6: "estimation", 7: "epics", 8: "metrics",
};

const PHASE_LABELS: Record<number, string> = {
  1: "Redaction", 2: "Chat & Refine", 3: "Modules", 4: "Tech Stack",
  5: "Team", 6: "Estimation", 7: "Epics & Sync", 8: "Complete",
};

const PHASE_COLORS: Record<number, string> = {
  1: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  2: "bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400",
  3: "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400",
  4: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400",
  5: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  6: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400",
  7: "bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400",
  8: "bg-success-subtle text-success",
};

const PHASE_DOT: Record<number, string> = {
  1: "bg-orange-500", 2: "bg-sky-500", 3: "bg-violet-500", 4: "bg-indigo-500",
  5: "bg-blue-500",   6: "bg-cyan-500", 7: "bg-teal-500",  8: "bg-success",
};

function phaseRoute(n: number)  { return PHASE_ROUTES[n] ?? "redaction"; }
function phaseLabel(n: number)  { return PHASE_LABELS[n] ?? "Draft"; }
function phaseColor(n: number)  { return PHASE_COLORS[n] ?? "bg-surface-subtle text-text-muted"; }
function phaseDot(n: number)    { return PHASE_DOT[n] ?? "bg-text-muted"; }
function actionLabel(n: number) { return n >= 7 ? "View" : "Resume"; }

function timeAgo(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return mins <= 1 ? "Just now" : `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return hrs === 1 ? "1h ago" : `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return days === 1 ? "Yesterday" : `${days}d ago`;
}

function ThreeDotsMenu({
  projectId, isArchived, onArchive, onUnarchive,
}: {
  projectId: string; isArchived: boolean;
  onArchive: (id: string) => void; onUnarchive: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div ref={ref} className="relative" onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center justify-center w-7 h-7 rounded-md text-text-muted hover:bg-surface-subtle hover:text-foreground transition-colors"
        aria-label="Project actions"
      >
        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
          <circle cx="8" cy="3" r="1.2" /><circle cx="8" cy="8" r="1.2" /><circle cx="8" cy="13" r="1.2" />
        </svg>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 w-44 bg-card border border-border rounded-lg shadow-md overflow-hidden">
          {isArchived ? (
            <button onClick={() => { onUnarchive(projectId); setOpen(false); }}
              className="w-full text-left px-3 py-2 text-sm text-foreground hover:bg-surface-subtle transition-colors">
              Restore project
            </button>
          ) : (
            <button onClick={() => { onArchive(projectId); setOpen(false); }}
              className="w-full text-left px-3 py-2 text-sm text-foreground hover:bg-surface-subtle transition-colors">
              Archive project
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function ProjectRow({ project, isArchived, onArchive, onUnarchive }: {
  project: ProjectListItem; isArchived: boolean;
  onArchive: (id: string) => void; onUnarchive: (id: string) => void;
}) {
  const route = phaseRoute(project.current_phase);

  return (
    <div className={cn("flex items-center gap-4 px-4 py-3 border-b border-border last:border-0 hover:bg-surface-subtle transition-colors", isArchived && "opacity-50")}>

      {/* PROJECT col */}
      <Link href={`/projects/${project.id}/${route}`} className="flex items-center gap-3 min-w-0 flex-[2]">
        <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center shrink-0">
          <svg className="w-4 h-4 text-primary" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={1.6}>
            <path d="M4 2h5l3 3v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z" />
            <path d="M9 2v3h3" /><path d="M5 8h6M5 11h4" strokeLinecap="round" />
          </svg>
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-foreground truncate">{project.name}</div>
          {project.document_filename && (
            <div className="text-[11px] text-text-muted truncate">{project.document_filename}</div>
          )}
        </div>
      </Link>

      {/* DOMAIN col */}
      <div className="flex-1 min-w-0 hidden sm:block">
        <span className="text-sm text-text-secondary truncate">{project.domain ?? "—"}</span>
        {/* Tech stack pills */}
        {project.tech_preview && project.tech_preview.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-0.5">
            {project.tech_preview.slice(0, 3).map((t) => (
              <span key={t} className="text-[10px] bg-surface-subtle border border-border rounded px-1.5 py-0.5 text-text-secondary">
                {t}
              </span>
            ))}
            {project.tech_preview.length > 3 && (
              <span className="text-[10px] text-text-muted">+{project.tech_preview.length - 3}</span>
            )}
          </div>
        )}
      </div>

      {/* CURRENT PHASE col */}
      <div className="flex-1 flex items-center gap-2 hidden md:flex">
        <span className={cn("inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium", phaseColor(project.current_phase))}>
          <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", phaseDot(project.current_phase))} />
          {phaseLabel(project.current_phase)}
        </span>
      </div>

      {/* LAST UPDATED col */}
      <div className="w-24 text-sm text-text-secondary text-right hidden lg:block shrink-0">
        {timeAgo(project.updated_at)}
      </div>

      {/* GitHub link */}
      {project.milestones_url && (
        <a href={project.milestones_url} target="_blank" rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="shrink-0 hidden lg:flex items-center gap-1 text-[11px] text-text-muted hover:text-primary transition-colors">
          <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 16 16">
            <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
          </svg>
        </a>
      )}

      {/* Action button */}
      <Link
        href={`/projects/${project.id}/${route}`}
        onClick={(e) => e.stopPropagation()}
        className="shrink-0 inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-border text-xs font-medium text-foreground hover:bg-surface-subtle transition-colors"
      >
        {actionLabel(project.current_phase)}
        <svg className="w-3 h-3" fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2}>
          <path d="M2 6h8M7 3l3 3-3 3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </Link>

      {/* Three-dot menu */}
      <ThreeDotsMenu projectId={project.id} isArchived={isArchived} onArchive={onArchive} onUnarchive={onUnarchive} />
    </div>
  );
}

function TableHeader() {
  return (
    <div className="flex items-center gap-4 px-4 py-2.5 border-b border-border bg-surface-subtle">
      <span className="flex-[2] text-[11px] font-semibold uppercase tracking-wider text-text-muted">Project</span>
      <span className="flex-1 text-[11px] font-semibold uppercase tracking-wider text-text-muted hidden sm:block">Domain</span>
      <span className="flex-1 text-[11px] font-semibold uppercase tracking-wider text-text-muted hidden md:block">Current Phase</span>
      <span className="w-24 text-[11px] font-semibold uppercase tracking-wider text-text-muted text-right hidden lg:block shrink-0">Last Updated</span>
      <span className="w-[88px] hidden lg:block shrink-0" />
      <span className="w-7 shrink-0" />
    </div>
  );
}

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["projects-all"],
    queryFn: listAllProjects,
  });

  const archive = useMutation({
    mutationFn: archiveProject,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects-all"] }),
  });

  const unarchive = useMutation({
    mutationFn: unarchiveProject,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects-all"] }),
  });

  if (isLoading) return <DashboardSkeleton />;

  const allProjects = data ?? [];
  const active   = allProjects.filter((p) => p.status !== "archived");
  const archived = allProjects.filter((p) => p.status === "archived");
  const activeCount = active.filter((p) => p.status === "active").length;
  const syncedCount = active.filter((p) => p.current_phase >= 7).length;

  const rowProps = {
    onArchive:   (id: string) => archive.mutate(id),
    onUnarchive: (id: string) => unarchive.mutate(id),
  };

  return (
    <div className="px-6 py-8 max-w-5xl mx-auto flex flex-col gap-6">

      {isError && (
        <ErrorBanner
          message={error instanceof Error ? error.message : "Failed to load projects"}
          onRetry={() => refetch()}
        />
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        <MetricsStatCard label="Total Projects"   value={active.length} />
        <MetricsStatCard label="In Progress"      value={activeCount} />
        <MetricsStatCard label="Synced to GitHub" value={syncedCount} />
      </div>

      {/* Active projects table */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <span className="text-xs font-semibold uppercase tracking-wide text-text-muted">Projects</span>
          <Link href="/projects/new"
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:text-accent-hover transition-colors">
            <svg className="w-3 h-3" fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2.5}>
              <path d="M6 2v8M2 6h8" strokeLinecap="round" />
            </svg>
            New
          </Link>
        </div>

        {active.length === 0 ? (
          <EmptyState
            title="No projects yet"
            description="Upload a requirements document to get started."
            icon={
              <svg className="w-5 h-5" fill="none" viewBox="0 0 20 20" stroke="currentColor" strokeWidth={1.5}>
                <rect x="3" y="3" width="6" height="6" rx="1.5" /><rect x="11" y="3" width="6" height="6" rx="1.5" />
                <rect x="3" y="11" width="6" height="6" rx="1.5" /><rect x="11" y="11" width="6" height="6" rx="1.5" />
              </svg>
            }
            action={
              <Link href="/projects/new"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium bg-primary text-primary-foreground hover:bg-accent-hover transition-colors">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2.5}>
                  <path d="M7 2v10M2 7h10" strokeLinecap="round" />
                </svg>
                New Project
              </Link>
            }
          />
        ) : (
          <>
            <TableHeader />
            {active.map((p) => <ProjectRow key={p.id} project={p} isArchived={false} {...rowProps} />)}
          </>
        )}
      </div>

      {/* Archived section */}
      {archived.length > 0 && (
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <button
            onClick={() => setShowArchived((v) => !v)}
            className="w-full flex items-center justify-between px-4 py-3 border-b border-border hover:bg-surface-subtle transition-colors"
          >
            <span className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Archived ({archived.length})
            </span>
            <svg className={cn("w-3 h-3 text-text-muted transition-transform", showArchived && "rotate-180")}
              fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2}>
              <path d="M2 4l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          {showArchived && (
            <>
              <TableHeader />
              {archived.map((p) => <ProjectRow key={p.id} project={p} isArchived={true} {...rowProps} />)}
            </>
          )}
        </div>
      )}

    </div>
  );
}
