import { cn } from "@/lib/utils";

export type PhaseStatus = "complete" | "in_progress" | "locked";

export interface Phase {
  label: string;
  status: PhaseStatus;
}

interface PhaseProgressStepperProps {
  phases: Phase[];
  onProceed?: () => void;
  onRerun?: () => void;
  className?: string;
}

const PHASE_LABELS = [
  "Ingestion",
  "Refinement",
  "Tech Stack",
  "Team",
  "Estimation",
  "Epics & Sync",
];

function StepIcon({ status }: { status: PhaseStatus }) {
  if (status === "complete") {
    return (
      <svg
        className="w-3.5 h-3.5"
        fill="none"
        viewBox="0 0 14 14"
        stroke="currentColor"
        strokeWidth={2.5}
      >
        <polyline points="2,7 5.5,10.5 12,3.5" />
      </svg>
    );
  }
  if (status === "in_progress") {
    return <span className="w-2 h-2 rounded-full bg-current" />;
  }
  return null;
}

export function PhaseProgressStepper({
  phases,
  onProceed,
  onRerun,
  className,
}: PhaseProgressStepperProps) {
  const activeIdx = phases.findIndex((p) => p.status === "in_progress");

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {/* Step track — horizontal scroll on very small screens */}
      <div className="flex items-center gap-0 overflow-x-auto pb-1 scrollbar-none">
        {phases.map((phase, i) => {
          const isLast = i === phases.length - 1;
          const isComplete = phase.status === "complete";
          const isActive = phase.status === "in_progress";
          const isLocked = phase.status === "locked";

          return (
            <div key={i} className="flex items-center flex-1 last:flex-none">
              {/* Circle */}
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={cn(
                    "w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold border-2 transition-colors",
                    isComplete &&
                      "bg-primary border-primary text-primary-foreground",
                    isActive &&
                      "bg-primary border-primary text-primary-foreground ring-4 ring-primary/20",
                    isLocked &&
                      "bg-background border-border text-text-muted"
                  )}
                >
                  {isComplete || isActive ? (
                    <StepIcon status={phase.status} />
                  ) : (
                    <span className="text-[10px]">{i + 1}</span>
                  )}
                </div>
                <span
                  className={cn(
                    "text-[10px] font-medium whitespace-nowrap",
                    isComplete && "text-primary",
                    isActive && "text-primary font-semibold",
                    isLocked && "text-text-muted"
                  )}
                >
                  {phase.label ?? PHASE_LABELS[i]}
                </span>
              </div>

              {/* Connector line */}
              {!isLast && (
                <div
                  className={cn(
                    "flex-1 h-0.5 mx-1 mb-5",
                    isComplete ? "bg-primary" : "bg-border"
                  )}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Actions */}
      {(onProceed || onRerun) && (
        <div className="flex items-center gap-2 pt-1">
          {onProceed && activeIdx !== -1 && (
            <button
              onClick={onProceed}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-accent-hover transition-colors"
            >
              Proceed
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}>
                <path d="M3 7h8M8 4l3 3-3 3" />
              </svg>
            </button>
          )}
          {onRerun && (
            <button
              onClick={onRerun}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border text-foreground text-sm font-medium hover:bg-secondary transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}>
                <path d="M2 7a5 5 0 1 0 1.5-3.5" />
                <path d="M2 3.5V7h3.5" />
              </svg>
              Re-run Phase
            </button>
          )}
        </div>
      )}
    </div>
  );
}
