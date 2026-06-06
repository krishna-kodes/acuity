"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { MetricsStatCard } from "@/components/metrics-stat-card";
import { cn } from "@/lib/utils";
import type { Phase } from "@/components/phase-progress-stepper";

const PHASES: Phase[] = [
  { label: "Ingestion",    status: "complete" },
  { label: "Refinement",   status: "complete" },
  { label: "Tech Stack",   status: "complete" },
  { label: "Team",         status: "complete" },
  { label: "Estimation",   status: "in_progress" },
  { label: "Epics & Sync", status: "locked" },
];

interface EstimateRow {
  area: string;
  low: number;
  mid: number;
  high: number;
  confidence: "high" | "medium" | "low";
  notes: string;
}

// TODO (Epic 4): fetch from GET /api/v1/projects/{id}/estimate
const MOCK_ESTIMATES: EstimateRow[] = [
  { area: "Document Ingestion & RAG",    low: 5,  mid: 8,  high: 12, confidence: "high",   notes: "Standard chunking pipeline; ChromaDB integration already specified." },
  { area: "Chat & Refinement (Phase 2)", low: 6,  mid: 10, high: 14, confidence: "medium", notes: "TBD detection complexity depends on LLM reliability; build in buffer." },
  { area: "Tech Stack Suggestion",       low: 3,  mid: 5,  high: 7,  confidence: "high",   notes: "Tool-calling pattern is well-defined; approved_technologies table is the bottleneck." },
  { area: "Team Suggestion Engine",      low: 4,  mid: 6,  high: 9,  confidence: "medium", notes: "Skills matcher logic may require iteration; availability data quality unknown." },
  { area: "Effort Estimation (LLM)",     low: 3,  mid: 5,  high: 8,  confidence: "medium", notes: "Historical project retrieval quality drives accuracy; needs real seed data." },
  { area: "Epic & Task Generation",      low: 4,  mid: 7,  high: 10, confidence: "high",   notes: "Pydantic structured output is reliable; GitHub MCP integration adds 1–2 days." },
  { area: "Eval Layer",                  low: 5,  mid: 8,  high: 12, confidence: "low",    notes: "Highly variable — depends on baseline pass rates and grader implementation time." },
  { area: "DevOps & CI",                 low: 2,  mid: 3,  high: 5,  confidence: "high",   notes: "Ruff, mypy, pytest already scaffolded. GitHub Actions CI already configured." },
];

const CONFIDENCE_STYLES: Record<EstimateRow["confidence"], string> = {
  high:   "text-success bg-success-subtle",
  medium: "text-warning bg-warning-subtle",
  low:    "text-destructive bg-destructive-subtle",
};

const totalMid  = MOCK_ESTIMATES.reduce((s, r) => s + r.mid, 0);
const totalLow  = MOCK_ESTIMATES.reduce((s, r) => s + r.low, 0);
const totalHigh = MOCK_ESTIMATES.reduce((s, r) => s + r.high, 0);

export default function EstimationPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [proceeding, setProceeding] = useState(false);

  async function handleProceed() {
    setProceeding(true);
    // TODO (Epic 4): POST /api/v1/projects/{id}/phases/6/start
    await new Promise((res) => setTimeout(res, 800));
    router.push(`/projects/${params.id}/epics`);
  }

  return (
    <div className="px-6 py-8 max-w-4xl mx-auto flex flex-col gap-6">
      <PhaseProgressStepper phases={PHASES} />

      <div className="flex flex-col gap-4">
        <div>
          <h2 className="text-base font-semibold text-foreground">Effort Estimation</h2>
          <p className="text-xs text-text-muted mt-0.5">
            AI-generated estimates based on requirements complexity and historical project data.
            Ranges show optimistic / most-likely / pessimistic days.
          </p>
        </div>

        {/* Summary stats */}
        <div className="grid grid-cols-3 gap-3">
          <MetricsStatCard label="Optimistic"   value={`${totalLow}d`}  />
          <MetricsStatCard label="Most Likely"  value={`${totalMid}d`}  />
          <MetricsStatCard label="Pessimistic"  value={`${totalHigh}d`} />
        </div>

        {/* Estimate table */}
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <div className="min-w-[520px]">
              <div className="px-4 py-3 border-b border-border bg-surface-subtle/50 grid grid-cols-12 gap-2 text-[10px] font-semibold uppercase tracking-wide text-text-muted">
                <span className="col-span-4">Area</span>
                <span className="col-span-3 text-center">Low / Mid / High (days)</span>
                <span className="col-span-2 text-center">Confidence</span>
                <span className="col-span-3 hidden sm:block">Notes</span>
              </div>

              <div className="divide-y divide-border">
                {MOCK_ESTIMATES.map((row) => (
                  <div key={row.area} className="grid grid-cols-12 gap-2 px-4 py-3 items-start">
                    <span className="col-span-4 text-sm font-medium text-foreground leading-snug">{row.area}</span>
                    <span className="col-span-3 text-center text-xs text-text-secondary tabular-nums font-mono">
                      {row.low} / <strong className="text-foreground">{row.mid}</strong> / {row.high}
                    </span>
                    <span className="col-span-2 flex justify-center">
                      <span className={cn("text-[10px] font-medium px-2 py-0.5 rounded-full capitalize", CONFIDENCE_STYLES[row.confidence])}>
                        {row.confidence}
                      </span>
                    </span>
                    <span className="col-span-3 text-[11px] text-text-secondary leading-relaxed hidden sm:block">{row.notes}</span>
                  </div>
                ))}
              </div>

              {/* Totals row */}
              <div className="grid grid-cols-12 gap-2 px-4 py-3 border-t border-border bg-surface-subtle/50 items-center">
                <span className="col-span-4 text-xs font-semibold text-foreground">Total</span>
                <span className="col-span-3 text-center text-xs font-semibold tabular-nums font-mono text-foreground">
                  {totalLow} / {totalMid} / {totalHigh}
                </span>
                <span className="col-span-5 text-[11px] text-text-muted hidden sm:block">
                  ≈ {Math.round(totalMid / 5)} weeks at full team capacity
                </span>
              </div>
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
