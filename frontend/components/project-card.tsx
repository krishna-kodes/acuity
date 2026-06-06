import { cn } from "@/lib/utils";

export type SyncStatus = "pending" | "synced" | "skipped" | "failed";

export interface ProjectCardProps {
  id: string;
  name: string;
  domain: string;
  phase: string;
  updated: string;
  syncStatus?: SyncStatus;
  onClick?: () => void;
  className?: string;
}

const PHASE_LABELS: Record<string, string> = {
  ingestion: "Ingestion",
  redaction: "Redaction",
  chat: "Refinement",
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
  onClick,
  className,
}: ProjectCardProps) {
  const phaseLabel = PHASE_LABELS[phase] ?? phase;
  const sync = syncStatus ? SYNC_STYLES[syncStatus] : null;

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
      {/* Left: name + domain */}
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className="text-sm font-semibold text-foreground truncate group-hover:text-primary transition-colors">
          {name}
        </span>
        <span className="text-xs text-text-secondary">{domain}</span>
      </div>

      {/* Right: phase badge + sync status + updated */}
      <div className="flex items-center gap-3 shrink-0">
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
