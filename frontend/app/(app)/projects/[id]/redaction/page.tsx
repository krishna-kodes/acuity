"use client";

import { useState, useEffect, use } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { RedactionHighlight } from "@/components/redaction-highlight";
import { getPhasesForRoute, getNextPhaseRoute } from "@/lib/project-phases";
import {
  getRedactionDecisions,
  patchRedactionDecisions,
  piiLlmFilter,
  getDocumentStatus,
} from "@/lib/api";
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
    confidence: d.detection_method === "regex" ? 1.0 : 0.85,
    decision: d.confirmed ? ("confirmed" as const) : d.overridden ? ("override" as const) : undefined,
  }));
}

export default function RedactionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();
  const [localDecisions, setLocalDecisions] = useState<Record<number, "confirmed" | "override">>({});
  const [proceeding, setProceeding] = useState(false);
  const [llmFiltered, setLlmFiltered] = useState(false);
  const [llmFiltering, setLlmFiltering] = useState(false);

  const { data: rawDetections, isLoading } = useQuery({
    queryKey: ["redaction-decisions", id],
    queryFn: async () => {
      const { data, error } = await getRedactionDecisions(id);
      if (error) throw new Error(String(error));
      return data ?? [];
    },
  });

  // Toast while initial fetch runs
  useEffect(() => {
    if (!isLoading) return;
    const tid = toast.loading("Scanning document for personal data…");
    return () => { toast.dismiss(tid); };
  }, [isLoading]);

  async function handleLlmFilter() {
    setLlmFiltering(true);
    const tid = toast.loading("Filtering AI-detected names with LLM…");
    try {
      const result = await piiLlmFilter(id);
      toast.dismiss(tid);
      if (result.pruned > 0) {
        toast.success(
          `Removed ${result.pruned} false positive${result.pruned !== 1 ? "s" : ""} — ${result.kept} real name${result.kept !== 1 ? "s" : ""}/org${result.kept !== 1 ? "s" : ""} kept`
        );
      } else {
        toast.success("All NER detections verified");
      }
      await queryClient.invalidateQueries({ queryKey: ["redaction-decisions", id] });
    } catch {
      toast.dismiss(tid);
      toast.error("AI filter unavailable — showing all detections");
    } finally {
      setLlmFiltering(false);
      setLlmFiltered(true);
    }
  }

  // Auto-trigger LLM filter once data loaded, if NER items exist
  useEffect(() => {
    if (!rawDetections || llmFiltered || llmFiltering) return;
    const hasNer = rawDetections.some((d) => d.detection_method === "ner");
    if (hasNer) {
      handleLlmFilter();
    } else {
      setLlmFiltered(true);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawDetections]);

  const detections: RedactionSpan[] = mapDetections(rawDetections ?? []).map((d) => ({
    ...d,
    decision: localDecisions[d.id] ?? d.decision,
  }));

  const pendingCount = detections.filter((d) => !d.decision).length;
  const allResolved  = detections.length === 0 || pendingCount === 0;

  function confirm(detId: number) {
    setLocalDecisions((prev) => ({ ...prev, [detId]: "confirmed" }));
  }

  function override(detId: number) {
    setLocalDecisions((prev) => ({ ...prev, [detId]: "override" }));
  }

  function confirmAll() {
    const all: Record<number, "confirmed"> = {};
    detections.forEach((d) => { if (!d.decision) all[d.id] = "confirmed"; });
    setLocalDecisions((prev) => ({ ...prev, ...all }));
  }

  function undo(detId: number) {
    setLocalDecisions((prev) => {
      const next = { ...prev };
      delete next[detId];
      return next;
    });
  }

  function confirmSelected(ids: number[]) {
    setLocalDecisions((prev) => {
      const next = { ...prev };
      ids.forEach((i) => (next[i] = "confirmed"));
      return next;
    });
  }

  function overrideSelected(ids: number[]) {
    setLocalDecisions((prev) => {
      const next = { ...prev };
      ids.forEach((i) => (next[i] = "override"));
      return next;
    });
  }

  async function handleProceed() {
    setProceeding(true);
    const tid = toast.loading("Applying redactions…");
    try {
      const decisions = detections.map((d) => ({
        detection_id: d.id,
        confirmed: (localDecisions[d.id] ?? d.decision) === "confirmed",
      }));
      if (decisions.length > 0) {
        await patchRedactionDecisions(id, decisions);
      }
    } catch {
      // Non-fatal — proceed to polling anyway
    }

    // Poll until document.status === "ready" (max 30s)
    const deadline = Date.now() + 30_000;
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const s = await getDocumentStatus(id);
        if (s.status === "ready" || s.project_phase !== "redaction") break;
      } catch {
        break;
      }
    }

    toast.dismiss(tid);
    toast.success("Redactions applied — proceeding to Refinement");
    router.push(getNextPhaseRoute("redaction", id));
  }

  const showLoader = isLoading || llmFiltering;

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

          {!showLoader && pendingCount > 0 && (
            <span className="shrink-0 text-xs font-medium text-warning bg-warning-subtle border border-warning/20 px-2 py-1 rounded-full">
              {pendingCount} pending
            </span>
          )}
        </div>

        {/* Detection list — loading overlay while scanning/filtering */}
        {showLoader ? (
          <div className="bg-card border border-border rounded-xl py-12 flex flex-col items-center gap-3">
            <svg className="w-6 h-6 animate-spin text-primary" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
              <path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" />
            </svg>
            <p className="text-xs text-text-muted">
              {isLoading ? "Loading detections…" : "Filtering with AI…"}
            </p>
          </div>
        ) : (
          <div className="bg-card border border-border rounded-xl overflow-hidden">
            <RedactionHighlight
              detections={detections}
              onConfirm={confirm}
              onOverride={override}
              onConfirmAll={confirmAll}
              onUndo={undo}
              onConfirmSelected={confirmSelected}
              onOverrideSelected={overrideSelected}
            />
          </div>
        )}

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
            {showLoader
              ? "Analyzing document…"
              : allResolved
              ? "All detections resolved. Ready to proceed."
              : `Resolve ${pendingCount} remaining item${pendingCount !== 1 ? "s" : ""} to continue.`}
          </p>
          <button
            onClick={handleProceed}
            disabled={!allResolved || proceeding || showLoader}
            className={[
              "inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors",
              allResolved && !proceeding && !showLoader
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
