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
  source_sentence?: string | null;
  source_section?: string | null;
  source_page?: number | null;
}

interface TBDClarificationWidgetProps {
  items: TBDItem[];
  onAction?: (id: string, action: TBDAction, answer?: string) => void;
  onBulkAction?: (action: TBDAction) => void;
  className?: string;
  newItemIds?: Set<string>;
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
  isNew,
}: {
  item: TBDItem;
  onAction?: (id: string, action: TBDAction, answer?: string) => void;
  isNew?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [answerText, setAnswerText] = useState("");
  const [showAnswerInput, setShowAnswerInput] = useState(false);
  const statusStyle = STATUS_STYLES[item.status];
  const levelStyle = LEVEL_STYLES[item.level] ?? "text-text-muted bg-surface-subtle";

  function handleActionClick(action: TBDAction) {
    if (action === "answered") {
      setShowAnswerInput(true);
    } else {
      onAction?.(item.id, action);
    }
  }

  function handleSubmitAnswer() {
    if (!answerText.trim()) return;
    onAction?.(item.id, "answered", answerText.trim());
    setShowAnswerInput(false);
    setAnswerText("");
  }

  return (
    <div
      className={cn(
        "border rounded-md overflow-hidden transition-all",
        isNew
          ? "border-primary/50 ring-1 ring-primary/30 bg-primary/[0.02]"
          : "border-border",
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
            {isNew && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-primary/10 text-primary">
                New
              </span>
            )}
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

      {/* Expanded: source sentence, reference, description + actions */}
      {expanded && (
        <div className="px-3.5 pb-3.5 border-t border-border bg-surface-subtle/50">
          {/* Source sentence from document */}
          {item.source_sentence && (
            <blockquote className="mt-2.5 mb-2 pl-3 border-l-2 border-primary/40 text-xs text-foreground italic leading-relaxed">
              &ldquo;{item.source_sentence}&rdquo;
            </blockquote>
          )}
          {/* Section / page reference */}
          {(item.source_section || item.source_page != null) && (
            <div className="flex items-center gap-1.5 mb-2.5">
              {item.source_section && (
                <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-surface-subtle border border-border text-text-muted">
                  <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2}>
                    <path d="M2 3h8M2 6h5M2 9h3" strokeLinecap="round" />
                  </svg>
                  {item.source_section}
                </span>
              )}
              {item.source_page != null && (
                <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-surface-subtle border border-border text-text-muted">
                  p.{item.source_page}
                </span>
              )}
            </div>
          )}
          {/* Why it was flagged */}
          <p className="text-xs text-text-secondary mb-3 leading-relaxed">{item.desc}</p>

          {showAnswerInput ? (
            <div className="space-y-2">
              <textarea
                value={answerText}
                onChange={(e) => setAnswerText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmitAnswer(); }
                  if (e.key === "Escape") { setShowAnswerInput(false); setAnswerText(""); }
                }}
                placeholder="Type your answer…"
                rows={2}
                autoFocus
                className="w-full resize-none bg-card border border-border rounded-md px-3 py-2 text-xs text-foreground placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-primary/40"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleSubmitAnswer}
                  disabled={!answerText.trim()}
                  className={cn(
                    "flex-1 py-1.5 rounded-md text-xs font-medium border transition-colors",
                    answerText.trim()
                      ? "bg-success border-success text-white hover:bg-success/90"
                      : "bg-muted border-border text-text-muted cursor-not-allowed",
                  )}
                >
                  Submit Answer
                </button>
                <button
                  onClick={() => { setShowAnswerInput(false); setAnswerText(""); }}
                  className="px-3 py-1.5 rounded-md text-xs text-text-muted hover:text-foreground border border-border transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            onAction && (
              <div className="flex items-center gap-2">
                {ACTION_BUTTONS.map(({ action, label }) => (
                  <button
                    key={action}
                    onClick={() => handleActionClick(action)}
                    className={cn(
                      "px-3 py-1.5 rounded-md text-xs font-medium border transition-colors",
                      item.status === action
                        ? action === "answered"
                          ? "bg-success border-success text-white"
                          : action === "oos"
                          ? "bg-destructive border-destructive text-white"
                          : "bg-secondary border-border text-foreground"
                        : action === "answered"
                        ? "bg-success-subtle border-success/30 text-success hover:bg-success hover:text-white"
                        : action === "oos"
                        ? "bg-destructive-subtle border-destructive/30 text-destructive hover:bg-destructive hover:text-white"
                        : "bg-surface-subtle border-border text-text-secondary hover:bg-secondary",
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}

export function TBDClarificationWidget({
  items,
  onAction,
  onBulkAction,
  className,
  newItemIds,
}: TBDClarificationWidgetProps) {
  const resolved = items.filter((i) => i.status !== "open").length;
  const outstanding = items.filter((i) => i.status === "open").length;

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {/* Summary counts + bulk actions */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-1">
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
        {outstanding > 0 && onBulkAction && (
          <div className="flex items-center gap-1.5 ml-auto">
            <span className="text-[11px] text-text-muted">All:</span>
            <button
              onClick={() => onBulkAction("answered")}
              className="px-2 py-1 rounded text-[11px] font-medium border border-success/30 bg-success-subtle text-success hover:bg-success hover:text-white transition-colors"
            >
              Answer
            </button>
            <button
              onClick={() => onBulkAction("tbd")}
              className="px-2 py-1 rounded text-[11px] font-medium border border-border bg-surface-subtle text-text-secondary hover:bg-secondary transition-colors"
            >
              Keep TBD
            </button>
            <button
              onClick={() => onBulkAction("oos")}
              className="px-2 py-1 rounded text-[11px] font-medium border border-destructive/30 bg-destructive-subtle text-destructive hover:bg-destructive hover:text-white transition-colors"
            >
              Out-of-Scope
            </button>
          </div>
        )}
      </div>

      {/* Items */}
      <div className="flex flex-col gap-2">
        {items.map((item) => (
          <TBDItemRow
            key={item.id}
            item={item}
            onAction={onAction}
            isNew={newItemIds?.has(item.id)}
          />
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
