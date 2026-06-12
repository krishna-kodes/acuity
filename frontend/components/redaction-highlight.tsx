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
  Email:         "bg-warning-subtle text-warning border-warning/30",
  Phone:         "bg-warning-subtle text-warning border-warning/30",
  Person:        "bg-destructive-subtle text-destructive border-destructive/30",
  Organization:  "bg-destructive-subtle text-destructive border-destructive/30",
  "Credit Card": "bg-destructive-subtle text-destructive border-destructive/30",
  Location:      "bg-accent-subtle text-accent-foreground border-accent/30",
  URL:           "bg-warning-subtle text-warning border-warning/30",
  Currency:      "bg-surface-subtle text-text-secondary border-border",
  Date:          "bg-surface-subtle text-text-secondary border-border",
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
      <input
        type="checkbox"
        checked={selected}
        onChange={() => onSelect(span.id)}
        className="w-3.5 h-3.5 accent-primary cursor-pointer shrink-0"
        aria-label={`Select ${span.original}`}
      />

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

      <div className="hidden sm:flex items-center gap-2 shrink-0">
        <span className="text-[10px] text-text-muted">{span.method}</span>
        <ConfidenceBadge score={span.confidence} />
      </div>

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

function GroupSection({
  type,
  spans,
  selected,
  onSelectGroup,
  onSelect,
  onConfirm,
  onOverride,
  onUndo,
  onConfirmGroup,
}: {
  type: string;
  spans: RedactionSpan[];
  selected: Set<number>;
  onSelectGroup: (ids: number[], selectAll: boolean) => void;
  onSelect: (id: number) => void;
  onConfirm?: (id: number) => void;
  onOverride?: (id: number) => void;
  onUndo?: (id: number) => void;
  onConfirmGroup: (ids: number[]) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const pendingIds = spans.filter((s) => !s.decision).map((s) => s.id);
  const redactedCount = spans.filter((s) => s.decision === "confirmed").length;
  const keptCount = spans.filter((s) => s.decision === "override").length;
  const pendingCount = pendingIds.length;
  const allPendingSelected =
    pendingIds.length > 0 && pendingIds.every((id) => selected.has(id));

  return (
    <div>
      {/* Group header */}
      <div
        className="flex items-center justify-between px-3.5 py-2 bg-surface-subtle/70 border-b border-border sticky top-0 z-10 cursor-pointer"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex items-center gap-2.5">
          {pendingIds.length > 0 ? (
            <input
              type="checkbox"
              checked={allPendingSelected}
              onChange={() => onSelectGroup(pendingIds, !allPendingSelected)}
              onClick={(e) => e.stopPropagation()}
              className="w-3.5 h-3.5 accent-primary cursor-pointer shrink-0"
              aria-label={`Select all pending ${type}`}
            />
          ) : (
            <span className="w-3.5 h-3.5 shrink-0" />
          )}
          <span className="text-[11px] font-semibold text-foreground">{type}</span>
          <span className="text-[10px] text-text-muted">
            {spans.length} item{spans.length !== 1 ? "s" : ""}
          </span>
          {redactedCount > 0 && (
            <span className="text-[10px] text-success font-medium">{redactedCount} redacted</span>
          )}
          {keptCount > 0 && (
            <span className="text-[10px] text-text-muted">{keptCount} kept</span>
          )}
          {pendingCount > 0 && (
            <span className="text-[10px] text-warning font-medium">{pendingCount} pending</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v); }}
            className="p-0.5"
            aria-label={expanded ? "Collapse group" : "Expand group"}
          >
            <svg className={cn("w-3 h-3 text-text-muted transition-transform", !expanded && "-rotate-90")} fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2}>
              <path d="M2 4l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          {pendingCount > 0 && (
            <button
              onClick={(e) => { e.stopPropagation(); onConfirmGroup(pendingIds); }}
              className="text-[10px] font-medium text-primary hover:text-accent-hover transition-colors"
            >
              Redact all
            </button>
          )}
        </div>
      </div>

      {expanded && spans.map((span) => (
        <RedactionRow
          key={span.id}
          span={span}
          selected={selected.has(span.id)}
          onSelect={onSelect}
          onConfirm={onConfirm}
          onOverride={onOverride}
          onUndo={onUndo}
        />
      ))}
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
  const [statusFilter, setStatusFilter] = useState<"all" | "pending" | "redacted" | "kept">("pending");
  const [typeFilter, setTypeFilter] = useState<Set<string>>(new Set());

  // Entity types present, sorted for a stable filter bar.
  const allTypes = Array.from(new Set(detections.map((d) => d.type))).sort();

  function matchesStatus(d: RedactionSpan): boolean {
    if (statusFilter === "pending") return !d.decision;
    if (statusFilter === "redacted") return d.decision === "confirmed";
    if (statusFilter === "kept") return d.decision === "override";
    return true;
  }
  // Empty typeFilter = no type filtering (show all types).
  function matchesType(d: RedactionSpan): boolean {
    return typeFilter.size === 0 || typeFilter.has(d.type);
  }

  const visible = detections.filter((d) => matchesStatus(d) && matchesType(d));
  const filterActive = statusFilter !== "all" || typeFilter.size > 0;

  function toggleType(type: string) {
    setSelected(new Set());
    setTypeFilter((prev) => {
      const next = new Set(prev);
      next.has(type) ? next.delete(type) : next.add(type);
      return next;
    });
  }

  function clearFilters() {
    setStatusFilter("all");
    setTypeFilter(new Set());
  }

  // Counts: true totals across all detections (not the filtered view).
  const confirmed = detections.filter((d) => d.decision === "confirmed").length;
  const pending   = detections.filter((d) => !d.decision).length;
  // Selection/bulk operate on the visible pending set.
  const pendingIds = visible.filter((d) => !d.decision).map((d) => d.id);
  const allPendingSelected = pendingIds.length > 0 && pendingIds.every((id) => selected.has(id));

  // Group the VISIBLE detections by type; sort within by confidence desc, groups by max confidence desc
  const groupMap = visible.reduce<Record<string, RedactionSpan[]>>((acc, d) => {
    (acc[d.type] ??= []).push(d);
    return acc;
  }, {});

  const groups = Object.entries(groupMap)
    .map(([type, spans]) => ({
      type,
      spans: [...spans].sort((a, b) => b.confidence - a.confidence),
      maxConfidence: Math.max(...spans.map((s) => s.confidence)),
    }))
    .sort((a, b) => b.maxConfidence - a.maxConfidence);

  function toggleSelect(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    setSelected(allPendingSelected ? new Set() : new Set(pendingIds));
  }

  function selectGroup(ids: number[], selectAll: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (selectAll) {
        ids.forEach((id) => next.add(id));
      } else {
        ids.forEach((id) => next.delete(id));
      }
      return next;
    });
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

  function handleConfirmGroup(ids: number[]) {
    onConfirmSelected?.(ids);
    setSelected((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => next.delete(id));
      return next;
    });
  }

  return (
    <div className={cn("flex flex-col", className)}>
      {/* Global header */}
      <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-border bg-surface-subtle gap-3 flex-wrap">
        <div className="flex items-center gap-3">
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
          {filterActive && (
            <span className="text-[11px] text-primary font-medium">
              showing {visible.length}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {selected.size > 0 && (
            <>
              <button
                onClick={handleConfirmSelected}
                className="text-xs font-medium px-2 py-1 rounded bg-success-subtle text-success border border-success/30 hover:bg-success hover:text-white transition-colors"
              >
                Redact selected ({selected.size})
              </button>
              <button
                onClick={handleOverrideSelected}
                className="text-xs font-medium px-2 py-1 rounded bg-surface-subtle text-text-secondary border border-border hover:bg-secondary transition-colors"
              >
                Keep selected ({selected.size})
              </button>
            </>
          )}
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

      {/* Filter bar */}
      {detections.length > 0 && (
        <div className="flex items-center gap-3 px-3.5 py-2 border-b border-border bg-background flex-wrap">
          {/* Status segmented control */}
          <div className="inline-flex rounded-md border border-border overflow-hidden">
            {(["all", "pending", "redacted", "kept"] as const).map((s) => (
              <button
                key={s}
                onClick={() => { setSelected(new Set()); setStatusFilter(s); }}
                className={cn(
                  "px-2.5 py-1 text-[11px] font-medium capitalize transition-colors border-r border-border last:border-r-0",
                  statusFilter === s
                    ? "bg-primary text-primary-foreground"
                    : "bg-surface-subtle text-text-secondary hover:bg-card",
                )}
              >
                {s === "pending" ? "Action items" : s}
              </button>
            ))}
          </div>

          {/* Type chips */}
          {allTypes.length > 1 && (
            <div className="flex items-center gap-1.5 flex-wrap">
              {allTypes.map((t) => {
                const on = typeFilter.has(t);
                return (
                  <button
                    key={t}
                    onClick={() => toggleType(t)}
                    className={cn(
                      "px-2 py-0.5 rounded-full text-[11px] font-medium border transition-colors",
                      on
                        ? "bg-accent-subtle text-accent-foreground border-accent/40"
                        : "bg-surface-subtle text-text-muted border-border hover:text-foreground",
                    )}
                  >
                    {t}
                  </button>
                );
              })}
            </div>
          )}

          {filterActive && (
            <button
              onClick={clearFilters}
              className="text-[11px] text-text-muted hover:text-foreground underline underline-offset-2 ml-auto"
            >
              Clear filters
            </button>
          )}
        </div>
      )}

      {/* Grouped rows */}
      {groups.map(({ type, spans }) => (
        <GroupSection
          key={type}
          type={type}
          spans={spans}
          selected={selected}
          onSelectGroup={selectGroup}
          onSelect={toggleSelect}
          onConfirm={onConfirm}
          onOverride={onOverride}
          onUndo={onUndo}
          onConfirmGroup={handleConfirmGroup}
        />
      ))}

      {/* Filtered-empty state (detections exist but none match the filter) */}
      {detections.length > 0 && visible.length === 0 && (
        <div className="flex flex-col items-center py-8 gap-2 text-center">
          <p className="text-sm text-text-muted">No items match this filter.</p>
          <button
            onClick={clearFilters}
            className="text-xs font-medium text-primary hover:text-accent-hover transition-colors"
          >
            Clear filters
          </button>
        </div>
      )}

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
