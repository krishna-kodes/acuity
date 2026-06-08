import { cn } from "@/lib/utils";

export type SyncStatus = "pending" | "synced" | "skipped" | "failed";

export interface ProjectCardProps {
  id: string;
  name: string;
  domain: string;
  phase: string;
  updated: string;
  syncStatus?: SyncStatus;
  techPreview?: string[];
  totalWeeks?: number | null;
  teamSize?: number;
  moduleCount?: number;
  milestonesUrl?: string | null;
  onClick?: () => void;
  className?: string;
}

const PHASE_LABELS: Record<string, string> = {
  ingestion: "Ingestion",
  redaction: "Redaction",
  chat: "Refinement",
  modules: "Modules",
  "tech-stack": "Tech Stack",
  techstack: "Tech Stack",
  team: "Team",
  estimation: "Estimation",
  epics: "Epics & Sync",
  synced: "Synced",
};

const SYNC_STYLES: Record<SyncStatus, { dot: string; label: string; bg: string; text: string }> = {
  pending:    { dot: "bg-text-muted",      label: "Pending",    bg: "bg-surface-subtle", text: "text-text-muted" },
  synced:     { dot: "bg-success",         label: "Synced",     bg: "bg-success-subtle", text: "text-success" },
  skipped:    { dot: "bg-warning",         label: "Skipped",    bg: "bg-warning-subtle", text: "text-warning" },
  failed:     { dot: "bg-destructive",     label: "Failed",     bg: "bg-destructive-subtle", text: "text-destructive" },
};

export function ProjectCard({
  name,
  domain,
  phase,
  updated,
  syncStatus,
  techPreview = [],
  totalWeeks,
  teamSize = 0,
  moduleCount = 0,
  milestonesUrl,
  onClick,
  className,
}: ProjectCardProps) {
  const phaseLabel = PHASE_LABELS[phase] ?? phase;
  const sync = syncStatus ? SYNC_STYLES[syncStatus] : null;
  const hasMeta = techPreview.length > 0 || totalWeeks || teamSize > 0 || moduleCount > 0;

  return (
    <div
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => e.key === "Enter" && onClick() : undefined}
      className={cn(
        "group flex items-center justify-between gap-4 px-4 py-3.5 border-b border-border last:border-0 transition-colors hover:bg-surface-subtle cursor-pointer",
        className
      )}
    >
      {/* Left: name + domain + metadata pills */}
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className="text-sm font-semibold text-foreground truncate group-hover:text-primary transition-colors">
          {name}
        </span>
        <span className="text-xs text-text-secondary">{domain}</span>
        {hasMeta && (
          <div className="flex flex-wrap gap-1 mt-0.5">
            {techPreview.map((t) => (
              <span key={t} className="text-[10px] bg-surface-subtle border border-border rounded px-1.5 py-0.5 text-text-secondary">
                {t}
              </span>
            ))}
            {totalWeeks != null && totalWeeks > 0 && (
              <span className="text-[10px] text-text-muted">{totalWeeks}w est.</span>
            )}
            {teamSize > 0 && (
              <span className="text-[10px] text-text-muted">{teamSize} devs</span>
            )}
            {moduleCount > 0 && (
              <span className="text-[10px] text-text-muted">{moduleCount} modules</span>
            )}
          </div>
        )}
      </div>

      {/* Right: phase badge + sync status + updated */}
      <div className="flex items-center gap-3 shrink-0">
        {milestonesUrl && (
          <a
            href={milestonesUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 text-[11px] text-primary hover:text-accent-hover transition-colors"
          >
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 16 16">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
            </svg>
            GitHub
          </a>
        )}
        <span className="text-xs text-text-secondary hidden sm:block">{updated}</span>

        {sync && (
          <span
            className={cn(
              "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium",
              sync.bg,
              sync.text
            )}
          >
            <span className={cn("w-1.5 h-1.5 rounded-full", sync.dot)} />
            {sync.label}
          </span>
        )}

        <span className="text-xs font-medium text-text-secondary bg-surface-subtle border border-border px-2 py-0.5 rounded-md">
          {phaseLabel}
        </span>
      </div>
    </div>
  );
}
