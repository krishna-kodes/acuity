"use client";

import { useQuery } from "@tanstack/react-query";
import { listAdminEmployees, type AdminEmployee, type AdminSkill } from "@/lib/api";
import { cn } from "@/lib/utils";

function calcExperience(joinedAt: string | null): string {
  if (!joinedAt) return "—";
  const ms = Date.now() - new Date(joinedAt).getTime();
  const months = Math.floor(ms / (1000 * 60 * 60 * 24 * 30.44));
  const years = Math.floor(months / 12);
  const rem = months % 12;
  if (years === 0) return `${rem}mo`;
  if (rem === 0) return `${years}yr`;
  return `${years}yr ${rem}mo`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

const SENIORITY_COLOR: Record<string, string> = {
  Junior:    "bg-accent/10 text-accent",
  Mid:       "bg-accent/20 text-accent",
  Senior:    "bg-accent/30 text-accent",
  Lead:      "bg-accent/40 text-accent",
  Principal: "bg-accent/50 text-accent",
};

export default function EmployeesPage() {
  const { data: employees, isLoading, isError } = useQuery({
    queryKey: ["admin-employees"],
    queryFn: listAdminEmployees,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  return (
    <div className="px-6 py-8 max-w-5xl mx-auto flex flex-col gap-6">
      <div>
        <h1 className="text-base font-semibold text-foreground">Employees</h1>
        <p className="text-xs text-text-muted mt-0.5">
          {employees ? `${employees.length} employees` : "Loading…"}
        </p>
      </div>

      {isError && (
        <p className="text-sm text-destructive">Failed to load employees. Please refresh.</p>
      )}

      {isLoading && (
        <p className="text-sm text-text-muted">Loading…</p>
      )}

      {employees && employees.length > 0 && (
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          {/* Header row */}
          <div className="grid grid-cols-[1fr_auto_auto_auto_auto_auto_auto] gap-4 px-4 py-2 border-b border-border bg-surface-subtle">
            {["Name", "Seniority", "Status", "Joined", "Experience", "Avail.", "Skills"].map((h) => (
              <span key={h} className="text-[10px] font-semibold uppercase tracking-widest text-text-muted">
                {h}
              </span>
            ))}
          </div>
          <div className="divide-y divide-border">
            {employees.map((emp: AdminEmployee) => (
              <div key={emp.id} className="grid grid-cols-[1fr_auto_auto_auto_auto_auto_auto] gap-4 items-center px-4 py-3">
                {/* Name + email */}
                <div className="min-w-0">
                  <div className="text-sm font-medium text-foreground truncate">{emp.name}</div>
                  {emp.email && (
                    <div className="text-[11px] text-text-muted truncate">{emp.email}</div>
                  )}
                </div>
                {/* Seniority */}
                <span className={cn("text-[10px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap",
                  SENIORITY_COLOR[emp.seniority] ?? "bg-accent/10 text-accent")}>
                  {emp.seniority}
                </span>
                {/* Status */}
                <span className={cn("text-[10px] font-medium px-1.5 py-0.5 rounded border whitespace-nowrap",
                  emp.status === "active"
                    ? "bg-success-subtle text-success border-success/20"
                    : "bg-surface-subtle text-text-muted border-border")}>
                  {emp.status}
                </span>
                {/* Joined */}
                <span className="text-[11px] text-text-muted whitespace-nowrap">
                  {formatDate(emp.joined_at)}
                </span>
                {/* Experience */}
                <span className="text-[11px] text-text-muted whitespace-nowrap">
                  {calcExperience(emp.joined_at)}
                </span>
                {/* Availability */}
                <span className="text-[11px] text-text-muted whitespace-nowrap">
                  {emp.availability_pct}%
                </span>
                {/* Skills */}
                <div className="flex flex-wrap gap-1 justify-end">
                  {emp.skills.map((s: AdminSkill) => (
                    <span key={s.id} className="text-[10px] bg-surface-subtle border border-border rounded px-1.5 py-0.5 whitespace-nowrap text-foreground">
                      {s.name}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
