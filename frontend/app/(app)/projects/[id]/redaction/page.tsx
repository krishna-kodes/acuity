"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { RedactionHighlight } from "@/components/redaction-highlight";
import type { Phase } from "@/components/phase-progress-stepper";
import type { RedactionSpan } from "@/components/redaction-highlight";

const PHASES: Phase[] = [
  { label: "Ingestion",    status: "in_progress" },
  { label: "Refinement",   status: "locked" },
  { label: "Tech Stack",   status: "locked" },
  { label: "Team",         status: "locked" },
  { label: "Estimation",   status: "locked" },
  { label: "Epics & Sync", status: "locked" },
];

// TODO (Epic 4): fetch from GET /api/v1/projects/{id}/tbds and pii_detections
const MOCK_DETECTIONS: RedactionSpan[] = [
  { id: 1,  original: "Sarah Johnson",         type: "Person",       method: "NER",   placeholder: "[PERSON_1]",   confidence: 0.96 },
  { id: 2,  original: "sarah.j@acme.com",      type: "Email",        method: "Regex", placeholder: "[EMAIL_1]",    confidence: 0.99 },
  { id: 3,  original: "+1 (415) 555-0192",     type: "Phone",        method: "Regex", placeholder: "[PHONE_1]",    confidence: 0.98 },
  { id: 4,  original: "Acme Corporation",      type: "Organization", method: "NER",   placeholder: "[ORG_1]",      confidence: 0.91 },
  { id: 5,  original: "David Chen",            type: "Person",       method: "NER",   placeholder: "[PERSON_2]",   confidence: 0.88 },
  { id: 6,  original: "4532 1234 5678 9012",   type: "Credit Card",  method: "Regex", placeholder: "[CARD_1]",     confidence: 0.99 },
  { id: 7,  original: "San Francisco, CA",     type: "Location",     method: "NER",   placeholder: "[LOCATION_1]", confidence: 0.82 },
  { id: 8,  original: "March 15, 2025",        type: "Date",         method: "Regex", placeholder: "[DATE_1]",     confidence: 0.95 },
];

export default function RedactionPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [detections, setDetections] = useState<RedactionSpan[]>(MOCK_DETECTIONS);
  const [proceeding, setProceeding] = useState(false);

  const pendingCount = detections.filter((d) => !d.decision).length;
  const allResolved  = pendingCount === 0;

  function confirm(id: number) {
    setDetections((prev) => prev.map((d) => d.id === id ? { ...d, decision: "confirmed" as const } : d));
  }

  function override(id: number) {
    setDetections((prev) => prev.map((d) => d.id === id ? { ...d, decision: "override" as const } : d));
  }

  function confirmAll() {
    setDetections((prev) => prev.map((d) => d.decision ? d : { ...d, decision: "confirmed" as const }));
  }

  async function handleProceed() {
    setProceeding(true);
    // TODO (Epic 4): PATCH /api/v1/projects/{id}/redaction-decisions then POST /api/v1/projects/{id}/phases/2/start
    await new Promise((res) => setTimeout(res, 800));
    router.push(`/projects/${params.id}/chat`);
  }

  return (
    <div className="px-6 py-8 max-w-4xl mx-auto flex flex-col gap-6">

      {/* Phase stepper */}
      <PhaseProgressStepper phases={PHASES} />

      {/* Content */}
      <div className="flex flex-col gap-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-foreground">PII Redaction Review</h2>
            <p className="text-xs text-text-muted mt-0.5">
              Review each detected item and confirm or override the anonymization before processing begins.
            </p>
          </div>

          {pendingCount > 0 && (
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
