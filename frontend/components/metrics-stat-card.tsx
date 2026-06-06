import { cn } from "@/lib/utils";

interface MetricsStatCardProps {
  label: string;
  value: string | number;
  unit?: string;
  delta?: { value: string; direction: "up" | "down" | "neutral" };
  icon?: React.ReactNode;
  className?: string;
}

function DeltaBadge({ delta }: { delta: NonNullable<MetricsStatCardProps["delta"]> }) {
  const color =
    delta.direction === "up"
      ? "text-success"
      : delta.direction === "down"
      ? "text-destructive"
      : "text-text-muted";

  const arrow =
    delta.direction === "up" ? "↑" : delta.direction === "down" ? "↓" : "–";

  return (
    <span className={cn("text-xs font-medium", color)}>
      {arrow} {delta.value}
    </span>
  );
}

export function MetricsStatCard({
  label,
  value,
  unit,
  delta,
  icon,
  className,
}: MetricsStatCardProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 bg-card border border-border rounded-xl p-4",
        className
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          {label}
        </span>
        {icon && (
          <div className="w-7 h-7 rounded-lg bg-accent-subtle flex items-center justify-center text-accent-foreground">
            {icon}
          </div>
        )}
      </div>

      <div className="flex items-end gap-1.5">
        <span className="text-2xl font-bold text-foreground tabular-nums leading-none">
          {value}
        </span>
        {unit && (
          <span className="text-sm text-text-muted mb-0.5">{unit}</span>
        )}
      </div>

      {delta && <DeltaBadge delta={delta} />}
    </div>
  );
}
