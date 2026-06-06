"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { ReviewPageSkeleton, ErrorBanner } from "@/components/page-states";
import { getPhasesForRoute, getNextPhaseRoute } from "@/lib/project-phases";
import { suggestStack } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useState } from "react";

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

function mapStackToItems(data: {
  frontend?: string[];
  backend?: string[];
  database?: string[];
  infra?: string[];
}): TechItem[] {
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

export default function TechStackPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [proceeding, setProceeding] = useState(false);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["techstack", params.id],
    queryFn: async () => {
      const { data, error } = await suggestStack(params.id);
      if (error) throw new Error(String(error));
      return data;
    },
  });

  if (isLoading) return <ReviewPageSkeleton />;
  if (isError) return (
    <div className="px-6 py-8 max-w-4xl mx-auto">
      <ErrorBanner
        message={error instanceof Error ? error.message : "Failed to load tech stack"}
        onRetry={() => refetch()}
      />
    </div>
  );

  const items = mapStackToItems(data ?? {});

  function handleProceed() {
    setProceeding(true);
    router.push(getNextPhaseRoute("techstack", params.id));
  }

  return (
    <div className="px-6 py-8 max-w-4xl mx-auto flex flex-col gap-6">
      <PhaseProgressStepper phases={getPhasesForRoute("techstack")} />

      <div className="flex flex-col gap-4">
        <div>
          <h2 className="text-base font-semibold text-foreground">Tech Stack Suggestion</h2>
          <p className="text-xs text-text-muted mt-0.5">
            AI-recommended technologies based on your requirements and approved technology list.
          </p>
        </div>

        {data?.rationale && (
          <div className="bg-surface-subtle border border-border rounded-lg px-4 py-3">
            <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-1">Rationale</p>
            <p className="text-sm text-text-secondary leading-relaxed">{data.rationale}</p>
          </div>
        )}

        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-border bg-surface-subtle/50 flex items-center justify-between">
            <span className="text-xs font-semibold text-text-muted uppercase tracking-wide">
              {items.length} technologies recommended
            </span>
            <span className="text-xs text-success font-medium">All approved ✓</span>
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
      </div>
    </div>
  );
}
