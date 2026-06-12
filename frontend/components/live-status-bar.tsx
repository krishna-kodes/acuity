"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { _apiBase } from "@/lib/api";

interface LiveStatusBarProps {
  projectId: string;
  className?: string;
}

interface LiveStatus {
  agent: string | null;
  model: string | null;
  total_tokens: number;
  session_cost_usd: number;
  last_node: string | null;
  last_latency_ms: number | null;
  llm_call_count: number;
  active_phase: string | null;
  token_budget: number;
  is_recent: boolean;
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
  const [data, setData] = useState<LiveStatus | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    function connect() {
      const es = new EventSource(`${_apiBase()}/api/v1/projects/${projectId}/live-status/stream`);
      esRef.current = es;

      es.onmessage = (e) => {
        try {
          setData(JSON.parse(e.data) as LiveStatus);
        } catch { /* skip malformed frame */ }
      };

      es.onerror = () => {
        es.close();
        // reconnect after 3s backoff
        setTimeout(connect, 3_000);
      };
    }

    connect();
    return () => {
      esRef.current?.close();
    };
  }, [projectId]);

  const tokenPct = data
    ? Math.min((data.total_tokens / (data.token_budget || 100_000)) * 100, 100)
    : 0;

  return (
    <div className={cn(
      "flex items-center px-4 h-9 bg-[#0f1117] border-b border-white/8 text-[11px] font-mono overflow-x-auto shrink-0",
      className
    )}>
      {/* Agent + model */}
      <span className="flex items-center gap-1.5 pr-3 border-r border-white/10 shrink-0">
        <span className={cn(
          "w-1.5 h-1.5 rounded-full",
          data?.is_recent ? "bg-green-400 animate-pulse" : "bg-white/20"
        )} />
        <span className="text-white/50">Agent</span>
        <span className="text-white/90 ml-1">{data?.agent ?? "—"}</span>
        {data?.model && (
          <span className="text-white/40 ml-1">{data.model}</span>
        )}
      </span>

      {/* Tokens + progress bar */}
      <span className="flex items-center gap-2 px-3 border-r border-white/10 shrink-0">
        <span className="text-white/50">Tokens</span>
        <span className="text-white/90">{fmt(data?.total_tokens ?? 0)}</span>
        <span className="w-16 h-1 bg-white/10 rounded-full overflow-hidden">
          <span
            className="block h-full bg-primary rounded-full transition-all duration-500"
            style={{ width: `${tokenPct}%` }}
          />
        </span>
        <span className="text-white/40">{fmt(data?.token_budget ?? 100_000)}</span>
      </span>

      {/* Cost */}
      <span className="flex items-center gap-1.5 px-3 border-r border-white/10 shrink-0">
        <span className="text-white/50">$</span>
        <span className={cn(
          "font-semibold",
          (data?.session_cost_usd ?? 0) > 0.3 ? "text-amber-400" : "text-emerald-400"
        )}>
          {(data?.session_cost_usd ?? 0).toFixed(4)}
        </span>
      </span>

      {/* Last tool/node */}
      {data?.last_node && (
        <span className="flex items-center gap-1.5 px-3 border-r border-white/10 shrink-0">
          <span className="text-white/50">Tool</span>
          <span className="text-violet-300">{fmtNode(data.last_node)}</span>
        </span>
      )}

      {/* Latency */}
      {data?.last_latency_ms != null && (
        <span className="flex items-center gap-1.5 px-3 border-r border-white/10 shrink-0">
          <span className="text-white/50">Latency</span>
          <span className="text-white/90">{fmtLatency(data.last_latency_ms)}</span>
        </span>
      )}

      {/* LLM call count */}
      <span className="flex items-center gap-1.5 px-3 shrink-0">
        <span className="text-white/50">LLM</span>
        <span className="text-white/90">{data?.llm_call_count ?? 0}</span>
      </span>
    </div>
  );
}
