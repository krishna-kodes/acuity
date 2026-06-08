"use client";

import { useState, useEffect, useRef, use } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { getPhasesForRoute, getNextPhaseRoute } from "@/lib/project-phases";
import {
  extractModules,
  getModules,
  saveModules,
  approveModules,
} from "@/lib/api";
import type { Module } from "@/lib/api";
import { cn } from "@/lib/utils";

const LABELS = ["frontend", "backend", "devops", "QA", "PM", "design", "data", "infra"] as const;
type Label = typeof LABELS[number];

const LABEL_STYLE: Record<Label, string> = {
  frontend: "bg-blue-50  text-blue-700  border-blue-200",
  backend:  "bg-purple-50 text-purple-700 border-purple-200",
  devops:   "bg-orange-50 text-orange-700 border-orange-200",
  QA:       "bg-green-50 text-green-700  border-green-200",
  PM:       "bg-pink-50  text-pink-700   border-pink-200",
  design:   "bg-yellow-50 text-yellow-700 border-yellow-200",
  data:     "bg-cyan-50  text-cyan-700   border-cyan-200",
  infra:    "bg-red-50   text-red-700    border-red-200",
};

function labelStyle(label: string): string {
  return LABEL_STYLE[label as Label] ?? "bg-surface-subtle text-text-secondary border-border";
}

function groupByLabel(modules: Module[]): Record<string, Module[]> {
  const out: Record<string, Module[]> = {};
  for (const m of modules) {
    if (!out[m.label]) out[m.label] = [];
    out[m.label].push(m);
  }
  return out;
}

export default function ModulesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();

  const [modules, setModules] = useState<Module[]>([]);
  const [extracting, setExtracting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newLabel, setNewLabel] = useState<Label>("backend");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  // Prevents React StrictMode double-fire from triggering two LLM extraction calls
  const extractionFiredRef = useRef(false);

  async function runExtraction(isCancelled?: () => boolean) {
    setExtracting(true);
    const tid = toast.loading("Extracting modules from proposal…");
    try {
      const data = await extractModules(id);
      if (isCancelled?.()) { toast.dismiss(tid); return; }
      setModules(data.modules);
      toast.dismiss(tid);
      toast.success(
        data.modules.length > 0
          ? `${data.modules.length} module${data.modules.length !== 1 ? "s" : ""} extracted`
          : "No modules extracted — add them manually below"
      );
    } catch {
      toast.dismiss(tid);
      if (!isCancelled?.()) toast.error("Extraction failed — add modules manually");
    } finally {
      setExtracting(false);
    }
  }

  // On mount: load stored modules; if empty, auto-extract.
  // The extractionFiredRef guard prevents React StrictMode from firing two simultaneous LLM calls.
  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await getModules(id);
        if (cancelled) return;
        if (data.modules.length > 0) {
          setModules(data.modules);
          return;
        }
      } catch {
        if (cancelled) return;
      }
      if (extractionFiredRef.current) return;
      extractionFiredRef.current = true;
      await runExtraction(() => cancelled);
    }

    load();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  function addModule() {
    if (!newTitle.trim()) return;
    const m: Module = {
      id: crypto.randomUUID(),
      title: newTitle.trim(),
      label: newLabel,
      description: "",
    };
    setModules((prev) => [...prev, m]);
    setNewTitle("");
  }

  function deleteModule(moduleId: string) {
    setModules((prev) => prev.filter((m) => m.id !== moduleId));
  }

  function startEdit(m: Module) {
    setEditingId(m.id);
    setEditingTitle(m.title);
  }

  function commitEdit(moduleId: string) {
    setModules((prev) =>
      prev.map((m) => (m.id === moduleId ? { ...m, title: editingTitle } : m))
    );
    setEditingId(null);
  }

  async function handleSave() {
    setSaving(true);
    try {
      await saveModules(id, modules);
      toast.success("Changes saved");
    } catch {
      toast.error("Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleApprove() {
    setApproving(true);
    try {
      await saveModules(id, modules);
      await approveModules(id);
      router.push(getNextPhaseRoute("modules", id));
    } catch {
      toast.error("Failed to approve — try again");
      setApproving(false);
    }
  }

  const grouped = groupByLabel(modules);
  const labelOrder = LABELS.filter((l) => grouped[l]?.length);
  const otherLabels = Object.keys(grouped).filter(
    (l) => !LABELS.includes(l as Label)
  );

  return (
    <div className="px-6 py-8 max-w-4xl mx-auto flex flex-col gap-6">
      <PhaseProgressStepper phases={getPhasesForRoute("modules")} />

      <div className="flex flex-col gap-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-base font-semibold text-foreground">Work Modules</h2>
            <p className="text-xs text-text-muted mt-0.5">
              Review AI-extracted work packages. Add, edit, or remove items before proceeding.
            </p>
          </div>
          <button
            onClick={() => runExtraction()}
            disabled={extracting}
            className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-border bg-card hover:bg-surface-subtle transition-colors disabled:opacity-50"
          >
            {extracting ? (
              <>
                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                  <path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" />
                </svg>
                Extracting…
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                  <path d="M13 6A6 6 0 1 0 8 14" strokeLinecap="round" />
                  <path d="M13 2v4h-4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Re-extract from Proposal
              </>
            )}
          </button>
        </div>

        {/* Loading state */}
        {extracting && modules.length === 0 ? (
          <div className="bg-card border border-border rounded-xl py-12 flex flex-col items-center gap-3">
            <svg className="w-6 h-6 animate-spin text-primary" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
              <path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" />
            </svg>
            <p className="text-xs text-text-muted">Extracting modules from proposal…</p>
          </div>
        ) : (
          <>
            {/* Module groups */}
            {[...labelOrder, ...otherLabels].length === 0 ? (
              <div className="bg-card border border-border rounded-xl py-10 flex flex-col items-center gap-2 text-center">
                <p className="text-sm text-text-muted">No modules yet — add one below or re-extract from the proposal.</p>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {[...labelOrder, ...otherLabels].map((label) => (
                  <div key={label} className="bg-card border border-border rounded-xl overflow-hidden">
                    {/* Group header */}
                    <div className="px-4 py-2.5 border-b border-border bg-surface-subtle/50 flex items-center gap-2">
                      <span className={cn(
                        "text-[11px] font-semibold px-2 py-0.5 rounded-full border",
                        labelStyle(label)
                      )}>
                        {label}
                      </span>
                      <span className="text-[11px] text-text-muted">
                        {grouped[label].length} module{grouped[label].length !== 1 ? "s" : ""}
                      </span>
                    </div>

                    {/* Module rows */}
                    <div className="divide-y divide-border">
                      {grouped[label].map((m) => (
                        <div key={m.id} className="flex items-center gap-3 px-4 py-2.5 group">
                          {editingId === m.id ? (
                            <input
                              autoFocus
                              value={editingTitle}
                              onChange={(e) => setEditingTitle(e.target.value)}
                              onBlur={() => commitEdit(m.id)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") commitEdit(m.id);
                                if (e.key === "Escape") setEditingId(null);
                              }}
                              className="flex-1 min-w-0 text-sm bg-transparent border-b border-primary outline-none py-0.5"
                            />
                          ) : (
                            <span
                              className="flex-1 min-w-0 text-sm text-foreground cursor-text truncate"
                              onClick={() => startEdit(m)}
                              title="Click to edit"
                            >
                              {m.title}
                            </span>
                          )}
                          <button
                            onClick={() => deleteModule(m.id)}
                            className="shrink-0 w-5 h-5 flex items-center justify-center rounded text-text-muted hover:text-destructive hover:bg-destructive-subtle opacity-0 group-hover:opacity-100 transition-all"
                            aria-label={`Delete ${m.title}`}
                          >
                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}>
                              <path d="M2 2l10 10M12 2L2 12" strokeLinecap="round" />
                            </svg>
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Manual add row */}
            <div className="bg-card border border-border rounded-xl px-4 py-3 flex items-center gap-2 flex-wrap">
              <input
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") addModule(); }}
                placeholder="Module title…"
                className="flex-1 min-w-[160px] text-sm bg-transparent outline-none placeholder:text-text-muted"
              />
              <select
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value as Label)}
                className="text-xs border border-border rounded-md px-2 py-1.5 bg-surface-subtle text-text-secondary outline-none cursor-pointer"
              >
                {LABELS.map((l) => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </select>
              <button
                onClick={addModule}
                disabled={!newTitle.trim()}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium bg-primary text-primary-foreground hover:bg-accent-hover transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2.5}>
                  <path d="M6 1v10M1 6h10" strokeLinecap="round" />
                </svg>
                Add
              </button>
            </div>
          </>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between pt-2 border-t border-border gap-3 flex-wrap">
          <p className="text-xs text-text-muted">
            {modules.length} module{modules.length !== 1 ? "s" : ""} total
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={handleSave}
              disabled={saving || extracting}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium border border-border bg-card hover:bg-surface-subtle transition-colors disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save Changes"}
            </button>
            <button
              onClick={handleApprove}
              disabled={approving || extracting}
              className={cn(
                "inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors",
                !approving && !extracting
                  ? "bg-primary text-primary-foreground hover:bg-accent-hover"
                  : "bg-muted text-text-muted cursor-not-allowed"
              )}
            >
              {approving ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                    <path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" />
                  </svg>
                  Approving…
                </>
              ) : (
                <>
                  Approve & Proceed
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}>
                    <path d="M2 7h10M8 3l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
