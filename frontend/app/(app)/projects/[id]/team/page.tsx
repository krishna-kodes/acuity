"use client";

import { useState, useEffect, use } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Circle } from "lucide-react";
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
  matchScore: number;
  active_projects_count: number;
}

const AVATAR_PALETTE = [
  "bg-blue-100 text-blue-700",
  "bg-emerald-100 text-emerald-700",
  "bg-violet-100 text-violet-700",
  "bg-amber-100 text-amber-700",
  "bg-rose-100 text-rose-700",
  "bg-cyan-100 text-cyan-700",
  "bg-indigo-100 text-indigo-700",
  "bg-teal-100 text-teal-700",
];

function avatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) | 0;
  return AVATAR_PALETTE[Math.abs(hash) % AVATAR_PALETTE.length];
}

function initials(name: string): string {
  return name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();
}

function AvailabilityBar({ pct }: { pct: number }) {
  const color = pct >= 80 ? "bg-success" : pct >= 50 ? "bg-warning" : "bg-destructive";
  return (
    <div className="w-full h-1.5 bg-surface-subtle rounded-full overflow-hidden">
      <div className={cn("h-full rounded-full", color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

interface CandidateCardProps {
  member: TeamMember;
  selected: boolean;
  onToggle: () => void;
}

function CandidateCard({ member, selected, onToggle }: CandidateCardProps) {
  const pct = Math.round(member.matchScore * 100);
  const matchColor =
    pct >= 90
      ? "text-success bg-success-subtle"
      : pct >= 80
      ? "text-warning bg-warning-subtle"
      : "text-text-muted bg-surface-subtle";

  return (
    <div
      onClick={onToggle}
      className={cn(
        "relative rounded-xl border p-4 cursor-pointer transition-colors select-none",
        selected
          ? "bg-blue-50/60 border-blue-300"
          : "bg-card border-border hover:border-accent"
      )}
    >
      {/* Checkbox */}
      <div className="absolute top-3 right-3">
        {selected ? (
          <CheckCircle2 className="w-5 h-5 text-blue-600" />
        ) : (
          <Circle className="w-5 h-5 text-border" />
        )}
      </div>

      {/* Avatar + Name */}
      <div className="flex items-center gap-3 pr-7 mb-3">
        <div
          className={cn(
            "w-9 h-9 rounded-full flex items-center justify-center shrink-0 text-xs font-bold",
            avatarColor(member.name)
          )}
        >
          {initials(member.name)}
        </div>
        <span className="text-sm font-semibold text-foreground truncate">{member.name}</span>
      </div>

      {/* Badge row: seniority + match score + active */}
      <div className="flex flex-wrap items-center gap-1.5 mb-3">
        <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-surface-subtle text-text-secondary border border-border">
          {member.seniority}
        </span>
        <span className={cn("text-[11px] font-semibold px-2 py-0.5 rounded-full tabular-nums", matchColor)}>
          {pct}% match
        </span>
        {member.active_projects_count > 0 && (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-warning bg-warning-subtle px-2 py-0.5 rounded-full border border-warning/20">
            <span className="w-1.5 h-1.5 rounded-full bg-warning inline-block" />
            {member.active_projects_count} active
          </span>
        )}
      </div>

      {/* Availability */}
      <div className="mb-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[11px] text-text-muted">Availability</span>
          <span className="text-[11px] font-semibold tabular-nums text-foreground">{member.availability_pct}%</span>
        </div>
        <AvailabilityBar pct={member.availability_pct} />
      </div>

      {/* Skills */}
      <div className="flex flex-wrap gap-1">
        {member.skills.slice(0, 4).map((s) => (
          <span
            key={s}
            className="text-[10px] bg-surface-subtle border border-border text-text-secondary px-1.5 py-0.5 rounded"
          >
            {s}
          </span>
        ))}
        {member.skills.length > 4 && (
          <span className="text-[10px] text-text-muted px-1 py-0.5">
            +{member.skills.length - 4}
          </span>
        )}
      </div>
    </div>
  );
}

export default function TeamPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [candidates, setCandidates] = useState<TeamMember[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [manualAdds, setManualAdds] = useState<TeamMember[]>([]);
  const [search, setSearch] = useState("");

  const { data: allEmployees } = useQuery({
    queryKey: ["admin-employees"],
    queryFn: listAdminEmployees,
    staleTime: 60_000,
  });

  const filteredEmployees = allEmployees?.filter(
    (e) =>
      e.name.toLowerCase().includes(search.toLowerCase()) &&
      !candidates.some((m) => m.id === e.id) &&
      !manualAdds.some((m) => m.id === e.id)
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
          matchScore: m.match_score ?? 0,
          active_projects_count: m.active_projects_count ?? 0,
        }));
        setCandidates(members);
      })
      .catch((err: Error) => {
        if (!cancelled) setFetchError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  function toggleCandidate(memberId: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(memberId) ? next.delete(memberId) : next.add(memberId);
      return next;
    });
  }

  const totalSelected = selected.size + manualAdds.length;

  async function handleConfirmTeam() {
    setSaving(true);
    try {
      const confirmedMembers = [
        ...candidates
          .filter((m) => selected.has(m.id))
          .map((m) => ({
            id: m.id,
            name: m.name,
            seniority: m.seniority,
            availability_pct: m.availability_pct,
            skills: m.skills,
            manual: false,
          })),
        ...manualAdds.map((m) => ({
          id: m.id,
          name: m.name,
          seniority: m.seniority,
          availability_pct: m.availability_pct,
          skills: m.skills,
          manual: true,
        })),
      ];
      await updateTeam(id, confirmedMembers);
      router.push(getNextPhaseRoute("team", id));
    } catch {
      // TODO: surface error toast
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <ReviewPageSkeleton />;
  if (fetchError)
    return (
      <div className="px-6 py-8 max-w-5xl mx-auto">
        <ErrorBanner message={fetchError} onRetry={() => window.location.reload()} />
      </div>
    );

  return (
    <div className="px-6 py-8 max-w-5xl mx-auto flex flex-col gap-6">
      <PhaseProgressStepper phases={getPhasesForRoute("team")} />

      <div className="flex flex-col gap-6">
        <div>
          <h2 className="text-base font-semibold text-foreground">Team suggestion</h2>
          <p className="text-xs text-text-muted mt-0.5">
            Matched from the resource pool by required skills, seniority and availability. Toggle a
            card to include or remove an engineer from the proposed team.
          </p>
        </div>

        {/* Candidate grid */}
        {candidates.length === 0 ? (
          <div className="py-12 text-center text-sm text-text-muted">
            No candidates found for this tech stack.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {candidates.map((member) => (
              <CandidateCard
                key={member.id}
                member={member}
                selected={selected.has(member.id)}
                onToggle={() => toggleCandidate(member.id)}
              />
            ))}
          </div>
        )}

        {/* Manual add */}
        <div className="flex flex-col gap-3">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted">
            Add team members
          </h3>
          <input
            type="text"
            placeholder="Search employees by name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full px-3 py-2 text-sm bg-card border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-accent/30 text-foreground placeholder:text-text-muted"
          />
          {search.trim() && filteredEmployees && filteredEmployees.length > 0 && (
            <div className="bg-card border border-border rounded-xl overflow-hidden divide-y divide-border">
              {filteredEmployees.slice(0, 8).map((emp) => (
                <div key={emp.id} className="flex items-center gap-3 px-4 py-3">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-foreground">{emp.name}</div>
                    <div className="text-[11px] text-text-muted">
                      {emp.seniority} · {emp.availability_pct}%
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {emp.skills.slice(0, 3).map((s) => (
                      <span
                        key={s.name}
                        className="text-[10px] bg-surface-subtle border border-border rounded px-1.5 py-0.5"
                      >
                        {s.name}
                      </span>
                    ))}
                  </div>
                  <button
                    onClick={() => {
                      setManualAdds((prev) => [
                        ...prev,
                        {
                          id: emp.id,
                          name: emp.name,
                          seniority: emp.seniority,
                          availability_pct: emp.availability_pct,
                          skills: emp.skills.map((s) => s.name),
                          matchScore: 0,
                          active_projects_count: 0,
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

        {/* Manually added section */}
        {manualAdds.length > 0 && (
          <div className="flex flex-col gap-2">
            <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted">
              Added members
            </h3>
            <div className="bg-card border border-border rounded-xl overflow-hidden divide-y divide-border">
              {manualAdds.map((m) => (
                <div key={m.id} className="flex items-center gap-3 px-4 py-3">
                  <div
                    className={cn(
                      "w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-[10px] font-bold",
                      avatarColor(m.name)
                    )}
                  >
                    {initials(m.name)}
                  </div>
                  <div className="flex-1 min-w-0 flex items-center gap-2">
                    <span className="text-sm font-medium text-foreground">{m.name}</span>
                    <span className="text-[11px] text-text-muted">{m.seniority}</span>
                  </div>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-warning-subtle text-warning border border-warning/20">
                    Manual
                  </span>
                  <button
                    onClick={() => setManualAdds((prev) => prev.filter((x) => x.id !== m.id))}
                    className="flex items-center justify-center w-6 h-6 rounded text-text-muted hover:bg-destructive-subtle hover:text-destructive transition-colors"
                    title="Remove"
                  >
                    <svg
                      className="w-3 h-3"
                      fill="none"
                      viewBox="0 0 12 12"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path d="M2 2l8 8M10 2l-8 8" strokeLinecap="round" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Confirm button */}
        <div className="flex items-center justify-between pt-2 border-t border-border">
          <span className="text-xs text-text-muted">
            {totalSelected} member{totalSelected !== 1 ? "s" : ""} selected
          </span>
          <button
            onClick={handleConfirmTeam}
            disabled={saving || totalSelected === 0}
            className={cn(
              "inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-opacity",
              saving || totalSelected === 0
                ? "bg-muted text-text-muted cursor-not-allowed opacity-50"
                : "bg-primary text-primary-foreground hover:opacity-90"
            )}
          >
            {saving ? (
              <>
                <svg
                  className="w-4 h-4 animate-spin"
                  fill="none"
                  viewBox="0 0 16 16"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" />
                </svg>
                Saving…
              </>
            ) : (
              <>
                Confirm Team ({totalSelected})
                <svg
                  className="w-3.5 h-3.5"
                  fill="none"
                  viewBox="0 0 14 14"
                  stroke="currentColor"
                  strokeWidth={2}
                >
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
