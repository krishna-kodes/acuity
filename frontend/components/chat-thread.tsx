"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

export type MessageRole = "ai" | "pm";

export interface ChatSource {
  section_hint: string;
  page_number?: number | null;
}

export interface GroundednessWarning {
  score: number;
  unsupported_claims: string[];
  reasoning: string;
  source: string | null;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  text: string;
  timestamp?: string;
  confidenceScore?: number | null;
  groundednessWarning?: GroundednessWarning | null;
  isError?: boolean;
  sources?: ChatSource[];
}

interface ChatThreadProps {
  messages: ChatMessage[];
  isLoading?: boolean;
  className?: string;
  onRetry?: () => void;
  suggestedReplies?: string[];
  onSuggestionClick?: (text: string) => void;
}

function AIAvatar() {
  return (
    <div className="w-7 h-7 rounded-full bg-accent-subtle border border-border flex items-center justify-center shrink-0">
      <svg className="w-3.5 h-3.5 text-primary" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}>
        <path d="M2 10L7 3l5 7" />
      </svg>
    </div>
  );
}

function PMAvatar() {
  return (
    <div className="w-7 h-7 rounded-full bg-surface-subtle border border-border flex items-center justify-center shrink-0">
      <svg className="w-3.5 h-3.5 text-text-secondary" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={1.75}>
        <circle cx="7" cy="5" r="2.5" />
        <path d="M2 13c0-2.8 2.2-5 5-5s5 2.2 5 5" />
      </svg>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-start gap-2.5">
      <AIAvatar />
      <div className="bg-card border border-border rounded-xl rounded-tl-sm px-3.5 py-2.5">
        <div className="flex items-center gap-1">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-text-muted animate-bounce"
              style={{ animationDelay: `${i * 150}ms` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function ConfidenceBadge({ score }: { score: number }) {
  const [color, label] =
    score >= 0.8 ? ["bg-success-subtle text-success", `${Math.round(score * 100)}% confident`]
    : score >= 0.6 ? ["bg-warning-subtle text-warning", `${Math.round(score * 100)}% confident`]
    : ["bg-destructive-subtle text-destructive", `${Math.round(score * 100)}% confident`];
  return (
    <span className={cn("inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium", color)}>
      {label}
    </span>
  );
}

function GroundednessWarningBanner({ warning }: { warning: GroundednessWarning }) {
  return (
    <div className="mt-1 px-3 py-2 bg-warning-subtle border border-warning/30 rounded-lg text-[11px] text-warning space-y-1">
      <div className="font-medium">
        Response may contain unverified claims ({Math.round(warning.score * 100)}% grounded)
      </div>
      {warning.unsupported_claims.length > 0 && (
        <ul className="list-disc list-inside space-y-0.5 text-warning/80">
          {warning.unsupported_claims.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SourcesCollapsible({ sources }: { sources: ChatSource[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-1">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-[11px] text-text-muted hover:text-foreground transition-colors"
      >
        <svg
          className={cn("w-3 h-3 transition-transform", open && "rotate-90")}
          fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2}
        >
          <path d="M4 2l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {sources.length} source{sources.length !== 1 ? "s" : ""}
      </button>
      {open && (
        <div className="mt-1.5 space-y-1 pl-3 border-l-2 border-border">
          {sources.map((s, i) => (
            <div key={i} className="text-[11px] text-text-muted leading-snug">
              <span className="text-foreground">{s.section_hint || "Untitled section"}</span>
              {s.page_number != null && (
                <span className="ml-1.5 opacity-60">p.{s.page_number}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MessageBubble({
  message,
  showRetry,
  onRetry,
}: {
  message: ChatMessage;
  showRetry?: boolean;
  onRetry?: () => void;
}) {
  const isAI = message.role === "ai";

  return (
    <div
      className={cn(
        "flex items-start gap-2.5",
        !isAI && "flex-row-reverse"
      )}
    >
      {isAI ? <AIAvatar /> : <PMAvatar />}

      <div
        className={cn(
          "max-w-[75%] flex flex-col gap-1",
          !isAI && "items-end"
        )}
      >
        <div
          className={cn(
            "px-3.5 py-2.5 text-sm leading-relaxed",
            isAI
              ? cn(
                  "bg-card border text-foreground rounded-xl rounded-tl-sm",
                  message.isError ? "border-destructive/40" : "border-border",
                )
              : "bg-primary text-primary-foreground rounded-xl rounded-tr-sm"
          )}
        >
          {isAI ? (
            message.text ? (
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                  h1: ({ children }) => <h1 className="text-base font-semibold mb-1 mt-2 first:mt-0">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-sm font-semibold mb-1 mt-2 first:mt-0">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-sm font-semibold mb-1 mt-2 first:mt-0">{children}</h3>,
                  ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>,
                  li: ({ children }) => <li className="text-sm">{children}</li>,
                  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                  code: ({ children }) => <code className="bg-surface-subtle px-1 py-0.5 rounded text-xs font-mono">{children}</code>,
                  hr: () => <hr className="border-border my-2" />,
                }}
              >
                {message.text}
              </ReactMarkdown>
            ) : (
              <span className="text-text-muted text-xs italic">No response received.</span>
            )
          ) : (
            message.text
          )}
        </div>
        {isAI && message.groundednessWarning && (
          <GroundednessWarningBanner warning={message.groundednessWarning} />
        )}
        {isAI && message.sources && message.sources.length > 0 && (
          <SourcesCollapsible sources={message.sources} />
        )}
        <div className="flex items-center gap-1.5 px-1">
          {message.timestamp && (
            <span className="text-[11px] text-text-muted">
              {message.timestamp}
            </span>
          )}
          {isAI && message.confidenceScore != null && (
            <ConfidenceBadge score={message.confidenceScore} />
          )}
          {showRetry && onRetry && (
            <button
              onClick={onRetry}
              className="flex items-center gap-1 text-[11px] text-text-muted hover:text-primary transition-colors"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2}>
                <path d="M10 6A4 4 0 1 1 6 2" strokeLinecap="round" />
                <path d="M6 2l2 2-2 2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Retry
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function ChatThread({
  messages,
  isLoading,
  className,
  onRetry,
  suggestedReplies,
  onSuggestionClick,
}: ChatThreadProps) {
  return (
    <div className={cn("flex flex-col gap-4 py-4 px-4 overflow-y-auto", className)}>
      {messages.length === 0 && !isLoading && (
        <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
          <div className="w-10 h-10 rounded-full bg-accent-subtle flex items-center justify-center">
            <svg className="w-5 h-5 text-primary" fill="none" viewBox="0 0 20 20" stroke="currentColor" strokeWidth={1.75}>
              <path d="M3 5h14v9H11l-3 4v-4H3V5z" />
            </svg>
          </div>
          <p className="text-sm text-text-muted">No messages yet. Start by asking a question.</p>
        </div>
      )}

      {messages.map((message, i) => {
        const isLast = i === messages.length - 1;
        const showRetry = isLast && message.role === "ai" && (!!message.isError || !message.text) && !isLoading;
        return (
          <MessageBubble
            key={message.id}
            message={message}
            showRetry={showRetry}
            onRetry={onRetry}
          />
        );
      })}

      {!isLoading && suggestedReplies && suggestedReplies.length > 0 && (
        <div className="flex flex-wrap gap-2 pl-9">
          {suggestedReplies.map((reply) => (
            <button
              key={reply}
              onClick={() => onSuggestionClick?.(reply)}
              className="text-xs px-3 py-1.5 rounded-full border border-primary/30 text-primary bg-primary/5 hover:bg-primary/10 transition-colors"
            >
              {reply}
            </button>
          ))}
        </div>
      )}

      {isLoading && <TypingIndicator />}
    </div>
  );
}
