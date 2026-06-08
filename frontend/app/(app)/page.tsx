"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ProjectCard } from "@/components/project-card";
import { MetricsStatCard } from "@/components/metrics-stat-card";
import { DashboardSkeleton, ErrorBanner, EmptyState } from "@/components/page-states";
import { listProjects } from "@/lib/api";

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

export default function DashboardPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => {
      const { data, error } = await listProjects();
      if (error) throw new Error(String(error));
      return data ?? [];
    },
  });

  if (isLoading) return <DashboardSkeleton />;

  const projects = data ?? [];
  const totalCount  = projects.length;
  const activeCount = projects.filter((p) => p.status === "active").length;
  const syncedCount = projects.filter((p) => p.current_phase >= 7).length;

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
        <MetricsStatCard label="Total Projects"   value={totalCount} />
        <MetricsStatCard label="In Progress"      value={activeCount} />
        <MetricsStatCard label="Synced to GitHub" value={syncedCount} />
      </div>

      {/* Project list */}
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

        {projects.length === 0 ? (
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
          <div>
            {projects.map((project) => (
              <Link
                key={project.id}
                href={`/projects/${project.id}/${phaseRoute(project.current_phase)}`}
                className="block"
              >
                <ProjectCard
                  id={project.id}
                  name={project.name}
                  domain={project.domain ?? ""}
                  phase={phaseRoute(project.current_phase)}
                  updated={timeAgo(project.updated_at)}
                  techPreview={project.tech_preview}
                  totalWeeks={project.total_weeks}
                  teamSize={project.team_size}
                  moduleCount={project.module_count}
                />
              </Link>
            ))}
          </div>
        )}
      </div>

    </div>
  );
}
