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
import { MetricInfo } from "@/components/ui/metric-info";

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
  input_tokens: number;
  output_tokens: number;
  tokens_by_phase: { phase: string; tokens: number; cost: number }[];
  daily_token_trend: { day: string; input_tokens: number; output_tokens: number; cost: number }[];
  latency_by_node: { node: string; p50: number; p95: number }[];
  errors_by_phase: { phase: string; errors: number }[];
  error_count: number;
  eval_pass_rate: number;
  github_sync_success_rate: number;
  github_sync_fails: number;
  retrieval_by_query: { query_index: number; n_retrieved: number; top_score: number; avg_score: number }[];
  quality_scores: { grader: string; score: number; source: string }[];
  avg_groundedness: number | null;
};

function TabTokens({ metrics }: { metrics?: ApiMetrics }) {
  const tokensByPhase = metrics?.tokens_by_phase?.length
    ? metrics.tokens_by_phase
    : TOKEN_BY_PHASE_MOCK;
  const totalTokens = metrics?.total_tokens ?? tokensByPhase.reduce((s, r) => s + r.tokens, 0);
  const totalCost   = metrics?.total_cost_usd ?? TOKEN_TREND.reduce((s, r) => s + r.cost, 0);
  const inputTokens = metrics?.input_tokens ?? Math.floor(totalTokens * 0.78);
  const outputTokens = metrics?.output_tokens ?? Math.floor(totalTokens * 0.22);

  const dailyTrend = metrics?.daily_token_trend?.length
    ? metrics.daily_token_trend.map((d) => ({
        ...d,
        day: new Date(d.day + "T00:00:00").toLocaleDateString("en-US", { weekday: "short", month: "numeric", day: "numeric" }),
        input: d.input_tokens,
        output: d.output_tokens,
      }))
    : TOKEN_TREND;

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricsStatCard
          label="Total Tokens" value={totalTokens.toLocaleString("en-US")}
          infoIcon={<MetricInfo what="Sum of all input + output tokens across every LLM call in this project." why="Tracks overall model consumption; rising totals without proportional output quality signal inefficiency." />}
        />
        <MetricsStatCard
          label="Total Cost" value={`$${totalCost.toFixed(3)}`} unit="USD"
          infoIcon={<MetricInfo what="USD cost of all LLM calls using the configured per-token rates." why="Keeps AI spend within budget thresholds." target="< $0.50 / workflow run" />}
        />
        <MetricsStatCard
          label="Input Tokens" value={inputTokens.toLocaleString("en-US")}
          infoIcon={<MetricInfo what="Tokens sent to the model: prompts, context, system messages." why="Large input relative to output signals prompt engineering opportunities (e.g. shorter context windows)." target="~75–85% of total" />}
        />
        <MetricsStatCard
          label="Output Tokens" value={outputTokens.toLocaleString("en-US")}
          infoIcon={<MetricInfo what="Tokens generated by the model: responses and structured outputs." why="High output-to-input ratio may indicate missing max_tokens limits." target="~15–25% of total" />}
        />
      </div>
      <Card>
        <div className="flex items-center gap-1 mb-3">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
            Daily Token Trend{metrics?.daily_token_trend?.length ? "" : " (sample)"}
          </span>
          <MetricInfo what="Input and output tokens grouped by calendar day." why="Identifies usage spikes correlated with development activity or regressions." target="Steady or declining trend" />
        </div>
        <MetricsLineChart data={dailyTrend} xKey="day" series={[{ key: "input", label: "Input" }, { key: "output", label: "Output" }]} height={200} />
      </Card>
      <Card>
        <div className="flex items-center gap-1 mb-3">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Tokens by Phase</span>
          <MetricInfo what="Token breakdown per workflow phase." why="Reveals which phase dominates cost; Phase 2 (RAG chat) typically 50–70%." target="Phase 2 should be largest" />
        </div>
        <MetricsBarChart data={tokensByPhase} xKey="phase" series={[{ key: "tokens", label: "Tokens" }]} height={180} />
      </Card>
    </div>
  );
}

function TabQuality({ metrics }: { metrics?: ApiMetrics }) {
  const hasLiveScores = (metrics?.quality_scores?.length ?? 0) > 0;
  const scores = hasLiveScores
    ? metrics!.quality_scores.map((q) => ({ grader: q.grader, score: q.score }))
    : QUALITY_SCORES;

  const avgScore = scores.reduce((s, r) => s + r.score, 0) / scores.length;
  const passed   = scores.filter((r) => r.score >= 0.75).length;
  const groundedness = metrics?.avg_groundedness != null
    ? `${Math.round(metrics.avg_groundedness * 100)}%`
    : "—";
  const evalPassRate = metrics?.eval_pass_rate
    ? `${Math.round(metrics.eval_pass_rate * 100)}%`
    : `${Math.round(avgScore * 100)}%`;

  const tbdScore = scores.find((r) => r.grader.toLowerCase().includes("tbd"));
  const tbdValue = tbdScore ? `${Math.round(tbdScore.score * 100)}%` : "—";

  const chartData = scores.map((r) => ({ grader: r.grader, score: Math.round(r.score * 100) }));
  const dataSource = hasLiveScores
    ? (metrics!.quality_scores.some((q) => q.source === "eval_run") ? "eval run" : "live")
    : "sample";

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricsStatCard
          label="Avg Pass Rate" value={evalPassRate}
          infoIcon={<MetricInfo what="Mean score across all graders in the latest eval run." why="Single headline quality signal for the AI pipeline." target="≥ 90%" />}
        />
        <MetricsStatCard
          label="Graders Passing" value={`${passed} / ${scores.length}`}
          infoIcon={<MetricInfo what="Count of graders scoring ≥ 0.75 out of total graders evaluated." why="Shows breadth of quality coverage; one failing grader can indicate a systemic regression." target="All passing" />}
        />
        <MetricsStatCard
          label="Groundedness" value={groundedness}
          infoIcon={<MetricInfo what="Average fraction of chat responses fully supported by retrieved context (0–1)." why="Measures hallucination risk — below 0.70 means the model is generating unsupported claims." target="≥ 0.70" />}
        />
        <MetricsStatCard
          label="TBD Detection" value={tbdValue} unit="explicit"
          infoIcon={<MetricInfo what="Pass rate of the explicit TBD detection grader from the offline eval suite." why="Ensures requirement gaps are flagged reliably before they become sprint blockers." target="100%" />}
        />
      </div>
      <Card>
        <div className="flex items-center gap-1 mb-3">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
            Pass Rate by Grader{dataSource !== "sample" ? ` (${dataSource})` : " (sample — run eval_suite.py --persist-db)"}
          </span>
          <MetricInfo what="Per-grader score bars from the latest eval run." why="Pinpoints which specific capability is degrading; each grader tests one system behavior in isolation." target="≥ 75% per grader" />
        </div>
        <MetricsBarChart
          data={chartData}
          xKey="grader"
          series={[{ key: "score", label: "Pass Rate (%)" }]}
          height={200}
        />
      </Card>
    </div>
  );
}

function TabRetrieval({ metrics }: { metrics?: ApiMetrics }) {
  const hasLiveData = (metrics?.retrieval_by_query?.length ?? 0) > 0;

  const retrievalData = hasLiveData
    ? metrics!.retrieval_by_query.map((r) => ({
        phase: `Q${r.query_index}`,
        recall: Math.round(r.avg_score * 100),
        relevancy: Math.round(r.top_score * 100),
      }))
    : RETRIEVAL_BY_PHASE.map((r) => ({ ...r, recall: Math.round(r.recall * 100), relevancy: Math.round(r.relevancy * 100) }));

  const avgRecall = hasLiveData
    ? metrics!.retrieval_by_query.reduce((s, r) => s + r.avg_score, 0) / metrics!.retrieval_by_query.length
    : RETRIEVAL_BY_PHASE.reduce((s, r) => s + r.recall, 0) / RETRIEVAL_BY_PHASE.length;

  const avgRelevancy = hasLiveData
    ? metrics!.retrieval_by_query.reduce((s, r) => s + r.top_score, 0) / metrics!.retrieval_by_query.length
    : RETRIEVAL_BY_PHASE.reduce((s, r) => s + r.relevancy, 0) / RETRIEVAL_BY_PHASE.length;

  const rerankerPrecision = hasLiveData
    ? `${Math.round(avgRelevancy * 100)}%`
    : "74%";

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricsStatCard
          label="Context Recall" value={`${Math.round(avgRecall * 100)}%`}
          delta={avgRecall >= 0.80 ? { value: "≥ 0.80 target ✓", direction: "up" } : { value: "< 0.80 target", direction: "down" }}
          infoIcon={<MetricInfo what="Mean of avg reranker scores per query — proxy for how much relevant content reaches the LLM context." why="Low recall means useful document sections are not reaching the model, causing hallucination or refusals." target="≥ 80%" />}
        />
        <MetricsStatCard
          label="Answer Relevancy" value={`${Math.round(avgRelevancy * 100)}%`}
          delta={avgRelevancy >= 0.75 ? { value: "≥ 0.75 target ✓", direction: "up" } : { value: "< 0.75 target", direction: "down" }}
          infoIcon={<MetricInfo what="Mean of top reranker scores per query — proxy for how well the highest-ranked chunk matches the question." why="A low top score indicates the corpus lacks the answer for that query." target="≥ 75%" />}
        />
        <MetricsStatCard
          label="Reranker Precision" value={rerankerPrecision}
          infoIcon={<MetricInfo what="Average top reranker score as a percentage — BERT cross-encoder confidence." why="Indicates how well the reranker separates relevant from irrelevant chunks." target="≥ 70%" />}
        />
        <MetricsStatCard
          label="Query Rewrites" value="3" unit="/ query"
          infoIcon={<MetricInfo what="Sub-queries generated per user question via LLM rewriting." why="More rewrites improve hybrid retrieval coverage at the cost of latency; fixed at 3 by default." target="3 (configurable via QUERY_REWRITE_COUNT)" />}
        />
      </div>
      <Card>
        <div className="flex items-center gap-1 mb-3">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
            {hasLiveData ? "Context Recall vs Relevancy per Query (proxy)" : "Recall vs Relevancy per Query (sample)"}
          </span>
          <MetricInfo what="Per-query avg score (recall proxy) and top score (relevancy proxy) as a line chart." why="Identifies specific queries where retrieval degrades — useful for curating the document corpus." target="Both lines ≥ 75%" />
        </div>
        <MetricsLineChart
          data={retrievalData}
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
  const syncFails = metrics?.github_sync_fails ?? "—";
  const recoveryRate = metrics != null
    ? `${Math.round(metrics.github_sync_success_rate * 100)}%`
    : "—";
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricsStatCard
          label="Total Errors" value={totalErrors}
          delta={{ value: totalErrors === 0 ? "clean run" : "investigate", direction: totalErrors === 0 ? "up" : "down" }}
          infoIcon={<MetricInfo what="Count of all errors logged to error_logs for this project." why="Baseline error budget; any errors in a completed workflow run warrant investigation." target="0 errors" />}
        />
        <MetricsStatCard
          label="GitHub Sync Fails" value={syncFails}
          infoIcon={<MetricInfo what="Count of epics and tasks where sync_status = 'failed'." why="A failed sync means GitHub issues were not created and the PM's output is incomplete." target="0 failures" />}
        />
        <MetricsStatCard
          label="Recovery Rate" value={recoveryRate}
          infoIcon={<MetricInfo what="Percentage of epics and tasks with sync_status = 'synced' out of all sync attempts." why="Measures the resilience of the GitHub sync pipeline; tracks improvement after retries." target="100%" />}
        />
        <MetricsStatCard
          label="Error Phases" value={errorsByPhase.filter(p => p.errors > 0).length}
          infoIcon={<MetricInfo what="Number of distinct workflow phases that had at least one error." why="Identifies whether errors are isolated to one phase or indicate a systemic failure." target="0 phases with errors" />}
        />
      </div>
      <Card>
        <div className="flex items-center gap-1 mb-3">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Errors by Phase</span>
          <MetricInfo what="Error count per workflow phase." why="Shows which phase is most error-prone; guides debugging effort." target="All bars at 0" />
        </div>
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
        <MetricsStatCard
          label="P50 Total" value={`${(p50Total / 1000).toFixed(1)}s`}
          delta={{ value: "end-to-end", direction: "neutral" }}
          infoIcon={<MetricInfo what="Median end-to-end latency summed across all LangGraph nodes." why="Represents the typical workflow duration users experience." target="< 60s total" />}
        />
        <MetricsStatCard
          label="P95 Total" value={`${(p95Total / 1000).toFixed(1)}s`}
          infoIcon={<MetricInfo what="95th-percentile latency sum across all nodes." why="Captures tail latency that degrades user experience under load." target="< 120s total" />}
        />
        <MetricsStatCard
          label="Slowest Node" value={slowest?.node ?? "—"} unit={slowest ? `${slowest.p50.toFixed(0)}ms p50` : ""}
          infoIcon={<MetricInfo what="The LangGraph node with the highest median (P50) duration." why="First optimization target; LLM inference nodes typically dominate." />}
        />
        <MetricsStatCard
          label="Fastest Node" value={fastest?.node ?? "—"} unit={fastest ? `${fastest.p50.toFixed(0)}ms p50` : ""}
          infoIcon={<MetricInfo what="The LangGraph node with the lowest median (P50) duration." why="Establishes a baseline for fast operations; useful for comparison." />}
        />
      </div>
      <Card>
        <div className="flex items-center gap-1 mb-3">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">P50 / P95 Latency per LangGraph Node (ms)</span>
          <MetricInfo what="Grouped bar chart of median and 95th-percentile latency per node." why="Reveals nodes with high variance (large P95/P50 gap) that may need timeout or retry tuning." target="P95/P50 ratio < 3×" />
        </div>
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
      {activeTab === "Token Usage & Cost" && <TabTokens   metrics={metricsData} />}
      {activeTab === "AI Quality"         && <TabQuality  metrics={metricsData} />}
      {activeTab === "Retrieval"          && <TabRetrieval metrics={metricsData} />}
      {activeTab === "Error Handling"     && <TabErrors   metrics={metricsData} />}
      {activeTab === "Latency"            && <TabLatency  metrics={metricsData} />}
    </div>
  );
}
