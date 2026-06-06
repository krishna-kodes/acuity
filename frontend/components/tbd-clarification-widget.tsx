"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

export type TBDAction = "answered" | "tbd" | "oos";

export interface TBDItem {
  id: string;
  title: string;
  desc: string;
  level: string;
  status: TBDAction | "open";
}

interface TBDClarificationWidgetProps {
  items: TBDItem[];
  onAction?: (id: string, action: TBDAction) => void;
  className?: string;
}

const ACTION_BUTTONS: { action: TBDAction; label: string }[] = [
  { action: "answered", label: "Answer" },
  { action: "tbd", label: "Keep TBD" },
  { action: "oos", label: "Out of Scope" },
];

const STATUS_STYLES: Record<TBDItem["status"], { label: string; bg: string; text: string }> = {
  open:     { label: "Open",         bg: "bg-warning-subtle",      text: "text-warning" },
  answered: { label: "Answered",     bg: "bg-success-subtle",      text: "text-success" },
  tbd:      { label: "TBD",          bg: "bg-surface-subtle",      text: "text-text-muted" },
  oos:      { label: "Out of Scope", bg: "bg-destructive-subtle",  text: "text-destructive" },
};

const LEVEL_STYLES: Record<string, string> = {
  "Explicit TBD":    "text-warning bg-warning-subtle",
  "Vague statement": "text-text-secondary bg-surface-subtle",
  "Missing section": "text-destructive bg-destructive-subtle",
  "Contradiction":   "text-destructive bg-destructive-subtle",
};

function TBDItemRow({
  item,
  onAction,
}: {
  item: TBDItem;
  onAction?: (id: string, action: TBDAction) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const statusStyle = STATUS_STYLES[item.status];
  const levelStyle = LEVEL_STYLES[item.level] ?? "text-text-muted bg-surface-subtle";
  const isResolved = item.status !== "open";

  return (
    <div
      className={cn(
        "border border-border rounded-md overflow-hidden transition-colors",
        isResolved && "opacity-70"
      )}
    >
      {/* Header row */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-start gap-3 px-3.5 py-3 text-left hover:bg-surface-subtle transition-colors"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-foreground">{item.title}</span>
            <span className={cn("text-[10px] font-medium px-1.5 py-0.5 rounded-full", levelStyle)}>
              {item.level}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={cn("text-[11px] font-medium px-2 py-0.5 rounded-full", statusStyle.bg, statusStyle.text)}>
            {statusStyle.label}
          </span>
          <svg
            className={cn("w-4 h-4 text-text-muted transition-transform", expanded && "rotate-180")}
            fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}
          >
            <path d="M4 6l4 4 4-4" />
          </svg>
        </div>
      </button>

      {/* Expanded: description + actions */}
      {expanded && (
        <div className="px-3.5 pb-3.5 border-t border-border bg-surface-subtle/50">
          <p className="text-xs text-text-secondary mt-2.5 mb-3 leading-relaxed">{item.desc}</p>
          {!isResolved && onAction && (
            <div className="flex items-center gap-2">
              {ACTION_BUTTONS.map(({ action, label }) => (
                <button
                  key={action}
                  onClick={() => onAction(item.id, action)}
                  className={cn(
                    "px-3 py-1.5 rounded-md text-xs font-medium border transition-colors",
                    action === "answered"
                      ? "bg-success-subtle border-success/30 text-success hover:bg-success hover:text-white"
                      : action === "oos"
                      ? "bg-destructive-subtle border-destructive/30 text-destructive hover:bg-destructive hover:text-white"
                      : "bg-surface-subtle border-border text-text-secondary hover:bg-secondary"
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function TBDClarificationWidget({
  items,
  onAction,
  className,
}: TBDClarificationWidgetProps) {
  const resolved = items.filter((i) => i.status !== "open").length;
  const outstanding = items.filter((i) => i.status === "open").length;

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {/* Summary counts */}
      <div className="flex items-center gap-4 px-1">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-warning" />
          <span className="text-xs font-medium text-text-secondary">
            {outstanding} outstanding
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-success" />
          <span className="text-xs font-medium text-text-secondary">
            {resolved} resolved
          </span>
        </div>
      </div>

      {/* Items */}
      <div className="flex flex-col gap-2">
        {items.map((item) => (
          <TBDItemRow key={item.id} item={item} onAction={onAction} />
        ))}
      </div>

      {items.length === 0 && (
        <div className="flex flex-col items-center py-8 gap-2 text-center">
          <svg className="w-8 h-8 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
          </svg>
          <p className="text-sm text-text-muted">No TBD items — document is fully specified.</p>
        </div>
      )}
    </div>
  );
}
