"use client";

import { useState } from "react";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { EpicTaskListItem } from "@/components/epic-task-list-item";
import { SyncStatusBadge } from "@/components/sync-status-badge";
import type { Phase } from "@/components/phase-progress-stepper";
import type { EpicItem } from "@/components/epic-task-list-item";
import type { SyncStatus } from "@/components/sync-status-badge";
import { cn } from "@/lib/utils";

const PHASES: Phase[] = [
  { label: "Ingestion",    status: "complete" },
  { label: "Refinement",   status: "complete" },
  { label: "Tech Stack",   status: "complete" },
  { label: "Team",         status: "complete" },
  { label: "Estimation",   status: "complete" },
  { label: "Epics & Sync", status: "in_progress" },
];

// TODO (Epic 4): fetch from GET /api/v1/projects/{id}/epics
const INITIAL_EPICS: EpicItem[] = [
  {
    id: "e1",
    title: "Document Ingestion Pipeline",
    points: 34,
    syncStatus: "pending",
    selected: true,
    tasks: [
      { id: "t1", title: "PDF/DOCX parser with structure detection",             points: 8,  assignee: "Priya Nair",   syncStatus: "pending" },
      { id: "t2", title: "Hybrid chunking strategy (header + paragraph + size)", points: 13, assignee: "Priya Nair",   syncStatus: "pending" },
      { id: "t3", title: "ChromaDB PersistentClient integration",                points: 5,  assignee: "Priya Nair",   syncStatus: "pending" },
      { id: "t4", title: "Embedding pipeline with text-embedding-3-small",       points: 8,  assignee: "Priya Nair",   syncStatus: "pending" },
    ],
  },
  {
    id: "e2",
    title: "PII Detection & Redaction",
    points: 21,
    syncStatus: "pending",
    selected: true,
    tasks: [
      { id: "t5", title: "Regex-based PII detection (Email, Phone, Card)",       points: 5,  assignee: "Sam Okonkwo",  syncStatus: "pending" },
      { id: "t6", title: "spaCy NER integration (Person, Org, Location)",        points: 8,  assignee: "Sam Okonkwo",  syncStatus: "pending" },
      { id: "t7", title: "Fernet encryption for confirmed PII",                  points: 5,  assignee: "Sam Okonkwo",  syncStatus: "pending" },
      { id: "t8", title: "Redaction review UI wiring to backend",               points: 3,  assignee: "Jordan Kim",   syncStatus: "pending" },
    ],
  },
  {
    id: "e3",
    title: "RAG Chat & Refinement",
    points: 42,
    syncStatus: "pending",
    selected: true,
    tasks: [
      { id: "t9",  title: "Query rewriting (3 sub-queries via fast LLM)",        points: 8,  assignee: "Priya Nair",   syncStatus: "pending" },
      { id: "t10", title: "BM25 sparse retrieval integration",                   points: 5,  assignee: "Priya Nair",   syncStatus: "pending" },
      { id: "t11", title: "BERT cross-encoder reranker (ms-marco-MiniLM)",       points: 8,  assignee: "Priya Nair",   syncStatus: "pending" },
      { id: "t12", title: "TBD detection (Level 1 + Level 2)",                  points: 8,  assignee: "Alex Rivera",  syncStatus: "pending" },
      { id: "t13", title: "Clarifications API + chat frontend wiring",           points: 8,  assignee: "Jordan Kim",   syncStatus: "pending" },
      { id: "t14", title: "Proposal generation from refined requirements",        points: 5,  assignee: "Alex Rivera",  syncStatus: "pending" },
    ],
  },
  {
    id: "e4",
    title: "LangGraph Agent (Phases 4–6)",
    points: 55,
    syncStatus: "pending",
    selected: true,
    tasks: [
      { id: "t15", title: "LangGraph ReAct graph with SqliteSaver checkpointer", points: 13, assignee: "Alex Rivera",  syncStatus: "pending" },
      { id: "t16", title: "Team suggestion node (skills + availability filter)", points: 8,  assignee: "Alex Rivera",  syncStatus: "pending" },
      { id: "t17", title: "Effort estimation node (historical retrieval)",       points: 13, assignee: "Alex Rivera",  syncStatus: "pending" },
      { id: "t18", title: "Epic/task generation with Pydantic structured output",points: 13, assignee: "Alex Rivera",  syncStatus: "pending" },
      { id: "t19", title: "GitHub MCP sync (milestones + issues)",               points: 8,  assignee: "Sam Okonkwo",  syncStatus: "pending" },
    ],
  },
  {
    id: "e5",
    title: "Eval Layer",
    points: 34,
    syncStatus: "skipped",
    selected: false,
    tasks: [
      { id: "t20", title: "10–15 test cases in test_cases.json",                 points: 5,  syncStatus: "skipped" },
      { id: "t21", title: "Code-based graders (retrieval, tool selection, loop)",points: 8,  syncStatus: "skipped" },
      { id: "t22", title: "Semantic + LLM-as-judge graders",                     points: 8,  syncStatus: "skipped" },
      { id: "t23", title: "HybridRAGAgentEval harness + CI gate",                points: 13, syncStatus: "skipped" },
    ],
  },
];

type SyncState = "idle" | "syncing" | "done" | "error";

function SyncSummary({ epics }: { epics: EpicItem[] }) {
  const counts: Record<SyncStatus, number> = { pending: 0, synced: 0, skipped: 0, failed: 0 };
  epics.forEach((e) => counts[e.syncStatus]++);
  return (
    <div className="flex items-center gap-3 flex-wrap">
      {(["synced", "pending", "skipped", "failed"] as SyncStatus[]).map((s) =>
        counts[s] > 0 ? (
          <span key={s} className="flex items-center gap-1.5 text-xs text-text-secondary">
            <SyncStatusBadge status={s} size="sm" />
            <span className="tabular-nums">{counts[s]}</span>
          </span>
        ) : null
      )}
    </div>
  );
}

export default function EpicsPage({ params }: { params: { id: string } }) {
  const [epics, setEpics]       = useState<EpicItem[]>(INITIAL_EPICS);
  const [syncState, setSyncState] = useState<SyncState>("idle");
  const [syncError, setSyncError] = useState<string | null>(null);

  const selectedCount = epics.filter((e) => e.selected).length;
  const selectedPoints = epics.filter((e) => e.selected).reduce((s, e) => s + e.points, 0);

  function toggleEpic(id: string) {
    setEpics((prev) =>
      prev.map((e) =>
        e.id === id
          ? {
              ...e,
              selected: !e.selected,
              syncStatus: !e.selected ? "pending" : "skipped",
              tasks: e.tasks.map((t) => ({
                ...t,
                syncStatus: (!e.selected ? "pending" : "skipped") as SyncStatus,
              })),
            }
          : e
      )
    );
  }

  async function handleSync() {
    setSyncState("syncing");
    setSyncError(null);

    try {
      // TODO (Epic 4): POST /api/v1/projects/{id}/sync
      // Simulates per-epic milestone creation with a brief delay
      await new Promise((res) => setTimeout(res, 2000));

      setEpics((prev) =>
        prev.map((e) => ({
          ...e,
          syncStatus: e.selected ? "synced" : "skipped",
          tasks: e.tasks.map((t) => ({
            ...t,
            syncStatus: e.selected ? "synced" : ("skipped" as SyncStatus),
          })),
        }))
      );
      setSyncState("done");
    } catch {
      setSyncState("error");
      setSyncError("GitHub sync failed. Check your GITHUB_TOKEN and try again.");
    }
  }

  return (
    <div className="px-6 py-8 max-w-4xl mx-auto flex flex-col gap-6">
      <PhaseProgressStepper phases={PHASES} />

      <div className="flex flex-col gap-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-base font-semibold text-foreground">Epics &amp; Tasks</h2>
            <p className="text-xs text-text-muted mt-0.5">
              Review generated epics. Deselect any you want to skip. Then sync to GitHub.
            </p>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <SyncSummary epics={epics} />
          </div>
        </div>

        {/* Selection summary */}
        <div className="flex items-center gap-4 text-xs text-text-secondary px-1">
          <span><strong className="text-foreground tabular-nums">{selectedCount}</strong> of {epics.length} epics selected</span>
          <span><strong className="text-foreground tabular-nums">{selectedPoints}</strong> story points</span>
        </div>

        {/* Epic list */}
        <div className="flex flex-col gap-2">
          {epics.map((epic) => (
            <EpicTaskListItem key={epic.id} epic={epic} onToggleSelect={toggleEpic} />
          ))}
        </div>

        {/* Error */}
        {syncError && (
          <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-destructive-subtle border border-destructive/20 text-xs text-destructive">
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
              <circle cx="8" cy="8" r="6" /><path d="M8 5v3.5M8 10v.5" strokeLinecap="round" />
            </svg>
            {syncError}
          </div>
        )}

        {/* Sync action */}
        <div className="flex items-center justify-between pt-2 border-t border-border flex-wrap gap-3">
          <div className="text-xs text-text-muted">
            {syncState === "done"
              ? "Sync complete — epics and tasks created in GitHub."
              : `${selectedCount} epic${selectedCount !== 1 ? "s" : ""} will be synced as GitHub Milestones.`}
          </div>
          <button
            onClick={handleSync}
            disabled={syncState === "syncing" || syncState === "done" || selectedCount === 0}
            className={cn(
              "inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors",
              syncState === "done"
                ? "bg-success-subtle text-success border border-success/20 cursor-default"
                : syncState === "syncing" || selectedCount === 0
                ? "bg-muted text-text-muted cursor-not-allowed"
                : "bg-primary text-primary-foreground hover:bg-accent-hover"
            )}
          >
            {syncState === "syncing" && (
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                <path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" />
              </svg>
            )}
            {syncState === "done" && (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2.5}>
                <polyline points="2.5,8 6,11.5 13.5,4" />
              </svg>
            )}
            {syncState === "syncing" ? "Syncing to GitHub…"
              : syncState === "done" ? "Synced"
              : "Sync to GitHub"}
          </button>
        </div>
      </div>
    </div>
  );
}
