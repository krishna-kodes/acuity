"use client";

import { useState } from "react";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { ProjectCard } from "@/components/project-card";
import { SyncStatusBadge } from "@/components/sync-status-badge";
import { EpicTaskListItem } from "@/components/epic-task-list-item";
import { ChatThread } from "@/components/chat-thread";
import { TBDClarificationWidget } from "@/components/tbd-clarification-widget";
import { RedactionHighlight } from "@/components/redaction-highlight";
import { MetricsStatCard } from "@/components/metrics-stat-card";
import { MetricsLineChart } from "@/components/metrics-line-chart";
import { MetricsBarChart } from "@/components/metrics-bar-chart";
import type { Phase } from "@/components/phase-progress-stepper";
import type { EpicItem } from "@/components/epic-task-list-item";
import type { ChatMessage } from "@/components/chat-thread";
import type { TBDItem } from "@/components/tbd-clarification-widget";
import type { RedactionSpan } from "@/components/redaction-highlight";

// ── sample data ──────────────────────────────────────────────────────────────

const PHASES: Phase[] = [
  { label: "Ingestion",    status: "complete" },
  { label: "Refinement",   status: "complete" },
  { label: "Tech Stack",   status: "in_progress" },
  { label: "Team",         status: "locked" },
  { label: "Estimation",   status: "locked" },
  { label: "Epics & Sync", status: "locked" },
];

const EPICS: EpicItem[] = [
  {
    id: "e1",
    title: "User Authentication & Authorization",
    points: 34,
    syncStatus: "synced",
    selected: true,
    tasks: [
      { id: "t1", title: "Set up NextAuth with OAuth providers",  points: 8,  assignee: "dev-a", syncStatus: "synced" },
      { id: "t2", title: "Implement role-based access control",   points: 13, assignee: "dev-b", syncStatus: "synced" },
      { id: "t3", title: "Add session management middleware",      points: 5,  assignee: "dev-a", syncStatus: "pending" },
      { id: "t4", title: "Write integration tests for auth flow", points: 8,  syncStatus: "pending" },
    ],
  },
  {
    id: "e2",
    title: "Document Ingestion Pipeline",
    points: 21,
    syncStatus: "pending",
    selected: true,
    tasks: [
      { id: "t5", title: "PDF/DOCX parser with structure detection", points: 8,  assignee: "dev-b", syncStatus: "pending" },
      { id: "t6", title: "Hybrid chunking strategy",                 points: 13, assignee: "dev-b", syncStatus: "pending" },
    ],
  },
  {
    id: "e3",
    title: "GitHub Sync (Skipped)",
    points: 13,
    syncStatus: "skipped",
    selected: false,
    tasks: [],
  },
];

const MESSAGES: ChatMessage[] = [
  { id: "1", role: "ai", text: "I've analysed your requirements document. I found 3 TBD items that need clarification before I can generate a full proposal. Want to go through them?", timestamp: "09:41" },
  { id: "2", role: "pm", text: "Yes, let's do that. Start with the TBDs.", timestamp: "09:42" },
  { id: "3", role: "ai", text: "The first TBD is in section 3.2 — the SLA for the document processing pipeline is not specified. What's the expected turnaround time for a 50-page PDF?", timestamp: "09:42" },
];

const TBD_ITEMS: TBDItem[] = [
  { id: "tbd1", title: "Processing SLA",   desc: "Document processing turnaround time is not specified.",                     level: "explicit", status: "open" },
  { id: "tbd2", title: "Team Size",        desc: "'Small team' is mentioned but not quantified.",                             level: "vague",    status: "tbd" },
  { id: "tbd3", title: "Cloud Provider",   desc: "Target cloud provider not mentioned.",                                      level: "explicit", status: "oos" },
];

const REDACTIONS: RedactionSpan[] = [
  { id: 1, original: "John Smith",          type: "Person",       method: "NER",   placeholder: "[PERSON_1]",  confidence: 0.97 },
  { id: 2, original: "john.smith@acme.com", type: "Email",        method: "Regex", placeholder: "[EMAIL_1]",   confidence: 0.99, decision: "confirmed" },
  { id: 3, original: "+1 (555) 867-5309",   type: "Phone",        method: "Regex", placeholder: "[PHONE_1]",   confidence: 0.95 },
  { id: 4, original: "Acme Corporation",    type: "Organization", method: "NER",   placeholder: "[ORG_1]",     confidence: 0.88, decision: "override" },
];

const LINE_DATA = [
  { day: "Mon", tokens: 12400, cost: 0.019 },
  { day: "Tue", tokens: 18700, cost: 0.028 },
  { day: "Wed", tokens: 9200,  cost: 0.014 },
  { day: "Thu", tokens: 22100, cost: 0.033 },
  { day: "Fri", tokens: 15800, cost: 0.024 },
];

const BAR_DATA = [
  { phase: "Ingest",   p50: 420,  p95: 890 },
  { phase: "RAG",      p50: 1240, p95: 2800 },
  { phase: "Stack",    p50: 680,  p95: 1400 },
  { phase: "Team",     p50: 510,  p95: 1100 },
  { phase: "Estimate", p50: 930,  p95: 2100 },
  { phase: "Sync",     p50: 290,  p95: 610 },
];

// ── section wrapper ───────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-xs font-semibold uppercase tracking-widest text-text-muted border-b border-border pb-2">
        {title}
      </h2>
      {children}
    </section>
  );
}

// ── page ─────────────────────────────────────────────────────────────────────

export default function DesignSystemPage() {
  const [epics, setEpics] = useState<EpicItem[]>(EPICS);
  const [tbds]            = useState<TBDItem[]>(TBD_ITEMS);
  const [spans, setSpans] = useState<RedactionSpan[]>(REDACTIONS);

  function toggleEpic(id: string) {
    setEpics((prev) => prev.map((e) => e.id === id ? { ...e, selected: !e.selected } : e));
  }

  function handleConfirm(id: number) {
    setSpans((prev) => prev.map((s) => s.id === id ? { ...s, decision: "confirmed" as const } : s));
  }

  function handleOverride(id: number) {
    setSpans((prev) => prev.map((s) => s.id === id ? { ...s, decision: "override" as const } : s));
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-4xl mx-auto px-6 py-10 flex flex-col gap-12">

        <div>
          <h1 className="text-2xl font-bold text-foreground">Design System Preview</h1>
          <p className="text-sm text-text-muted mt-1">All Epic 0 components — dev-only route</p>
        </div>

        {/* Sync Status Badges */}
        <Section title="SyncStatusBadge">
          <div className="flex flex-wrap gap-3">
            <SyncStatusBadge status="pending" />
            <SyncStatusBadge status="synced" />
            <SyncStatusBadge status="skipped" />
            <SyncStatusBadge status="failed" />
            <SyncStatusBadge status="pending" size="sm" />
            <SyncStatusBadge status="synced"  size="sm" />
            <SyncStatusBadge status="failed"  size="sm" />
          </div>
        </Section>

        {/* Phase Stepper */}
        <Section title="PhaseProgressStepper">
          <PhaseProgressStepper
            phases={PHASES}
            onProceed={() => console.log("proceed")}
            onRerun={() => console.log("rerun")}
          />
        </Section>

        {/* Project Cards */}
        <Section title="ProjectCard">
          <div className="flex flex-col gap-2">
            <ProjectCard
              id="p1"
              name="E-Commerce Platform Rewrite"
              domain="Retail"
              phase="chat"
              syncStatus="synced"
              updated="2 hours ago"
            />
            <ProjectCard
              id="p2"
              name="Internal HR Portal"
              domain="HR"
              phase="synced"
              syncStatus="skipped"
              updated="Yesterday"
            />
            <ProjectCard
              id="p3"
              name="Mobile Banking App"
              domain="FinTech"
              phase="ingestion"
              syncStatus="failed"
              updated="3 days ago"
            />
          </div>
        </Section>

        {/* Epic / Task List */}
        <Section title="EpicTaskListItem">
          <div className="flex flex-col gap-2">
            {epics.map((epic) => (
              <EpicTaskListItem key={epic.id} epic={epic} onToggleSelect={toggleEpic} />
            ))}
          </div>
        </Section>

        {/* Chat Thread */}
        <Section title="ChatThread">
          <div className="border border-border rounded-xl overflow-hidden">
            <ChatThread messages={MESSAGES} isLoading={false} />
          </div>
          <div className="border border-border rounded-xl overflow-hidden">
            <ChatThread messages={[]} isLoading={true} />
          </div>
        </Section>

        {/* TBD Clarification Widget */}
        <Section title="TBDClarificationWidget">
          <TBDClarificationWidget items={tbds} />
        </Section>

        {/* Redaction Highlight */}
        <Section title="RedactionHighlight">
          <RedactionHighlight
            detections={spans}
            onConfirm={handleConfirm}
            onOverride={handleOverride}
          />
        </Section>

        {/* Metrics Stat Cards */}
        <Section title="MetricsStatCard">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <MetricsStatCard
              label="Total Tokens"
              value="78,420"
              delta={{ value: "+12%", direction: "up" }}
            />
            <MetricsStatCard
              label="Est. Cost"
              value="$0.18"
              unit="USD"
              delta={{ value: "-3%", direction: "down" }}
            />
            <MetricsStatCard
              label="Pass Rate"
              value="87"
              unit="%"
              delta={{ value: "stable", direction: "neutral" }}
            />
            <MetricsStatCard
              label="Sync Success"
              value="12 / 13"
              delta={{ value: "1 failed", direction: "down" }}
            />
          </div>
        </Section>

        {/* Line Chart */}
        <Section title="MetricsLineChart">
          <div className="bg-card border border-border rounded-xl p-4">
            <MetricsLineChart
              data={LINE_DATA}
              xKey="day"
              series={[
                { key: "tokens", label: "Tokens" },
                { key: "cost",   label: "Cost (USD)" },
              ]}
              height={200}
            />
          </div>
        </Section>

        {/* Bar Chart */}
        <Section title="MetricsBarChart">
          <div className="bg-card border border-border rounded-xl p-4">
            <MetricsBarChart
              data={BAR_DATA}
              xKey="phase"
              series={[
                { key: "p50", label: "P50 (ms)" },
                { key: "p95", label: "P95 (ms)" },
              ]}
              height={200}
            />
          </div>
        </Section>

        {/* Bar Chart — Stacked */}
        <Section title="MetricsBarChart (stacked)">
          <div className="bg-card border border-border rounded-xl p-4">
            <MetricsBarChart
              data={BAR_DATA}
              xKey="phase"
              series={[
                { key: "p50", label: "P50 (ms)" },
                { key: "p95", label: "P95 (ms)" },
              ]}
              stacked
              height={200}
            />
          </div>
        </Section>

      </div>
    </div>
  );
}
