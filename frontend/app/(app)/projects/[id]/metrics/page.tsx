"use client";

import { useState, use } from "react";
import { useQuery } from "@tanstack/react-query";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { MetricsStatCard } from "@/components/metrics-stat-card";
import { MetricsLineChart } from "@/components/metrics-line-chart";
import { MetricsBarChart } from "@/components/metrics-bar-chart";
import { getPhasesForRoute } from "@/lib/project-phases";
import { getMetrics } from "@/lib/api";
import { cn } from "@/lib/utils";

// ── Fallback mock data (shown while loading or when no runs yet) ──────────────

const TOKEN_TREND = [
  { day: "Mon", input: 12400, output: 3200, cost: 0.025 },
  { day: "Tue", input: 18700, output: 5100, cost: 0.038 },
  { day: "Wed", input: 9200,  output: 2800, cost: 0.019 },
  { day: "Thu", input: 22100, output: 6400, cost: 0.044 },
  { day: "Fri", input: 15800, output: 4300, cost: 0.031 },
];

const TOKEN_BY_PHASE_MOCK = [
  { phase: "Ingest",   tokens: 8400 },
  { phase: "RAG",      tokens: 31200 },
  { phase: "Stack",    tokens: 9800 },
  { phase: "Team",     tokens: 7100 },
  { phase: "Estimate", tokens: 14600 },
  { phase: "Epics",    tokens: 7100 },
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

const ERRORS_BY_PHASE_MOCK = [
  { phase: "Ingest",   errors: 0 },
  { phase: "RAG",      errors: 2 },
  { phase: "Stack",    errors: 0 },
  { phase: "Team",     errors: 1 },
  { phase: "Estimate", errors: 0 },
  { phase: "Sync",     errors: 1 },
];

const LATENCY_BY_NODE_MOCK = [
  { node: "Ingest",   p50: 420,  p95: 890 },
  { node: "Embed",    p50: 1240, p95: 2800 },
  { node: "Rewrite",  p50: 380,  p95: 720 },
  { node: "Retrieve", p50: 290,  p95: 610 },
  { node: "Rerank",   p50: 680,  p95: 1400 },
  { node: "LLM",      p50: 2100, p95: 4800 },
  { node: "Sync",     p50: 510,  p95: 1100 },
];

// ── Tab definitions ───────────────────────────────────────────────────────────

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

// ── Tab panels ────────────────────────────────────────────────────────────────

type ApiMetrics = {
  total_tokens: number;
  total_cost_usd: number;
  tokens_by_phase: { phase: string; tokens: number; cost: number }[];
  latency_by_node: { node: string; p50: number; p95: number }[];
  errors_by_phase: { phase: string; errors: number }[];
  error_count: number;
};

function TabTokens({ metrics }: { metrics?: ApiMetrics }) {
  const tokensByPhase = metrics?.tokens_by_phase?.length
    ? metrics.tokens_by_phase
    : TOKEN_BY_PHASE_MOCK;
  const totalTokens = metrics?.total_tokens ?? tokensByPhase.reduce((s, r) => s + r.tokens, 0);
  const totalCost   = metrics?.total_cost_usd ?? TOKEN_TREND.reduce((s, r) => s + r.cost, 0);
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricsStatCard label="Total Tokens"  value={totalTokens.toLocaleString('en-US')} />
        <MetricsStatCard label="Total Cost"    value={`$${totalCost.toFixed(3)}`} unit="USD" />
        <MetricsStatCard label="Input Tokens"  value={Math.floor(totalTokens * 0.78).toLocaleString('en-US')} />
        <MetricsStatCard label="Output Tokens" value={Math.floor(totalTokens * 0.22).toLocaleString('en-US')} />
      </div>
      <Card>
        <SectionLabel>Daily Token Trend</SectionLabel>
        <MetricsLineChart data={TOKEN_TREND} xKey="day" series={[{ key: "input", label: "Input" }, { key: "output", label: "Output" }]} height={200} />
      </Card>
      <Card>
        <SectionLabel>Tokens by Phase</SectionLabel>
        <MetricsBarChart data={tokensByPhase} xKey="phase" series={[{ key: "tokens", label: "Tokens" }]} height={180} />
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
        <MetricsStatCard label="Context Recall"     value={`${Math.round(avgRecall * 100)}%`}    delta={{ value: "≥ 0.80 target ✓", direction: "up" }} />
        <MetricsStatCard label="Answer Relevancy"   value={`${Math.round(avgRelevancy * 100)}%`} delta={{ value: "≥ 0.75 target ✓", direction: "up" }} />
        <MetricsStatCard label="Reranker Precision" value="74%"  delta={{ value: "≥ 70% target ✓", direction: "up" }} />
        <MetricsStatCard label="Query Rewrites"     value="3" unit="/ query" />
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

function TabErrors({ metrics }: { metrics?: ApiMetrics }) {
  const errorsByPhase = metrics?.errors_by_phase?.length
    ? metrics.errors_by_phase
    : ERRORS_BY_PHASE_MOCK;
  const totalErrors = metrics?.error_count ?? errorsByPhase.reduce((s, r) => s + r.errors, 0);
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricsStatCard label="Total Errors"     value={totalErrors} delta={{ value: totalErrors === 0 ? "clean run" : "investigate", direction: totalErrors === 0 ? "up" : "down" }} />
        <MetricsStatCard label="GitHub Sync Fails" value="0" />
        <MetricsStatCard label="Recovery Rate"    value="—" />
        <MetricsStatCard label="Error Phases"     value={errorsByPhase.filter(p => p.errors > 0).length} />
      </div>
      <Card>
        <SectionLabel>Errors by Phase</SectionLabel>
        <MetricsBarChart
          data={errorsByPhase}
          xKey="phase"
          series={[{ key: "errors", label: "Errors" }]}
          height={200}
        />
      </Card>
    </div>
  );
}

function TabLatency({ metrics }: { metrics?: ApiMetrics }) {
  const latencyByNode = metrics?.latency_by_node?.length
    ? metrics.latency_by_node
    : LATENCY_BY_NODE_MOCK;
  const p50Total = latencyByNode.reduce((s, r) => s + r.p50, 0);
  const p95Total = latencyByNode.reduce((s, r) => s + r.p95, 0);
  const slowest  = latencyByNode.reduce((a, b) => a.p50 > b.p50 ? a : b, latencyByNode[0]);
  const fastest  = latencyByNode.reduce((a, b) => a.p50 < b.p50 ? a : b, latencyByNode[0]);
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricsStatCard label="P50 Total"    value={`${(p50Total / 1000).toFixed(1)}s`} delta={{ value: "end-to-end", direction: "neutral" }} />
        <MetricsStatCard label="P95 Total"    value={`${(p95Total / 1000).toFixed(1)}s`} />
        <MetricsStatCard label="Slowest Node" value={slowest?.node ?? "—"} unit={slowest ? `${slowest.p50.toFixed(0)}ms p50` : ""} />
        <MetricsStatCard label="Fastest Node" value={fastest?.node ?? "—"} unit={fastest ? `${fastest.p50.toFixed(0)}ms p50` : ""} />
      </div>
      <Card>
        <SectionLabel>P50 / P95 Latency per LangGraph Node (ms)</SectionLabel>
        <MetricsBarChart
          data={latencyByNode}
          xKey="node"
          series={[{ key: "p50", label: "P50 (ms)" }, { key: "p95", label: "P95 (ms)" }]}
          height={220}
        />
      </Card>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function MetricsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [activeTab, setActiveTab] = useState<Tab>("Token Usage & Cost");

  const { data: metricsData } = useQuery({
    queryKey: ["metrics", id],
    queryFn: async () => {
      const { data } = await getMetrics(id);
      return data as ApiMetrics | undefined;
    },
    enabled: !!id,
    refetchInterval: 30_000,
  });

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
      {activeTab === "Token Usage & Cost" && <TabTokens  metrics={metricsData} />}
      {activeTab === "AI Quality"         && <TabQuality />}
      {activeTab === "Retrieval"          && <TabRetrieval />}
      {activeTab === "Error Handling"     && <TabErrors   metrics={metricsData} />}
      {activeTab === "Latency"            && <TabLatency  metrics={metricsData} />}
    </div>
  );
}
