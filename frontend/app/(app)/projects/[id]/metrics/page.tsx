"use client";

import { useState } from "react";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { MetricsStatCard } from "@/components/metrics-stat-card";
import { MetricsLineChart } from "@/components/metrics-line-chart";
import { MetricsBarChart } from "@/components/metrics-bar-chart";
import { getPhasesForRoute } from "@/lib/project-phases";
import { cn } from "@/lib/utils";

// ── Mock data ────────────────────────────────────────────────────────────────
// TODO (Epic 4): fetch from GET /api/v1/projects/{id}/metrics

const TOKEN_TREND = [
  { day: "Mon", input: 12400, output: 3200, cost: 0.025 },
  { day: "Tue", input: 18700, output: 5100, cost: 0.038 },
  { day: "Wed", input: 9200,  output: 2800, cost: 0.019 },
  { day: "Thu", input: 22100, output: 6400, cost: 0.044 },
  { day: "Fri", input: 15800, output: 4300, cost: 0.031 },
];

const TOKEN_BY_PHASE = [
  { phase: "Ingest",  tokens: 8400 },
  { phase: "RAG",     tokens: 31200 },
  { phase: "Stack",   tokens: 9800 },
  { phase: "Team",    tokens: 7100 },
  { phase: "Estimate",tokens: 14600 },
  { phase: "Epics",   tokens: 7100 },
];

const QUALITY_SCORES = [
  { grader: "Retrieval",    score: 0.83 },
  { grader: "Relevancy",    score: 0.78 },
  { grader: "Reranker",     score: 0.74 },
  { grader: "TBD explicit", score: 1.00 },
  { grader: "TBD vague",    score: 0.72 },
  { grader: "Proposal",     score: 0.76 },
  { grader: "Groundedness", score: 0.81 },
  { grader: "GitHub schema",score: 1.00 },
];

const RETRIEVAL_BY_PHASE = [
  { phase: "Q1", recall: 0.88, relevancy: 0.82 },
  { phase: "Q2", recall: 0.91, relevancy: 0.85 },
  { phase: "Q3", recall: 0.79, relevancy: 0.74 },
  { phase: "Q4", recall: 0.93, relevancy: 0.89 },
  { phase: "Q5", recall: 0.87, relevancy: 0.83 },
];

const ERRORS_BY_PHASE = [
  { phase: "Ingest",  errors: 0, retries: 1 },
  { phase: "RAG",     errors: 2, retries: 4 },
  { phase: "Stack",   errors: 0, retries: 0 },
  { phase: "Team",    errors: 1, retries: 2 },
  { phase: "Estimate",errors: 0, retries: 1 },
  { phase: "Sync",    errors: 1, retries: 3 },
];

const LATENCY_BY_NODE = [
  { node: "Ingest",   p50: 420,  p95: 890 },
  { node: "Embed",    p50: 1240, p95: 2800 },
  { node: "Rewrite",  p50: 380,  p95: 720 },
  { node: "Retrieve", p50: 290,  p95: 610 },
  { node: "Rerank",   p50: 680,  p95: 1400 },
  { node: "LLM",      p50: 2100, p95: 4800 },
  { node: "Sync",     p50: 510,  p95: 1100 },
];

// ── Tab definitions ──────────────────────────────────────────────────────────

const TABS = [
  "Token Usage & Cost",
  "AI Quality",
  "Retrieval",
  "Error Handling",
  "Latency",
] as const;
type Tab = typeof TABS[number];

// ── Section wrapper ───────────────────────────────────────────────────────────

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("bg-card border border-border rounded-xl p-4", className)}>
      {children}
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted mb-3">
      {children}
    </p>
  );
}

// ── Tab panels ───────────────────────────────────────────────────────────────

function TabTokens() {
  const totalTokens = TOKEN_BY_PHASE.reduce((s, r) => s + r.tokens, 0);
  const totalCost   = TOKEN_TREND.reduce((s, r) => s + r.cost, 0);
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricsStatCard label="Total Tokens"   value={totalTokens.toLocaleString()} />
        <MetricsStatCard label="Total Cost"     value={`$${totalCost.toFixed(3)}`} unit="USD" delta={{ value: "-8% vs last run", direction: "down" }} />
        <MetricsStatCard label="Input Tokens"   value={(totalTokens * 0.78).toLocaleString().split(".")[0]} />
        <MetricsStatCard label="Output Tokens"  value={(totalTokens * 0.22).toLocaleString().split(".")[0]} />
      </div>
      <Card>
        <SectionLabel>Daily Token Trend</SectionLabel>
        <MetricsLineChart data={TOKEN_TREND} xKey="day" series={[{ key: "input", label: "Input" }, { key: "output", label: "Output" }]} height={200} />
      </Card>
      <Card>
        <SectionLabel>Tokens by Phase</SectionLabel>
        <MetricsBarChart data={TOKEN_BY_PHASE} xKey="phase" series={[{ key: "tokens", label: "Tokens" }]} height={180} />
      </Card>
    </div>
  );
}

function TabQuality() {
  const avgScore = QUALITY_SCORES.reduce((s, r) => s + r.score, 0) / QUALITY_SCORES.length;
  const passed   = QUALITY_SCORES.filter((r) => r.score >= 0.75).length;
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricsStatCard label="Avg Pass Rate"   value={`${Math.round(avgScore * 100)}%`} delta={{ value: "+4% vs baseline", direction: "up" }} />
        <MetricsStatCard label="Graders Passing" value={`${passed} / ${QUALITY_SCORES.length}`} />
        <MetricsStatCard label="Groundedness"    value="81%" delta={{ value: "+11% vs baseline", direction: "up" }} />
        <MetricsStatCard label="TBD Detection"   value="100%" unit="explicit" />
      </div>
      <Card>
        <SectionLabel>Pass Rate by Grader</SectionLabel>
        <MetricsBarChart
          data={QUALITY_SCORES.map((r) => ({ grader: r.grader, score: Math.round(r.score * 100) }))}
          xKey="grader"
          series={[{ key: "score", label: "Pass Rate (%)" }]}
          height={200}
        />
      </Card>
    </div>
  );
}

function TabRetrieval() {
  const avgRecall    = RETRIEVAL_BY_PHASE.reduce((s, r) => s + r.recall, 0) / RETRIEVAL_BY_PHASE.length;
  const avgRelevancy = RETRIEVAL_BY_PHASE.reduce((s, r) => s + r.relevancy, 0) / RETRIEVAL_BY_PHASE.length;
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricsStatCard label="Context Recall"    value={`${Math.round(avgRecall * 100)}%`}    delta={{ value: "≥ 0.80 target ✓", direction: "up" }} />
        <MetricsStatCard label="Answer Relevancy"  value={`${Math.round(avgRelevancy * 100)}%`} delta={{ value: "≥ 0.75 target ✓", direction: "up" }} />
        <MetricsStatCard label="Reranker Precision" value="74%"  delta={{ value: "≥ 70% target ✓", direction: "up" }} />
        <MetricsStatCard label="Query Rewrites"    value="3" unit="/ query" />
      </div>
      <Card>
        <SectionLabel>Recall vs Relevancy per Query</SectionLabel>
        <MetricsLineChart
          data={RETRIEVAL_BY_PHASE.map((r) => ({ ...r, recall: Math.round(r.recall * 100), relevancy: Math.round(r.relevancy * 100) }))}
          xKey="phase"
          series={[{ key: "recall", label: "Context Recall (%)" }, { key: "relevancy", label: "Answer Relevancy (%)" }]}
          height={200}
        />
      </Card>
    </div>
  );
}

function TabErrors() {
  const totalErrors  = ERRORS_BY_PHASE.reduce((s, r) => s + r.errors, 0);
  const totalRetries = ERRORS_BY_PHASE.reduce((s, r) => s + r.retries, 0);
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricsStatCard label="Total Errors"    value={totalErrors}  delta={{ value: totalErrors === 0 ? "clean run" : "investigate", direction: totalErrors === 0 ? "up" : "down" }} />
        <MetricsStatCard label="Total Retries"   value={totalRetries} />
        <MetricsStatCard label="GitHub Sync Fails" value="1" delta={{ value: "token expired", direction: "down" }} />
        <MetricsStatCard label="Recovery Rate"   value="75%" delta={{ value: "3 / 4 retried ok", direction: "up" }} />
      </div>
      <Card>
        <SectionLabel>Errors &amp; Retries by Phase</SectionLabel>
        <MetricsBarChart
          data={ERRORS_BY_PHASE}
          xKey="phase"
          series={[{ key: "errors", label: "Errors" }, { key: "retries", label: "Retries" }]}
          height={200}
          stacked
        />
      </Card>
      <Card>
        <SectionLabel>Recent Errors</SectionLabel>
        <div className="flex flex-col divide-y divide-border">
          {[
            { phase: "RAG",  code: "LLM_TIMEOUT",    msg: "Gemini 1.5 Pro response timeout after 30s. Retried ×2, succeeded.",    ts: "Thu 14:22" },
            { phase: "RAG",  code: "HALLUCINATION",  msg: "Groundedness score 0.58 — below threshold 0.70. Response flagged.",    ts: "Thu 15:07" },
            { phase: "Team", code: "DB_QUERY_SLOW",  msg: "Employee skills query >500ms. WAL mode enabled, resolved on retry.",   ts: "Fri 09:13" },
            { phase: "Sync", code: "GITHUB_401",     msg: "GitHub token expired. Update GITHUB_TOKEN in .env and re-sync.",        ts: "Fri 11:45" },
          ].map((e, i) => (
            <div key={i} className="flex items-start gap-3 py-2.5">
              <span className="text-[10px] font-mono bg-destructive-subtle text-destructive px-1.5 py-0.5 rounded shrink-0 mt-0.5">{e.code}</span>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-foreground">{e.msg}</p>
                <p className="text-[10px] text-text-muted mt-0.5">{e.phase} · {e.ts}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function TabLatency() {
  const p50Total = LATENCY_BY_NODE.reduce((s, r) => s + r.p50, 0);
  const p95Total = LATENCY_BY_NODE.reduce((s, r) => s + r.p95, 0);
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricsStatCard label="P50 Total"  value={`${(p50Total / 1000).toFixed(1)}s`} delta={{ value: "end-to-end", direction: "neutral" }} />
        <MetricsStatCard label="P95 Total"  value={`${(p95Total / 1000).toFixed(1)}s`} />
        <MetricsStatCard label="Slowest Node" value="LLM" unit="2.1s p50" />
        <MetricsStatCard label="Fastest Node" value="Retrieve" unit="290ms p50" />
      </div>
      <Card>
        <SectionLabel>P50 / P95 Latency per LangGraph Node (ms)</SectionLabel>
        <MetricsBarChart
          data={LATENCY_BY_NODE}
          xKey="node"
          series={[{ key: "p50", label: "P50 (ms)" }, { key: "p95", label: "P95 (ms)" }]}
          height={220}
        />
      </Card>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function MetricsPage({ params: _ }: { params: { id: string } }) {
  const [activeTab, setActiveTab] = useState<Tab>("Token Usage & Cost");

  return (
    <div className="px-6 py-8 max-w-4xl mx-auto flex flex-col gap-6">
      <PhaseProgressStepper phases={getPhasesForRoute("metrics")} />

      {/* Tab bar */}
      <div className="flex gap-1 p-1 bg-surface-subtle border border-border rounded-lg overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              "shrink-0 px-3 py-1.5 rounded-md text-xs font-medium transition-colors whitespace-nowrap",
              activeTab === tab
                ? "bg-card text-foreground shadow-sm border border-border"
                : "text-text-secondary hover:text-foreground hover:bg-card/60"
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Active tab content */}
      {activeTab === "Token Usage & Cost" && <TabTokens />}
      {activeTab === "AI Quality"         && <TabQuality />}
      {activeTab === "Retrieval"          && <TabRetrieval />}
      {activeTab === "Error Handling"     && <TabErrors />}
      {activeTab === "Latency"            && <TabLatency />}
    </div>
  );
}
