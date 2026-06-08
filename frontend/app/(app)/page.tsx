"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useRef, useEffect } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { ProjectCard } from "@/components/project-card";
import { MetricsStatCard } from "@/components/metrics-stat-card";
import { DashboardSkeleton, ErrorBanner, EmptyState } from "@/components/page-states";
import { listAllProjects, archiveProject, unarchiveProject } from "@/lib/api";
import { cn } from "@/lib/utils";

const PHASE_ROUTES: Record<number, string> = {
  1: "redaction",
  2: "chat",
  3: "modules",
  4: "techstack",
  5: "team",
  6: "estimation",
  7: "epics",
  8: "metrics",
};

function phaseRoute(phaseNum: number): string {
  return PHASE_ROUTES[phaseNum] ?? "redaction";
}

function timeAgo(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return mins <= 1 ? "Just now" : `${mins} minutes ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return hrs === 1 ? "1 hour ago" : `${hrs} hours ago`;
  const days = Math.floor(hrs / 24);
  return days === 1 ? "Yesterday" : `${days} days ago`;
}

function ThreeDotsMenu({
  projectId,
  isArchived,
  onArchive,
  onUnarchive,
}: {
  projectId: string;
  isArchived: boolean;
  onArchive: (id: string) => void;
  onUnarchive: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={ref} className="relative" onClick={(e) => e.preventDefault()}>
      <button
        onClick={(e) => { e.stopPropagation(); e.preventDefault(); setOpen((v) => !v); }}
        className="flex items-center justify-center w-7 h-7 rounded-md text-text-muted hover:bg-surface-subtle hover:text-foreground transition-colors"
        aria-label="Project actions"
      >
        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
          <circle cx="8" cy="3" r="1.2" />
          <circle cx="8" cy="8" r="1.2" />
          <circle cx="8" cy="13" r="1.2" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 w-40 bg-card border border-border rounded-lg shadow-md overflow-hidden">
          {isArchived ? (
            <button
              onClick={(e) => { e.stopPropagation(); e.preventDefault(); onUnarchive(projectId); setOpen(false); }}
              className="w-full text-left px-3 py-2 text-sm text-foreground hover:bg-surface-subtle transition-colors"
            >
              Restore project
            </button>
          ) : (
            <button
              onClick={(e) => { e.stopPropagation(); e.preventDefault(); onArchive(projectId); setOpen(false); }}
              className="w-full text-left px-3 py-2 text-sm text-foreground hover:bg-surface-subtle transition-colors"
            >
              Archive project
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
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

  function renderRow(project: typeof allProjects[number], isArch: boolean) {
    const route = phaseRoute(project.current_phase);
    return (
      <div key={project.id} className="flex items-center gap-1 pr-2 border-b border-border last:border-0">
        <Link href={`/projects/${project.id}/${route}`} className="flex-1 min-w-0">
          <ProjectCard
            id={project.id}
            name={project.name}
            domain={project.domain ?? ""}
            phase={route}
            updated={timeAgo(project.updated_at)}
            className={cn("border-0", isArch ? "opacity-50" : undefined)}
          />
        </Link>
        <ThreeDotsMenu
          projectId={project.id}
          isArchived={isArch}
          onArchive={(id) => archive.mutate(id)}
          onUnarchive={(id) => unarchive.mutate(id)}
        />
      </div>
    );
  }

  return (
    <div className="px-6 py-8 max-w-5xl mx-auto flex flex-col gap-6">

      {isError && (
        <ErrorBanner
          message={error instanceof Error ? error.message : "Failed to load projects"}
          onRetry={() => refetch()}
        />
      )}

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3">
        <MetricsStatCard label="Total Projects"   value={active.length} />
        <MetricsStatCard label="In Progress"      value={activeCount} />
        <MetricsStatCard label="Synced to GitHub" value={syncedCount} />
      </div>

      {/* Active projects */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <span className="text-xs font-semibold uppercase tracking-wide text-text-muted">Projects</span>
          <Link
            href="/projects/new"
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:text-accent-hover transition-colors"
          >
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
              <Link
                href="/projects/new"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium bg-primary text-primary-foreground hover:bg-accent-hover transition-colors"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2.5}>
                  <path d="M7 2v10M2 7h10" strokeLinecap="round" />
                </svg>
                New Project
              </Link>
            }
          />
        ) : (
          <div>{active.map((p) => renderRow(p, false))}</div>
        )}
      </div>

      {/* Archived projects */}
      {archived.length > 0 && (
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <button
            onClick={() => setShowArchived((v) => !v)}
            className="w-full flex items-center justify-between px-4 py-3 border-b border-border hover:bg-surface-subtle transition-colors"
          >
            <span className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Archived ({archived.length})
            </span>
            <svg
              className={cn("w-3 h-3 text-text-muted transition-transform", showArchived && "rotate-180")}
              fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2}
            >
              <path d="M2 4l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          {showArchived && (
            <div>{archived.map((p) => renderRow(p, true))}</div>
          )}
        </div>
      )}

    </div>
  );
}
