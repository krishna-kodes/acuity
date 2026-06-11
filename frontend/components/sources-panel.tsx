"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import type { ChatSource } from "@/components/chat-thread";

interface SourcesPanelProps {
  sources: ChatSource[];
  activeChunkId: string | null;
  onBack: () => void;
}

export function SourcesPanel({ sources, activeChunkId, onBack }: SourcesPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Scroll the active citation into view + highlight when it changes.
  useEffect(() => {
    if (!activeChunkId || !containerRef.current) return;
    const el = containerRef.current.querySelector<HTMLElement>(
      `[data-chunk-id="${CSS.escape(activeChunkId)}"]`,
    );
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [activeChunkId, sources]);

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-xs text-text-muted hover:text-foreground transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}>
            <path d="M9 3L5 7l4 4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Back
        </button>
        <span className="text-xs font-semibold text-foreground">
          {sources.length} Source{sources.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Source cards */}
      <div ref={containerRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {sources.length === 0 ? (
          <p className="text-xs text-text-muted">No sources for this message.</p>
        ) : (
          sources.map((s, i) => {
            const isActive = s.chunk_id === activeChunkId;
            return (
              <div
                key={s.chunk_id || i}
                data-chunk-id={s.chunk_id}
                className={cn(
                  "rounded-lg border p-3 transition-colors",
                  isActive
                    ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                    : "border-border bg-surface-subtle",
                )}
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <span className="text-xs font-semibold text-foreground truncate">
                    {s.section_hint || "Untitled section"}
                  </span>
                  {s.page_number != null && (
                    <span className="text-[10px] text-text-muted shrink-0">p.{s.page_number}</span>
                  )}
                </div>
                {s.text ? (
                  <p className="text-[11px] text-text-secondary leading-relaxed whitespace-pre-wrap line-clamp-[12]">
                    {s.text}
                  </p>
                ) : (
                  <p className="text-[11px] text-text-muted italic">Snippet unavailable.</p>
                )}
              </div>
            );
          })
        )}
      </div>
    </>
  );
}
