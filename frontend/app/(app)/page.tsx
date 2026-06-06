"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ProjectCard } from "@/components/project-card";
import { MetricsStatCard } from "@/components/metrics-stat-card";
import { DashboardSkeleton, ErrorBanner, EmptyState } from "@/components/page-states";
import type { ProjectCardProps } from "@/components/project-card";

// Placeholder data — replaced by API call in Epic 4
const MOCK_PROJECTS: ProjectCardProps[] = [
  { id: "proj_001", name: "E-Commerce Platform Rewrite", domain: "Retail",           phase: "chat",      syncStatus: "synced",  updated: "2 hours ago" },
  { id: "proj_002", name: "Internal HR Portal",          domain: "Human Resources",  phase: "epics",     syncStatus: "pending", updated: "Yesterday" },
  { id: "proj_003", name: "Mobile Banking App",          domain: "FinTech",          phase: "estimation",syncStatus: "failed",  updated: "3 days ago" },
  { id: "proj_004", name: "Data Analytics Dashboard",    domain: "Internal Tools",   phase: "ingestion",                        updated: "1 week ago" },
];

type LoadState = "loading" | "loaded" | "error" | "empty";

export default function DashboardPage() {
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [error, setError]         = useState<string | null>(null);
  const projects = loadState === "empty" ? [] : MOCK_PROJECTS;

  // TODO (Epic 4): replace with real API fetch
  useEffect(() => {
    const timer = setTimeout(() => setLoadState("loaded"), 600);
    return () => clearTimeout(timer);
  }, []);

  function retry() {
    setError(null);
    setLoadState("loading");
    setTimeout(() => setLoadState("loaded"), 600);
  }

  if (loadState === "loading") return <DashboardSkeleton />;

  const totalCount  = projects.length;
  const activeCount = projects.filter((p) => p.phase !== "synced").length;
  const syncedCount = projects.filter((p) => p.syncStatus === "synced").length;

  return (
    <div className="px-6 py-8 max-w-5xl mx-auto flex flex-col gap-6">

      {error && <ErrorBanner message={error} onRetry={retry} />}

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
              <Link key={project.id} href={`/projects/${project.id}/redaction`} className="block">
                <ProjectCard {...project} />
              </Link>
            ))}
          </div>
        )}
      </div>

    </div>
  );
}
