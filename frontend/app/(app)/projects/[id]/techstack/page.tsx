"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { ReviewPageSkeleton, ErrorBanner } from "@/components/page-states";
import { getPhasesForRoute, getNextPhaseRoute } from "@/lib/project-phases";
import { cn } from "@/lib/utils";

interface TechItem {
  name: string;
  category: string;
  reason: string;
  approved: boolean;
}

// TODO (Epic 4): fetch from GET /api/v1/projects/{id}/stack
const MOCK_STACK: TechItem[] = [
  { name: "Next.js 14+",          category: "Frontend",    reason: "SSR + App Router matches document's real-time requirements. Team has prior experience.",                    approved: true },
  { name: "FastAPI",              category: "Backend",     reason: "Async Python framework; pairs well with LangChain/LangGraph for the AI pipeline.",                        approved: true },
  { name: "PostgreSQL",          category: "Database",    reason: "Document references ACID compliance requirements. PostgreSQL preferred over SQLite for production scale.", approved: true },
  { name: "ChromaDB",            category: "Vector DB",   reason: "Cosine-distance vector store for RAG retrieval; PersistentClient pattern already established.",           approved: true },
  { name: "LangGraph",           category: "Orchestration", reason: "ReAct agent pattern required for Phases 4–6; SqliteSaver checkpointer for durability.",                  approved: true },
  { name: "Gemini 1.5 Pro",      category: "LLM",         reason: "Primary model via MAIN_LLM_PROVIDER env var; switchable to Anthropic without code changes.",              approved: true },
  { name: "text-embedding-3-small", category: "Embeddings", reason: "1536-dim OpenAI model; locked post-ingestion per ADR-004.",                                             approved: true },
  { name: "GitHub Issues + MCP", category: "Integration", reason: "Replaces Jira per ADR-001. Milestones = Epics, Issues = Tasks.",                                          approved: true },
];

const CATEGORY_COLORS: Record<string, string> = {
  Frontend:      "bg-accent-subtle text-accent-foreground",
  Backend:       "bg-success-subtle text-success",
  Database:      "bg-warning-subtle text-warning",
  "Vector DB":   "bg-destructive-subtle text-destructive",
  Orchestration: "bg-surface-subtle text-text-secondary",
  LLM:           "bg-accent-subtle text-accent-foreground",
  Embeddings:    "bg-success-subtle text-success",
  Integration:   "bg-warning-subtle text-warning",
};

export default function TechStackPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [loading, setLoading]   = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [proceeding, setProceeding] = useState(false);

  // TODO (Epic 4): replace with GET /api/v1/projects/{id}/stack
  useEffect(() => { const t = setTimeout(() => setLoading(false), 500); return () => clearTimeout(t); }, []);

  if (loading) return <ReviewPageSkeleton />;
  if (fetchError) return (
    <div className="px-6 py-8 max-w-4xl mx-auto">
      <ErrorBanner message={fetchError} onRetry={() => { setFetchError(null); setLoading(true); setTimeout(() => setLoading(false), 500); }} />
    </div>
  );

  async function handleProceed() {
    setProceeding(true);
    // TODO (Epic 4): POST /api/v1/projects/{id}/phases/4/start
    await new Promise((res) => setTimeout(res, 800));
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

        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-border bg-surface-subtle/50 flex items-center justify-between">
            <span className="text-xs font-semibold text-text-muted uppercase tracking-wide">
              {MOCK_STACK.length} technologies recommended
            </span>
            <span className="text-xs text-success font-medium">All approved ✓</span>
          </div>

          <div className="divide-y divide-border">
            {MOCK_STACK.map((item) => (
              <div key={item.name} className="flex items-start gap-4 px-4 py-3.5">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="text-sm font-semibold text-foreground">{item.name}</span>
                    <span className={cn("text-[10px] font-medium px-1.5 py-0.5 rounded-full", CATEGORY_COLORS[item.category] ?? "bg-surface-subtle text-text-secondary")}>
                      {item.category}
                    </span>
                  </div>
                  <p className="text-xs text-text-secondary leading-relaxed">{item.reason}</p>
                </div>
                <svg className="w-4 h-4 text-success shrink-0 mt-0.5" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2.5}>
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
              !proceeding ? "bg-primary text-primary-foreground hover:bg-accent-hover" : "bg-muted text-text-muted cursor-not-allowed"
            )}
          >
            {proceeding ? (
              <><svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}><path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" /></svg>Processing…</>
            ) : (
              <>Proceed to Team<svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}><path d="M2 7h10M8 3l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" /></svg></>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
