"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

export type RedactionDecision = "confirmed" | "override";

export interface RedactionSpan {
  id: number;
  original: string;
  type: string;
  method: string;
  placeholder: string;
  confidence: number;
  decision?: RedactionDecision;
}

interface RedactionHighlightProps {
  detections: RedactionSpan[];
  onConfirm?: (id: number) => void;
  onOverride?: (id: number) => void;
  onConfirmAll?: () => void;
  onUndo?: (id: number) => void;
  onConfirmSelected?: (ids: number[]) => void;
  onOverrideSelected?: (ids: number[]) => void;
  className?: string;
}

const TYPE_COLOR: Record<string, string> = {
  Email:        "bg-warning-subtle text-warning border-warning/30",
  Phone:        "bg-warning-subtle text-warning border-warning/30",
  Person:       "bg-destructive-subtle text-destructive border-destructive/30",
  Organization: "bg-destructive-subtle text-destructive border-destructive/30",
  "Credit Card":"bg-destructive-subtle text-destructive border-destructive/30",
  Location:     "bg-accent-subtle text-accent-foreground border-accent/30",
  URL:          "bg-warning-subtle text-warning border-warning/30",
  Currency:     "bg-surface-subtle text-text-secondary border-border",
  Date:         "bg-surface-subtle text-text-secondary border-border",
};

function ConfidenceBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 95 ? "text-success" : pct >= 85 ? "text-warning" : "text-destructive";
  return (
    <span className={cn("text-[10px] font-medium tabular-nums", color)}>
      {pct}%
    </span>
  );
}

function RedactionRow({
  span,
  selected,
  onSelect,
  onConfirm,
  onOverride,
  onUndo,
}: {
  span: RedactionSpan;
  selected: boolean;
  onSelect: (id: number) => void;
  onConfirm?: (id: number) => void;
  onOverride?: (id: number) => void;
  onUndo?: (id: number) => void;
}) {
  const typeStyle = TYPE_COLOR[span.type] ?? "bg-surface-subtle text-text-secondary border-border";
  const isConfirmed = span.decision === "confirmed";
  const isOverridden = span.decision === "override";

  return (
    <div
      className={cn(
        "flex items-center gap-3 px-3.5 py-2.5 border-b border-border last:border-0 transition-colors",
        isConfirmed && "bg-success-subtle/30",
        isOverridden && "bg-surface-subtle opacity-60",
        selected && !isConfirmed && !isOverridden && "bg-accent-subtle/20"
      )}
    >
      {/* Checkbox */}
      <input
        type="checkbox"
        checked={selected}
        onChange={() => onSelect(span.id)}
        className="w-3.5 h-3.5 accent-primary cursor-pointer shrink-0"
        aria-label={`Select ${span.original}`}
      />

      {/* PII value */}
      <div className="flex-1 min-w-0 flex items-center gap-2">
        <span
          className={cn(
            "inline-flex items-center px-2 py-0.5 rounded border text-xs font-mono font-medium",
            typeStyle
          )}
        >
          {span.original}
        </span>
        <span className="text-[11px] text-text-muted">→</span>
        <span className="text-[11px] font-mono text-text-secondary">{span.placeholder}</span>
      </div>

      {/* Meta */}
      <div className="hidden sm:flex items-center gap-2 shrink-0">
        <span className="text-[10px] text-text-muted bg-surface-subtle border border-border px-1.5 py-0.5 rounded">
          {span.type}
        </span>
        <span className="text-[10px] text-text-muted">{span.method}</span>
        <ConfidenceBadge score={span.confidence} />
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1.5 shrink-0">
        {isConfirmed ? (
          <span className="text-xs text-success font-medium flex items-center gap-1">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2.5}>
              <polyline points="2,7 5.5,10.5 12,3.5" />
            </svg>
            Redacted
            <button
              onClick={() => onUndo?.(span.id)}
              className="text-[10px] text-text-muted hover:text-foreground underline underline-offset-2 ml-1"
            >
              Undo
            </button>
          </span>
        ) : isOverridden ? (
          <span className="text-xs text-text-muted font-medium flex items-center gap-1">
            Kept
            <button
              onClick={() => onUndo?.(span.id)}
              className="text-[10px] text-text-muted hover:text-foreground underline underline-offset-2 ml-1"
            >
              Undo
            </button>
          </span>
        ) : (
          <>
            <button
              onClick={() => onConfirm?.(span.id)}
              className="px-2.5 py-1 rounded text-xs font-medium bg-success-subtle text-success border border-success/30 hover:bg-success hover:text-white transition-colors"
            >
              Redact
            </button>
            <button
              onClick={() => onOverride?.(span.id)}
              className="px-2.5 py-1 rounded text-xs font-medium bg-surface-subtle text-text-secondary border border-border hover:bg-secondary transition-colors"
            >
              Keep
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export function RedactionHighlight({
  detections,
  onConfirm,
  onOverride,
  onConfirmAll,
  onUndo,
  onConfirmSelected,
  onOverrideSelected,
  className,
}: RedactionHighlightProps) {
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const confirmed = detections.filter((d) => d.decision === "confirmed").length;
  const pending   = detections.filter((d) => !d.decision).length;
  const pendingIds = detections.filter((d) => !d.decision).map((d) => d.id);
  const allPendingSelected = pendingIds.length > 0 && pendingIds.every((id) => selected.has(id));

  function toggleSelect(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (allPendingSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(pendingIds));
    }
  }

  function handleConfirmSelected() {
    const ids = Array.from(selected);
    onConfirmSelected?.(ids);
    setSelected(new Set());
  }

  function handleOverrideSelected() {
    const ids = Array.from(selected);
    onOverrideSelected?.(ids);
    setSelected(new Set());
  }

  return (
    <div className={cn("flex flex-col", className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-border bg-surface-subtle gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          {/* Select-all checkbox */}
          {pendingIds.length > 0 && (
            <input
              type="checkbox"
              checked={allPendingSelected}
              onChange={toggleSelectAll}
              className="w-3.5 h-3.5 accent-primary cursor-pointer shrink-0"
              aria-label="Select all pending"
            />
          )}
          <span className="text-xs font-semibold text-foreground">
            {detections.length} detection{detections.length !== 1 ? "s" : ""}
          </span>
          <span className="text-xs text-text-muted">
            {confirmed} redacted · {pending} pending
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Batch actions when items selected */}
          {selected.size > 0 && (
            <>
              <button
                onClick={handleConfirmSelected}
                className="text-xs font-medium px-2 py-1 rounded bg-success-subtle text-success border border-success/30 hover:bg-success hover:text-white transition-colors"
              >
                Redact Selected ({selected.size})
              </button>
              <button
                onClick={handleOverrideSelected}
                className="text-xs font-medium px-2 py-1 rounded bg-surface-subtle text-text-secondary border border-border hover:bg-secondary transition-colors"
              >
                Keep Selected ({selected.size})
              </button>
            </>
          )}

          {/* Redact all — only when no selection active */}
          {selected.size === 0 && onConfirmAll && pending > 0 && (
            <button
              onClick={onConfirmAll}
              className="text-xs font-medium text-primary hover:text-accent-hover transition-colors"
            >
              Redact all
            </button>
          )}
        </div>
      </div>

      {/* Rows */}
      <div className="divide-y-0">
        {detections.map((span) => (
          <RedactionRow
            key={span.id}
            span={span}
            selected={selected.has(span.id)}
            onSelect={toggleSelect}
            onConfirm={onConfirm}
            onOverride={onOverride}
            onUndo={onUndo}
          />
        ))}
      </div>

      {detections.length === 0 && (
        <div className="flex flex-col items-center py-8 gap-2 text-center">
          <svg className="w-8 h-8 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
          <p className="text-sm text-text-muted">No PII detected in this document.</p>
        </div>
      )}
    </div>
  );
}
