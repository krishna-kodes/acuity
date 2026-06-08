"use client";

import { useQuery } from "@tanstack/react-query";
import { getLiveStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

interface LiveStatusBarProps {
  projectId: string;
  className?: string;
}

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function fmtLatency(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}

function fmtNode(node: string): string {
  return node.replace(/_node$/, "") + "()";
}

export function LiveStatusBar({ projectId, className }: LiveStatusBarProps) {
  const { data } = useQuery({
    queryKey: ["live-status", projectId],
    queryFn: () => getLiveStatus(projectId),
    refetchInterval: 5_000,
    staleTime: 0,
  });

  if (!data || data.llm_call_count === 0) return null;

  const tokenPct = Math.min((data.total_tokens / data.token_budget) * 100, 100);

  return (
    <div className={cn(
      "flex items-center px-4 h-9 bg-[#0f1117] border-b border-white/8 text-[11px] font-mono overflow-x-auto shrink-0",
      className
    )}>
      {/* Agent + model */}
      <span className="flex items-center gap-1.5 pr-3 border-r border-white/10 shrink-0">
        <span className={cn(
          "w-1.5 h-1.5 rounded-full",
          data.is_recent ? "bg-green-400 animate-pulse" : "bg-white/20"
        )} />
        <span className="text-white/50">Agent</span>
        <span className="text-white/90 ml-1">{data.agent ?? "—"}</span>
        {data.model && (
          <span className="text-white/40 ml-1">{data.model}</span>
        )}
      </span>

      {/* Tokens + progress bar */}
      <span className="flex items-center gap-2 px-3 border-r border-white/10 shrink-0">
        <span className="text-white/50">Tokens</span>
        <span className="text-white/90">{fmt(data.total_tokens)}</span>
        <span className="w-16 h-1 bg-white/10 rounded-full overflow-hidden">
          <span
            className="block h-full bg-primary rounded-full transition-all duration-500"
            style={{ width: `${tokenPct}%` }}
          />
        </span>
        <span className="text-white/40">{fmt(data.token_budget)}</span>
      </span>

      {/* Cost */}
      <span className="flex items-center gap-1.5 px-3 border-r border-white/10 shrink-0">
        <span className="text-white/50">$</span>
        <span className={cn(
          "font-semibold",
          data.session_cost_usd > 0.3 ? "text-amber-400" : "text-emerald-400"
        )}>
          {data.session_cost_usd.toFixed(4)}
        </span>
      </span>

      {/* Last tool/node */}
      {data.last_node && (
        <span className="flex items-center gap-1.5 px-3 border-r border-white/10 shrink-0">
          <span className="text-white/50">Tool</span>
          <span className="text-violet-300">{fmtNode(data.last_node)}</span>
        </span>
      )}

      {/* Latency */}
      {data.last_latency_ms != null && (
        <span className="flex items-center gap-1.5 px-3 border-r border-white/10 shrink-0">
          <span className="text-white/50">Latency</span>
          <span className="text-white/90">{fmtLatency(data.last_latency_ms)}</span>
        </span>
      )}

      {/* LLM call count */}
      <span className="flex items-center gap-1.5 px-3 shrink-0">
        <span className="text-white/50">LLM</span>
        <span className="text-white/90">{data.llm_call_count}</span>
      </span>
    </div>
  );
}
