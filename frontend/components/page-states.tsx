import { cn } from "@/lib/utils";

// ── Skeleton primitives ───────────────────────────────────────────────────────

export function SkeletonBox({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-md bg-border animate-pulse", className)} />
  );
}

export function SkeletonRow({ cols = 3, className }: { cols?: number; className?: string }) {
  const widths = ["w-2/5", "w-1/4", "w-1/6", "w-1/5", "w-1/3"];
  return (
    <div className={cn("flex items-center gap-4 px-4 py-3.5 border-b border-border last:border-0", className)}>
      {Array.from({ length: cols }).map((_, i) => (
        <SkeletonBox key={i} className={cn("h-3", widths[i % widths.length])} />
      ))}
    </div>
  );
}

export function SkeletonCard({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("bg-card border border-border rounded-xl overflow-hidden", className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface-subtle/50">
        <SkeletonBox className="h-3 w-28" />
        <SkeletonBox className="h-3 w-16" />
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonRow key={i} cols={3} />
      ))}
    </div>
  );
}

export function SkeletonStatCards({ count = 4, className }: { count?: number; className?: string }) {
  return (
    <div className={cn("grid gap-3", count <= 2 ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-4", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex flex-col gap-3 bg-card border border-border rounded-xl p-4">
          <SkeletonBox className="h-2.5 w-20" />
          <SkeletonBox className="h-7 w-16" />
          <SkeletonBox className="h-2 w-12" />
        </div>
      ))}
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center py-16 px-6 gap-4 text-center", className)}>
      {icon && (
        <div className="w-12 h-12 rounded-xl bg-surface-subtle border border-border flex items-center justify-center text-text-muted">
          {icon}
        </div>
      )}
      <div className="flex flex-col gap-1">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        {description && <p className="text-xs text-text-muted max-w-xs">{description}</p>}
      </div>
      {action}
    </div>
  );
}

// ── Error banner ──────────────────────────────────────────────────────────────

interface ErrorBannerProps {
  message: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorBanner({ message, onRetry, className }: ErrorBannerProps) {
  return (
    <div className={cn(
      "flex items-center gap-3 px-4 py-3 rounded-lg border",
      "bg-destructive-subtle border-destructive/20 text-destructive",
      className
    )}>
      <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
        <circle cx="8" cy="8" r="6" />
        <path d="M8 5v3.5M8 10v.5" strokeLinecap="round" />
      </svg>
      <p className="text-xs flex-1">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-xs font-medium underline underline-offset-2 hover:no-underline shrink-0"
        >
          Retry
        </button>
      )}
    </div>
  );
}

// ── Page-level loading skeleton ───────────────────────────────────────────────

export function DashboardSkeleton() {
  return (
    <div className="px-6 py-8 max-w-5xl mx-auto flex flex-col gap-6">
      <SkeletonStatCards count={3} />
      <SkeletonCard rows={4} />
    </div>
  );
}

export function ReviewPageSkeleton() {
  return (
    <div className="px-6 py-8 max-w-4xl mx-auto flex flex-col gap-6">
      {/* Stepper skeleton */}
      <div className="flex items-center gap-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-2 flex-1 last:flex-none">
            <SkeletonBox className="w-7 h-7 rounded-full" />
            {i < 5 && <SkeletonBox className="flex-1 h-0.5" />}
          </div>
        ))}
      </div>
      <SkeletonBox className="h-5 w-48" />
      <SkeletonCard rows={5} />
    </div>
  );
}
