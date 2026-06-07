"use client";

import { useState, useEffect, use } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { ReviewPageSkeleton, ErrorBanner } from "@/components/page-states";
import { getPhasesForRoute, getNextPhaseRoute } from "@/lib/project-phases";
import { cn } from "@/lib/utils";
import { triggerTeam, updateTeam, listAdminEmployees } from "@/lib/api";

interface TeamMember {
  id: number;
  name: string;
  seniority: string;
  availability_pct: number;
  skills: string[];
  matchScore: number; // 0-1
  manual?: boolean;
}


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
  const [saving, setSaving]         = useState(false);
  const [team, setTeam]             = useState<TeamMember[]>([]);
  const [search, setSearch]         = useState("");

  // Load all employees for the search dropdown
  const { data: allEmployees } = useQuery({
    queryKey: ["admin-employees"],
    queryFn: listAdminEmployees,
    staleTime: 60_000,
    enabled: true,
  });

  // Filter employees: match search text, exclude already-added members
  const filteredEmployees = allEmployees?.filter(
    (e) =>
      e.name.toLowerCase().includes(search.toLowerCase()) &&
      !team.some((m) => m.id === e.id)
  );

  useEffect(() => {
    let cancelled = false;
    triggerTeam(id)
      .then((data) => {
        if (cancelled) return;
        const members: TeamMember[] = data.members.map((m) => ({
          id: m.id,
          name: m.name,
          seniority: m.seniority,
          availability_pct: m.availability_pct,
          skills: m.skills,
          matchScore: (m as { match_score?: number }).match_score ?? 0,
          manual: false,
        }));
        setTeam(members);
      })
      .catch((err: Error) => {
        if (!cancelled) setFetchError(err.message);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [id]);

  if (loading) return <ReviewPageSkeleton />;
  if (fetchError) return (
    <div className="px-6 py-8 max-w-4xl mx-auto">
      <ErrorBanner message={fetchError} onRetry={() => window.location.reload()} />
    </div>
  );

  async function handleConfirmTeam() {
    setSaving(true);
    try {
      await updateTeam(
        id,
        team.map((m) => ({
          id: m.id,
          name: m.name,
          seniority: m.seniority,
          availability_pct: m.availability_pct,
          skills: m.skills,
          manual: m.manual,
        }))
      );
      router.push(getNextPhaseRoute("team", id));
    } catch {
      // TODO: surface error toast
    } finally {
      setSaving(false);
    }
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
              {team.length} member{team.length !== 1 ? "s" : ""} selected
            </span>
          </div>

          <div className="divide-y divide-border">
            {team.map((member) => (
              <div key={member.id} className="flex items-start gap-4 px-4 py-3.5">
                {/* Avatar */}
                <div className="w-8 h-8 rounded-full bg-accent-subtle border border-border flex items-center justify-center shrink-0 text-xs font-semibold text-accent-foreground">
                  {member.name.split(" ").map((n) => n[0]).join("")}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="text-sm font-semibold text-foreground">{member.name}</span>
                    <span className="text-xs text-text-secondary">{member.seniority}</span>
                    {member.manual && (
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-warning-subtle text-warning border border-warning/20">
                        Manual
                      </span>
                    )}
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
                    <AvailabilityBar pct={member.availability_pct} />
                  </div>
                </div>

                {!member.manual && <MatchBadge score={member.matchScore} />}

                {/* Remove button */}
                <button
                  onClick={() => setTeam((prev) => prev.filter((m) => m.id !== member.id))}
                  className="flex items-center justify-center w-7 h-7 rounded-md text-text-muted hover:bg-destructive-subtle hover:text-destructive transition-colors"
                  title="Remove"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                    <path d="M3 4h10M6 4V3h4v1M5 4v8h6V4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              </div>
            ))}

            {team.length === 0 && (
              <div className="px-4 py-8 text-center text-sm text-text-muted">
                No team members selected. Use the search below to add employees.
              </div>
            )}
          </div>
        </div>

        {/* Search & Add section */}
        <div className="flex flex-col gap-3 mt-2">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-text-muted">Add Team Members</h2>
          <div className="relative">
            <input
              type="text"
              placeholder="Search employees by name…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-card border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-accent/30 text-foreground placeholder:text-text-muted"
            />
          </div>
          {search.trim() && filteredEmployees && filteredEmployees.length > 0 && (
            <div className="bg-card border border-border rounded-xl overflow-hidden divide-y divide-border">
              {filteredEmployees.slice(0, 8).map((emp) => (
                <div key={emp.id} className="flex items-center gap-3 px-4 py-3">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-foreground">{emp.name}</div>
                    <div className="text-[11px] text-text-muted">{emp.seniority} · {emp.availability_pct}%</div>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {emp.skills.slice(0, 3).map((s) => (
                      <span key={s.name} className="text-[10px] bg-surface-subtle border border-border rounded px-1.5 py-0.5">{s.name}</span>
                    ))}
                  </div>
                  <button
                    onClick={() => {
                      setTeam((prev) => [
                        ...prev,
                        {
                          id: emp.id,
                          name: emp.name,
                          seniority: emp.seniority,
                          availability_pct: emp.availability_pct,
                          skills: emp.skills.map((s) => s.name),
                          matchScore: 0,
                          manual: true,
                        },
                      ]);
                      setSearch("");
                    }}
                    className="px-3 py-1.5 text-xs font-medium bg-accent text-accent-foreground rounded-md hover:opacity-90 transition-opacity shrink-0"
                  >
                    Add
                  </button>
                </div>
              ))}
            </div>
          )}
          {search.trim() && filteredEmployees?.length === 0 && (
            <p className="text-sm text-text-muted italic">No matching employees.</p>
          )}
        </div>

        <div className="flex items-center justify-end pt-2 border-t border-border">
          <button
            onClick={handleConfirmTeam}
            disabled={saving || team.length === 0}
            className={cn(
              "inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-opacity",
              saving || team.length === 0
                ? "bg-muted text-text-muted cursor-not-allowed opacity-50"
                : "bg-primary text-primary-foreground hover:opacity-90"
            )}
          >
            {saving ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                  <path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" />
                </svg>
                Saving…
              </>
            ) : (
              <>
                Confirm Team ({team.length})
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
