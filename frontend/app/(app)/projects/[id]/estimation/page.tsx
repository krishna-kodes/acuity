"use client";

import { useState, useEffect, use } from "react";
import { useRouter } from "next/navigation";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { MetricsStatCard } from "@/components/metrics-stat-card";
import { getPhasesForRoute, getNextPhaseRoute } from "@/lib/project-phases";
import { cn } from "@/lib/utils";
import { estimateEffort } from "@/lib/api";

interface EpicEstimate {
  title: string;
  estimated_points: number;
  confidence?: number;
}

interface EffortData {
  epics: EpicEstimate[];
  total_points: number;
  total_weeks: number;
  confidence?: number;
}

export default function EstimationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [proceeding, setProceeding] = useState(false);
  const [loading, setLoading] = useState(true);
  const [effort, setEffort] = useState<EffortData | null>(null);

  useEffect(() => {
    estimateEffort(id)
      .then(({ data }) => {
        if (data) setEffort(data as unknown as EffortData);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  async function handleProceed() {
    setProceeding(true);
    await new Promise((res) => setTimeout(res, 800));
    router.push(getNextPhaseRoute("estimation", id));
  }

  const epics = effort?.epics ?? [];
  const overallConfidence = effort?.confidence ?? epics[0]?.confidence;
  const confidenceLabel = overallConfidence != null
    ? `${(overallConfidence * 100).toFixed(0)}%`
    : "—";

  return (
    <div className="px-6 py-8 max-w-4xl mx-auto flex flex-col gap-6">
      <PhaseProgressStepper phases={getPhasesForRoute("estimation")} />

      <div className="flex flex-col gap-4">
        <div>
          <h2 className="text-base font-semibold text-foreground">Effort Estimation</h2>
          <p className="text-xs text-text-muted mt-0.5">
            AI-generated estimates based on requirements complexity and historical project data.
          </p>
        </div>

        {/* Summary stats */}
        <div className="grid grid-cols-3 gap-3">
          <MetricsStatCard label="Story Points" value={loading ? "…" : effort ? String(effort.total_points) : "—"} />
          <MetricsStatCard label="Weeks"         value={loading ? "…" : effort ? `${effort.total_weeks}w` : "—"} />
          <MetricsStatCard label="Confidence"    value={loading ? "…" : confidenceLabel} />
        </div>

        {/* Estimate table */}
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <div className="min-w-[420px]">
              <div className="px-4 py-3 border-b border-border bg-surface-subtle/50 grid grid-cols-12 gap-2 text-[10px] font-semibold uppercase tracking-wide text-text-muted">
                <span className="col-span-7">Epic</span>
                <span className="col-span-2 text-center">Points</span>
                <span className="col-span-3 text-center">Confidence</span>
              </div>

              <div className="divide-y divide-border">
                {loading ? (
                  <div className="px-4 py-6 text-sm text-text-muted text-center">Estimating…</div>
                ) : epics.length === 0 ? (
                  <div className="px-4 py-6 text-sm text-text-muted text-center">No breakdown available yet.</div>
                ) : (
                  epics.map((epic, i) => {
                    const conf = epic.confidence;
                    const confLabel = conf != null ? `${(conf * 100).toFixed(0)}%` : "—";
                    const confColor =
                      conf == null ? "text-text-muted bg-muted"
                      : conf >= 0.75 ? "text-success bg-success-subtle"
                      : conf >= 0.5 ? "text-warning bg-warning-subtle"
                      : "text-destructive bg-destructive-subtle";
                    return (
                      <div key={i} className="grid grid-cols-12 gap-2 px-4 py-3 items-center">
                        <span className="col-span-7 text-sm font-medium text-foreground leading-snug">{epic.title}</span>
                        <span className="col-span-2 text-center text-xs tabular-nums font-mono text-foreground font-semibold">
                          {epic.estimated_points}
                        </span>
                        <span className="col-span-3 flex justify-center">
                          <span className={cn("text-[10px] font-medium px-2 py-0.5 rounded-full", confColor)}>
                            {confLabel}
                          </span>
                        </span>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Totals row */}
              {!loading && effort && (
                <div className="grid grid-cols-12 gap-2 px-4 py-3 border-t border-border bg-surface-subtle/50 items-center">
                  <span className="col-span-7 text-xs font-semibold text-foreground">Total</span>
                  <span className="col-span-2 text-center text-xs font-semibold tabular-nums font-mono text-foreground">
                    {effort.total_points}
                  </span>
                  <span className="col-span-3 text-[11px] text-text-muted text-center">
                    ≈ {effort.total_weeks}w
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end pt-2 border-t border-border">
          <button
            onClick={handleProceed}
            disabled={proceeding}
            className={cn(
              "inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors",
              !proceeding ? "bg-primary text-primary-foreground hover:bg-accent-hover" : "bg-muted text-text-muted cursor-not-allowed"
            )}
          >
            {proceeding ? (
              <><svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}><path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" /></svg>Processing…</>
            ) : (
              <>Generate Epics &amp; Tasks<svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}><path d="M2 7h10M8 3l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" /></svg></>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
