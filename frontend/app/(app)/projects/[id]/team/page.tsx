"use client";

import { useState, useEffect, use } from "react";
import { useRouter } from "next/navigation";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { ReviewPageSkeleton, ErrorBanner } from "@/components/page-states";
import { getPhasesForRoute, getNextPhaseRoute } from "@/lib/project-phases";
import { cn } from "@/lib/utils";

interface TeamMember {
  name: string;
  role: string;
  skills: string[];
  availability: number; // percent
  matchScore: number;   // 0-1
}

// TODO (Epic 4): fetch from GET /api/v1/projects/{id}/team
const MOCK_TEAM: TeamMember[] = [
  { name: "Alex Rivera",   role: "Tech Lead",          skills: ["Python", "FastAPI", "LangChain", "System Design"], availability: 80, matchScore: 0.96 },
  { name: "Priya Nair",    role: "ML Engineer",        skills: ["LangGraph", "ChromaDB", "Embeddings", "RAG"],      availability: 100, matchScore: 0.94 },
  { name: "Jordan Kim",    role: "Frontend Engineer",  skills: ["Next.js", "TypeScript", "Tailwind", "React"],      availability: 100, matchScore: 0.91 },
  { name: "Sam Okonkwo",   role: "Backend Engineer",   skills: ["FastAPI", "SQLAlchemy", "Alembic", "PostgreSQL"],  availability: 60,  matchScore: 0.88 },
  { name: "Taylor Brooks", role: "DevOps Engineer",    skills: ["Docker", "GitHub Actions", "AWS", "rclone"],       availability: 40,  matchScore: 0.79 },
];

function AvailabilityBar({ pct }: { pct: number }) {
  const color = pct >= 80 ? "bg-success" : pct >= 50 ? "bg-warning" : "bg-destructive";
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-surface-subtle rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[11px] text-text-muted tabular-nums">{pct}%</span>
    </div>
  );
}

function MatchBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 90 ? "text-success bg-success-subtle" : pct >= 80 ? "text-warning bg-warning-subtle" : "text-text-muted bg-surface-subtle";
  return (
    <span className={cn("text-[11px] font-semibold px-2 py-0.5 rounded-full tabular-nums", color)}>
      {pct}% match
    </span>
  );
}

export default function TeamPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [loading, setLoading]       = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [proceeding, setProceeding] = useState(false);

  // TODO (Epic 4): replace with GET /api/v1/projects/{id}/team
  useEffect(() => { const t = setTimeout(() => setLoading(false), 500); return () => clearTimeout(t); }, []);

  if (loading) return <ReviewPageSkeleton />;
  if (fetchError) return (
    <div className="px-6 py-8 max-w-4xl mx-auto">
      <ErrorBanner message={fetchError} onRetry={() => { setFetchError(null); setLoading(true); setTimeout(() => setLoading(false), 500); }} />
    </div>
  );

  async function handleProceed() {
    setProceeding(true);
    // TODO (Epic 4): POST /api/v1/projects/{id}/phases/5/start
    await new Promise((res) => setTimeout(res, 800));
    router.push(getNextPhaseRoute("team", id));
  }

  return (
    <div className="px-6 py-8 max-w-4xl mx-auto flex flex-col gap-6">
      <PhaseProgressStepper phases={getPhasesForRoute("team")} />

      <div className="flex flex-col gap-4">
        <div>
          <h2 className="text-base font-semibold text-foreground">Team Suggestion</h2>
          <p className="text-xs text-text-muted mt-0.5">
            Suggested team based on required skills, availability, and historical project match.
          </p>
        </div>

        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-border bg-surface-subtle/50">
            <span className="text-xs font-semibold text-text-muted uppercase tracking-wide">
              {MOCK_TEAM.length} members suggested
            </span>
          </div>

          <div className="divide-y divide-border">
            {MOCK_TEAM.map((member) => (
              <div key={member.name} className="flex items-start gap-4 px-4 py-3.5">
                {/* Avatar */}
                <div className="w-8 h-8 rounded-full bg-accent-subtle border border-border flex items-center justify-center shrink-0 text-xs font-semibold text-accent-foreground">
                  {member.name.split(" ").map((n) => n[0]).join("")}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="text-sm font-semibold text-foreground">{member.name}</span>
                    <span className="text-xs text-text-secondary">{member.role}</span>
                  </div>
                  <div className="flex flex-wrap gap-1 mb-2">
                    {member.skills.map((s) => (
                      <span key={s} className="text-[10px] bg-surface-subtle border border-border text-text-secondary px-1.5 py-0.5 rounded">
                        {s}
                      </span>
                    ))}
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-[11px] text-text-muted">Availability</span>
                    <AvailabilityBar pct={member.availability} />
                  </div>
                </div>

                <MatchBadge score={member.matchScore} />
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
              <>Proceed to Estimation<svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}><path d="M2 7h10M8 3l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" /></svg></>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
