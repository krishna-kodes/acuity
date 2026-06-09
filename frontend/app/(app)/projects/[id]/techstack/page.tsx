"use client";

import { useState, useEffect, useRef, use } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { getPhasesForRoute, getNextPhaseRoute } from "@/lib/project-phases";
import { getStack, suggestStackStream } from "@/lib/api";
import type { TechStackData } from "@/lib/api";
import { cn } from "@/lib/utils";

interface TechItem {
  name: string;
  category: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  Frontend:       "bg-accent-subtle text-accent-foreground",
  Backend:        "bg-success-subtle text-success",
  Database:       "bg-warning-subtle text-warning",
  Infrastructure: "bg-destructive-subtle text-destructive",
};

function mapStackToItems(data: Partial<TechStackData>): TechItem[] {
  const entries: [string, string[]][] = [
    ["Frontend",       data.frontend       ?? []],
    ["Backend",        data.backend        ?? []],
    ["Database",       data.database       ?? []],
    ["Infrastructure", data.infra          ?? []],
  ];
  return entries.flatMap(([category, names]) =>
    names.map((name) => ({ name, category }))
  );
}

type StackStatus = "idle" | "started" | "generating" | "done";

const CATEGORY_LABELS: Record<string, string> = {
  frontend: "Frontend",
  backend: "Backend",
  database: "Database",
  infra: "Infrastructure",
  rationale: "Rationale",
};

export default function TechStackPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [proceeding, setProceeding] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [stackStatus, setStackStatus] = useState<StackStatus>("idle");
  const [completedCount, setCompletedCount] = useState(0);
  const [currentCategory, setCurrentCategory] = useState("");
  const [stack, setStack] = useState<Partial<TechStackData>>({});
  // Prevents React StrictMode double-fire from triggering two LLM calls
  const stackFiredRef = useRef(false);

  async function runStackGeneration(isCancelled?: () => boolean, force = false) {
    setGenerating(true);
    setStackStatus("started");
    setStack({});
    setCompletedCount(0);
    setCurrentCategory("");
    try {
      await suggestStackStream(
        id,
        (_message) => {
          if (!isCancelled?.()) setStackStatus("started");
        },
        (key, items) => {
          if (!isCancelled?.()) {
            setStack((prev) => ({ ...prev, [key]: items }));
            setCurrentCategory(CATEGORY_LABELS[key] ?? key);
            setCompletedCount((n) => n + 1);
            setStackStatus("generating");
          }
        },
        (text) => {
          if (!isCancelled?.()) {
            setStack((prev) => ({ ...prev, rationale: text }));
            setCompletedCount((n) => n + 1);
          }
        },
        (fullStack) => {
          if (!isCancelled?.()) {
            setStack(fullStack);
            setStackStatus("done");
          }
        },
        force,
      );
    } catch {
      if (!isCancelled?.()) {
        toast.error("Tech stack generation failed — try again");
        setStackStatus("idle");
      }
    } finally {
      if (!isCancelled?.()) setGenerating(false);
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await getStack(id);
        if (cancelled) return;
        if (data) {
          setStack(data);
          setStackStatus("done");
          return;
        }
      } catch {
        if (cancelled) return;
      }
      if (stackFiredRef.current) return;
      stackFiredRef.current = true;
      await runStackGeneration(() => cancelled);
    }

    load();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const items = mapStackToItems(stack);
  const totalCount = items.length;

  function handleProceed() {
    setProceeding(true);
    router.push(getNextPhaseRoute("techstack", id));
  }

  return (
    <div className="px-6 py-8 max-w-4xl mx-auto flex flex-col gap-6">
      <PhaseProgressStepper phases={getPhasesForRoute("techstack")} />

      <div className="flex flex-col gap-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-base font-semibold text-foreground">Tech Stack Suggestion</h2>
            <p className="text-xs text-text-muted mt-0.5">
              AI-recommended technologies based on your requirements and approved technology list.
            </p>
          </div>
          <button
            onClick={() => {
              stackFiredRef.current = true;
              runStackGeneration(undefined, true);
            }}
            disabled={generating}
            className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-border bg-card hover:bg-surface-subtle transition-colors disabled:opacity-50"
          >
            {generating ? (
              <>
                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                  <path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" />
                </svg>
                Generating…
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                  <path d="M13 6A6 6 0 1 0 8 14" strokeLinecap="round" />
                  <path d="M13 2v4h-4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Regenerate
              </>
            )}
          </button>
        </div>

        {/* Progress bar — visible during and after generation */}
        {stackStatus !== "idle" && (
          <div className="flex flex-col gap-2 bg-card border border-border rounded-xl px-4 py-3">
            <div className="flex items-center justify-between">
              <span
                className={cn(
                  "text-xs font-medium",
                  stackStatus === "started" && "text-amber-600",
                  stackStatus === "generating" && "text-blue-600 animate-pulse",
                  stackStatus === "done" && "text-green-600",
                )}
              >
                {stackStatus === "started" && "Analyzing requirements…"}
                {stackStatus === "generating" &&
                  `Generating ${currentCategory}… (${completedCount}/5)`}
                {stackStatus === "done" &&
                  `${totalCount} technolog${totalCount !== 1 ? "ies" : "y"} selected ✓`}
              </span>
              {stackStatus === "done" && (
                <svg
                  className="w-4 h-4 text-green-500"
                  fill="none"
                  viewBox="0 0 16 16"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path d="M3 8l4 4 6-7" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </div>
            <div className="w-full h-1.5 bg-border rounded-full overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-500",
                  stackStatus === "done" ? "bg-green-500" : "bg-primary",
                )}
                style={{
                  width:
                    stackStatus === "started"
                      ? "5%"
                      : stackStatus === "done"
                        ? "100%"
                        : `${Math.round((completedCount / 5) * 95)}%`,
                }}
              />
            </div>
          </div>
        )}

        {stack.rationale && (
          <div className="bg-surface-subtle border border-border rounded-lg px-4 py-3">
            <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-1">Rationale</p>
            <p className="text-sm text-text-secondary leading-relaxed">{stack.rationale}</p>
          </div>
        )}

        {items.length > 0 && (
          <div className="bg-card border border-border rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-border bg-surface-subtle/50 flex items-center justify-between">
              <span className="text-xs font-semibold text-text-muted uppercase tracking-wide">
                {items.length} technolog{items.length !== 1 ? "ies" : "y"} recommended
              </span>
              <span className="text-xs text-text-muted font-medium">From approved list</span>
            </div>

            <div className="divide-y divide-border">
              {items.map((item) => (
                <div key={`${item.category}-${item.name}`} className="flex items-center gap-4 px-4 py-3.5">
                  <div className="flex-1 min-w-0 flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-foreground">{item.name}</span>
                    <span className={cn(
                      "text-[10px] font-medium px-1.5 py-0.5 rounded-full",
                      CATEGORY_COLORS[item.category] ?? "bg-surface-subtle text-text-secondary"
                    )}>
                      {item.category}
                    </span>
                  </div>
                  <svg className="w-4 h-4 text-success shrink-0" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2.5}>
                    <polyline points="2.5,8 6,11.5 13.5,4" />
                  </svg>
                </div>
              ))}
            </div>
          </div>
        )}

        {stackStatus === "done" && (
          <div className="flex items-center justify-end pt-2 border-t border-border">
            <button
              onClick={handleProceed}
              disabled={proceeding}
              className={cn(
                "inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors",
                !proceeding
                  ? "bg-primary text-primary-foreground hover:bg-accent-hover"
                  : "bg-muted text-text-muted cursor-not-allowed"
              )}
            >
              {proceeding ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                    <path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" />
                  </svg>
                  Processing…
                </>
              ) : (
                <>
                  Proceed to Team
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}>
                    <path d="M2 7h10M8 3l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
