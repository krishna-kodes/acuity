"use client";

import { useState, use } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { RedactionHighlight } from "@/components/redaction-highlight";
import { getPhasesForRoute, getNextPhaseRoute } from "@/lib/project-phases";
import { getRedactionDecisions, patchRedactionDecisions } from "@/lib/api";
import type { RedactionSpan } from "@/components/redaction-highlight";

function mapDetections(raw: Array<{
  id: number;
  text_original: string;
  text_replacement: string;
  pii_type: string;
  detection_method: string;
  confirmed: boolean;
  overridden: boolean;
}>): RedactionSpan[] {
  const TYPE_LABELS: Record<string, string> = {
    EMAIL: "Email", PHONE: "Phone", SSN: "SSN",
    PERSON: "Person", ORG: "Organization", GPE: "Location",
  };
  const METHOD_LABELS: Record<string, string> = { regex: "Regex", ner: "NER" };
  return raw.map((d) => ({
    id: d.id,
    original: d.text_original,
    type: TYPE_LABELS[d.pii_type] ?? d.pii_type,
    method: METHOD_LABELS[d.detection_method] ?? d.detection_method,
    placeholder: d.text_replacement,
    confidence: 0.9,
    decision: d.confirmed ? ("confirmed" as const) : d.overridden ? ("override" as const) : undefined,
  }));
}

export default function RedactionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [localDecisions, setLocalDecisions] = useState<Record<number, "confirmed" | "override">>({});
  const [proceeding, setProceeding] = useState(false);

  const { data: rawDetections, isLoading } = useQuery({
    queryKey: ["redaction-decisions", id],
    queryFn: async () => {
      const { data, error } = await getRedactionDecisions(id);
      if (error) throw new Error(String(error));
      return data ?? [];
    },
  });

  const detections: RedactionSpan[] = mapDetections(rawDetections ?? []).map((d) => ({
    ...d,
    decision: localDecisions[d.id] ?? d.decision,
  }));

  const pendingCount = detections.filter((d) => !d.decision).length;
  const allResolved  = detections.length === 0 || pendingCount === 0;

  function confirm(id: number) {
    setLocalDecisions((prev) => ({ ...prev, [id]: "confirmed" }));
  }

  function override(id: number) {
    setLocalDecisions((prev) => ({ ...prev, [id]: "override" }));
  }

  function confirmAll() {
    const all: Record<number, "confirmed"> = {};
    detections.forEach((d) => { if (!d.decision) all[d.id] = "confirmed"; });
    setLocalDecisions((prev) => ({ ...prev, ...all }));
  }

  async function handleProceed() {
    setProceeding(true);
    try {
      const decisions = detections.map((d) => ({
        detection_id: d.id,
        confirmed: (localDecisions[d.id] ?? d.decision) === "confirmed",
      }));
      if (decisions.length > 0) {
        await patchRedactionDecisions(id, decisions);
      }
    } catch {
      // Non-fatal — proceed anyway even if patch fails
    }
    router.push(getNextPhaseRoute("redaction", id));
  }

  return (
    <div className="px-6 py-8 max-w-4xl mx-auto flex flex-col gap-6">

      {/* Phase stepper */}
      <PhaseProgressStepper phases={getPhasesForRoute("redaction")} />

      {/* Content */}
      <div className="flex flex-col gap-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-foreground">PII Redaction Review</h2>
            <p className="text-xs text-text-muted mt-0.5">
              Review each detected item and confirm or override the anonymization before processing begins.
            </p>
          </div>

          {isLoading && (
            <span className="text-xs text-text-muted">Loading detections…</span>
          )}
          {!isLoading && pendingCount > 0 && (
            <span className="shrink-0 text-xs font-medium text-warning bg-warning-subtle border border-warning/20 px-2 py-1 rounded-full">
              {pendingCount} pending
            </span>
          )}
        </div>

        {/* Detection list */}
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <RedactionHighlight
            detections={detections}
            onConfirm={confirm}
            onOverride={override}
            onConfirmAll={confirmAll}
          />
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-4 text-[11px] text-text-muted">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-destructive-subtle border border-destructive/30 shrink-0" />
            Person / Org
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-warning-subtle border border-warning/30 shrink-0" />
            Email / Phone / URL
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-accent-subtle border border-accent/30 shrink-0" />
            Location
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-surface-subtle border border-border shrink-0" />
            Date / Currency
          </span>
        </div>

        {/* Proceed */}
        <div className="flex items-center justify-between pt-2 border-t border-border">
          <p className="text-xs text-text-muted">
            {allResolved
              ? "All detections resolved. Ready to proceed."
              : `Resolve ${pendingCount} remaining item${pendingCount !== 1 ? "s" : ""} to continue.`}
          </p>
          <button
            onClick={handleProceed}
            disabled={!allResolved || proceeding}
            className={[
              "inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors",
              allResolved && !proceeding
                ? "bg-primary text-primary-foreground hover:bg-accent-hover"
                : "bg-muted text-text-muted cursor-not-allowed",
            ].join(" ")}
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
                Proceed to Refinement
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
