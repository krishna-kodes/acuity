import { cn } from "@/lib/utils";

export type SyncStatus = "pending" | "synced" | "skipped" | "failed";

interface SyncStatusBadgeProps {
  status: SyncStatus;
  size?: "sm" | "md";
  className?: string;
}

const STYLES: Record<SyncStatus, { dot: string; label: string; bg: string; text: string }> = {
  pending: { dot: "bg-text-muted",  label: "Pending", bg: "bg-surface-subtle",      text: "text-text-muted" },
  synced:  { dot: "bg-success",     label: "Synced",  bg: "bg-success-subtle",       text: "text-success" },
  skipped: { dot: "bg-warning",     label: "Skipped", bg: "bg-warning-subtle",       text: "text-warning" },
  failed:  { dot: "bg-destructive", label: "Failed",  bg: "bg-destructive-subtle",   text: "text-destructive" },
};

export function SyncStatusBadge({ status, size = "md", className }: SyncStatusBadgeProps) {
  const s = STYLES[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-medium border",
        size === "sm" ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-0.5 text-[11px]",
        s.bg,
        s.text,
        "border-transparent",
        className
      )}
    >
      <span className={cn("rounded-full shrink-0", s.dot, size === "sm" ? "w-1 h-1" : "w-1.5 h-1.5")} />
      {s.label}
    </span>
  );
}
