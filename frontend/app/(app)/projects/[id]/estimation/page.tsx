"use client";

import { useState, useEffect, useRef, use } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { MetricsStatCard } from "@/components/metrics-stat-card";
import { getPhasesForRoute, getNextPhaseRoute } from "@/lib/project-phases";
import { cn } from "@/lib/utils";
import { estimateEffortStream, getModules } from "@/lib/api";
import type { Module } from "@/lib/api";

interface EpicEstimate {
  title: string;
  estimated_points: number;
  confidence?: number;
}

interface SummaryData {
  total_points: number;
  total_weeks: number;
  confidence: number;
  reasoning: string;
}

type EstimateStatus = "idle" | "fetching" | "computing" | "done";

export default function EstimationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [proceeding, setProceeding] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [estimateStatus, setEstimateStatus] = useState<EstimateStatus>("idle");
  const [completedCount, setCompletedCount] = useState(0);
  const [streamedEpics, setStreamedEpics] = useState<EpicEstimate[]>([]);
  const [summaryData, setSummaryData] = useState<SummaryData | null>(null);
  const [modules, setModules] = useState<Module[]>([]);
  const estimationFiredRef = useRef(false);

  async function runEstimation(isCancelled?: () => boolean, force = false) {
    setGenerating(true);
    setEstimateStatus("fetching");
    setStreamedEpics([]);
    setSummaryData(null);
    setCompletedCount(0);
    try {
      await estimateEffortStream(
        id,
        {
          onStatus: (message) => {
            if (isCancelled?.()) return;
            setEstimateStatus(message.toLowerCase().includes("fetching") ? "fetching" : "computing");
          },
          onEpic: (epic) => {
            if (isCancelled?.()) return;
            setStreamedEpics((prev) => [...prev, epic]);
            setCompletedCount((n) => n + 1);
            setEstimateStatus("computing");
          },
          onSummary: (data) => {
            if (isCancelled?.()) return;
            setSummaryData(data);
          },
          onDone: (data) => {
            if (isCancelled?.()) return;
            setStreamedEpics(data.epics);
            setSummaryData((prev) => prev ?? { total_points: data.total_points, total_weeks: data.total_weeks, confidence: 0, reasoning: "" });
            setEstimateStatus("done");
          },
        },
        force,
      );
    } catch {
      if (!isCancelled?.()) {
        toast.error("Effort estimation failed — try again");
        setEstimateStatus("idle");
      }
    } finally {
      if (!isCancelled?.()) setGenerating(false);
    }
  }

  useEffect(() => {
    if (estimationFiredRef.current) return;
    estimationFiredRef.current = true;
    runEstimation();
    getModules(id)
      .then((data) => { setModules(data.modules); })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleProceed() {
    setProceeding(true);
    await new Promise((res) => setTimeout(res, 800));
    router.push(getNextPhaseRoute("estimation", id));
  }

  const progressWidth =
    estimateStatus === "idle" ? "0%"
    : estimateStatus === "fetching" ? "10%"
    : estimateStatus === "done" ? "100%"
    : `${Math.min(10 + completedCount * 8, 90)}%`;

  const confidenceLabel = summaryData?.confidence != null
    ? `${(summaryData.confidence * 100).toFixed(0)}%`
    : "—";

  return (
    <div className="px-6 py-8 max-w-4xl mx-auto flex flex-col gap-6">
      <PhaseProgressStepper phases={getPhasesForRoute("estimation")} />

      <div className="flex flex-col gap-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-base font-semibold text-foreground">Effort Estimation</h2>
            <p className="text-xs text-text-muted mt-0.5">
              AI-generated estimates based on requirements complexity and historical project data.
            </p>
          </div>
          <button
            onClick={() => {
              estimationFiredRef.current = true;
              runEstimation(undefined, true);
            }}
            disabled={generating}
            className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-border bg-card hover:bg-surface-subtle transition-colors disabled:opacity-50"
          >
            {generating ? (
              <>
                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                  <path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" />
                </svg>
                Estimating…
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                  <path d="M13 6A6 6 0 1 0 8 14" strokeLinecap="round" />
                  <path d="M13 2v4h-4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Re-run Estimation
              </>
            )}
          </button>
        </div>

        {/* Progress bar */}
        {estimateStatus !== "idle" && (
          <div className="flex flex-col gap-2 bg-card border border-border rounded-xl px-4 py-3">
            <div className="flex items-center justify-between">
              <span
                className={cn(
                  "text-xs font-medium",
                  estimateStatus === "fetching" && "text-amber-600",
                  estimateStatus === "computing" && "text-blue-600 animate-pulse",
                  estimateStatus === "done" && "text-green-600",
                )}
              >
                {estimateStatus === "fetching" && "Fetching historical projects…"}
                {estimateStatus === "computing" &&
                  `Estimating epics… (${completedCount} found)`}
                {estimateStatus === "done" &&
                  `${summaryData?.total_points ?? 0} story points across ${streamedEpics.length} epic${streamedEpics.length !== 1 ? "s" : ""} ✓`}
              </span>
              {estimateStatus === "done" && (
                <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                  <path d="M3 8l4 4 6-7" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </div>
            <div className="w-full h-1.5 bg-border rounded-full overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-500",
                  estimateStatus === "done" ? "bg-green-500" : "bg-primary",
                )}
                style={{ width: progressWidth }}
              />
            </div>
          </div>
        )}

        {/* Summary stats */}
        <div className="grid grid-cols-3 gap-3">
          <MetricsStatCard
            label="Story Points"
            value={estimateStatus === "idle" ? "—" : summaryData ? String(summaryData.total_points) : "…"}
          />
          <MetricsStatCard
            label="Weeks"
            value={estimateStatus === "idle" ? "—" : summaryData ? `${summaryData.total_weeks}w` : "…"}
          />
          <MetricsStatCard
            label="Confidence"
            value={estimateStatus === "idle" ? "—" : summaryData ? confidenceLabel : "…"}
          />
        </div>

        {/* Estimate table */}
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <div className="min-w-[420px]">
              <div className="px-4 py-3 border-b border-border bg-surface-subtle/50 grid grid-cols-12 gap-2 text-[10px] font-semibold uppercase tracking-wide text-text-muted">
                <span className="col-span-9">Epic</span>
                <span className="col-span-3 text-center">Points</span>
              </div>

              <div className="divide-y divide-border">
                {estimateStatus === "idle" || (estimateStatus === "fetching" && streamedEpics.length === 0) ? (
                  <div className="px-4 py-6 text-sm text-text-muted text-center">
                    {estimateStatus === "idle" ? "No breakdown available yet." : "Fetching historical projects…"}
                  </div>
                ) : streamedEpics.length === 0 && estimateStatus === "computing" ? (
                  <div className="px-4 py-6 text-sm text-text-muted text-center">Estimating epics…</div>
                ) : (
                  streamedEpics.map((epic, i) => (
                    <div key={i} className="grid grid-cols-12 gap-2 px-4 py-3 items-center">
                      <span className="col-span-9 text-sm font-medium text-foreground leading-snug">{epic.title}</span>
                      <span className="col-span-3 text-center text-xs tabular-nums font-mono text-foreground font-semibold">
                        {epic.estimated_points}
                      </span>
                    </div>
                  ))
                )}
              </div>

              {estimateStatus === "done" && summaryData && (
                <div className="grid grid-cols-12 gap-2 px-4 py-3 border-t border-border bg-surface-subtle/50 items-center">
                  <span className="col-span-9 text-xs font-semibold text-foreground">Total</span>
                  <span className="col-span-3 text-center text-xs font-semibold tabular-nums font-mono text-foreground">
                    {summaryData.total_points}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Modules breakdown */}
        {modules.length > 0 && (
          <div className="flex flex-col gap-2">
            <p className="text-xs font-semibold text-text-muted uppercase tracking-wide">Work Modules</p>
            <div className="flex flex-wrap gap-2">
              {modules.map((m, i) => (
                <span
                  key={`${m.id}-${i}`}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-medium bg-surface-subtle text-text-secondary border-border"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-primary/60 shrink-0" />
                  <span className="font-semibold text-text-muted">{m.label}</span>
                  <span className="text-foreground">{m.title}</span>
                </span>
              ))}
            </div>
          </div>
        )}

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
