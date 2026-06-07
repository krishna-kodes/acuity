"use client";

import { useQuery } from "@tanstack/react-query";
import { listAdminSkills, type AdminSkill } from "@/lib/api";
import { cn } from "@/lib/utils";

const CATEGORY_COLOR: Record<string, string> = {
  programming: "bg-accent/10 text-accent border-accent/20",
  framework:   "bg-success/10 text-success border-success/20",
  database:    "bg-warning/10 text-warning border-warning/20",
  devops:      "bg-surface-subtle text-text-muted border-border",
  design:      "bg-surface-subtle text-text-muted border-border",
};

export default function SkillsPage() {
  const { data: skills, isLoading, isError } = useQuery({
    queryKey: ["admin-skills"],
    queryFn: listAdminSkills,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  return (
    <div className="px-6 py-8 max-w-2xl mx-auto flex flex-col gap-6">
      <div>
        <h1 className="text-base font-semibold text-foreground">Skills</h1>
        <p className="text-xs text-text-muted mt-0.5">
          {skills ? `${skills.length} skills` : "Loading…"}
        </p>
      </div>

      {isError && <p className="text-sm text-destructive">Failed to load skills. Please refresh.</p>}
      {isLoading && <p className="text-sm text-text-muted">Loading…</p>}

      {skills && skills.length > 0 && (
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="grid grid-cols-[1fr_auto] gap-4 px-4 py-2 border-b border-border bg-surface-subtle">
            {["Skill", "Category"].map((h) => (
              <span key={h} className="text-[10px] font-semibold uppercase tracking-widest text-text-muted">{h}</span>
            ))}
          </div>
          <div className="divide-y divide-border">
            {skills.map((s: AdminSkill) => (
              <div key={s.id} className="grid grid-cols-[1fr_auto] gap-4 items-center px-4 py-3">
                <span className="text-sm text-foreground">{s.name}</span>
                <span className={cn("text-[10px] font-semibold px-2 py-0.5 rounded-full border capitalize whitespace-nowrap",
                  CATEGORY_COLOR[s.category] ?? "bg-surface-subtle text-text-muted border-border")}>
                  {s.category}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
