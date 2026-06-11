"use client";

import { useState, useRef, useEffect, use } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { ChatThread } from "@/components/chat-thread";
import { TBDClarificationWidget } from "@/components/tbd-clarification-widget";
import { ErrorBanner } from "@/components/page-states";
import { getPhasesForRoute, getNextPhaseRoute } from "@/lib/project-phases";
import {
  getTBDs,
  submitClarification,
  generateProposalStream,
  retryProposalStream,
  approveProposal,
  regenerateSection,
  getProposalExportUrl,
  getChatHistory,
} from "@/lib/api";
import type { ProposalData, StructuredSection, SectionStatus, RiskItem, PersonaItem, FeatureItem } from "@/lib/api";
import type { ChatMessage, ChatSource } from "@/components/chat-thread";
import type { TBDItem, TBDAction } from "@/components/tbd-clarification-widget";
import { cn } from "@/lib/utils";

// ── Structured proposal accordion components ─────────────────────────────────

function StatusBadge({ status }: { status: SectionStatus }) {
  const cls =
    status === "generated"
      ? "bg-success-subtle text-success"
      : status === "draft"
        ? "bg-warning-subtle text-warning"
        : status === "generating"
          ? "bg-primary/10 text-primary"
          : "bg-destructive-subtle text-destructive"
  return (
    <span className={cn("text-[10px] font-medium px-2 py-0.5 rounded-full", cls)}>
      {status === "generating" ? "generating…" : status}
    </span>
  )
}

function RisksTable({ items }: { items: RiskItem[] }) {
  return (
    <div className="divide-y divide-border">
      <div className="grid grid-cols-2 gap-3 px-4 py-2 bg-surface-subtle/30 text-[10px] font-semibold uppercase tracking-wide text-text-muted">
        <span>Risk</span>
        <span>Mitigation</span>
      </div>
      {items.map((r, i) => (
        <div key={i} className="grid grid-cols-2 gap-3 px-4 py-2 text-xs">
          <span className="text-destructive">{r.risk}</span>
          <span className="text-success">{r.mitigation}</span>
        </div>
      ))}
    </div>
  )
}

function PersonaCards({ items }: { items: PersonaItem[] }) {
  return (
    <div className="flex flex-wrap gap-2 p-4">
      {items.map((p, i) => (
        <div key={i} className="p-3 rounded-lg border border-border bg-surface-subtle text-xs min-w-[140px]">
          <div className="font-semibold text-foreground">{p.name}</div>
          <div className="text-text-muted mt-0.5">{p.role}</div>
          <div className="text-foreground mt-1">{p.needs}</div>
        </div>
      ))}
    </div>
  )
}

function FeaturesTable({ items }: { items: FeatureItem[] }) {
  return (
    <div className="divide-y divide-border">
      {items.map((f, i) => (
        <div key={i} className="flex items-start gap-3 px-4 py-2 text-xs">
          <span className={cn("font-mono shrink-0 mt-0.5", f.in_scope ? "text-success" : "text-text-muted")}>
            {f.in_scope ? "IN" : "OUT"}
          </span>
          <div>
            <div className="font-medium text-foreground">{f.title}</div>
            <div className="text-text-muted mt-0.5">{f.description}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

function ProposalAccordion({
  sections,
  projectId,
  onSectionUpdate,
}: {
  sections: StructuredSection[]
  projectId: string
  onSectionUpdate: (updated: StructuredSection) => void
}) {
  const [open, setOpen] = useState<Record<string, boolean>>({})
  const [regenerating, setRegenerating] = useState<Record<string, boolean>>({})

  async function handleRegen(sectionId: string) {
    setRegenerating((p) => ({ ...p, [sectionId]: true }))
    const { data } = await regenerateSection(projectId, sectionId)
    if (data) onSectionUpdate(data)
    setRegenerating((p) => ({ ...p, [sectionId]: false }))
  }

  return (
    <div className="divide-y divide-border rounded-xl border border-border overflow-hidden">
      {sections.map((s) => (
        <div key={s.section_id}>
          <div
            className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-surface-subtle/50 select-none"
            onClick={() => setOpen((p) => ({ ...p, [s.section_id]: !p[s.section_id] }))}
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-xs font-medium text-foreground truncate">{s.title}</span>
              <StatusBadge status={s.status} />
            </div>
            <div className="flex items-center gap-2 shrink-0 ml-2" onClick={(e) => e.stopPropagation()}>
              {s.section_id !== "open_questions" && (
                <button
                  disabled={regenerating[s.section_id]}
                  onClick={() => handleRegen(s.section_id)}
                  className="text-[10px] text-text-muted hover:text-foreground px-1.5 py-0.5 rounded border border-border transition-colors disabled:opacity-50"
                >
                  {regenerating[s.section_id] ? "…" : "Regenerate"}
                </button>
              )}
              <svg
                className={cn("w-3 h-3 text-text-muted transition-transform", open[s.section_id] && "rotate-180")}
                fill="none"
                viewBox="0 0 12 12"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path d="M2 4l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </div>

          {open[s.section_id] && (
            <div className="border-t border-border">
              {s.status === "draft" && (
                <p className="px-4 py-2 text-[10px] text-warning italic border-b border-border bg-warning-subtle/20">
                  Generated from requirements — update after Phase 3/5 completes
                </p>
              )}
              {s.status === "failed" ? (
                <div className="px-4 py-3 text-xs text-destructive">
                  Section generation failed. Use Regenerate to retry.
                </div>
              ) : s.section_id === "risks_and_mitigations" && s.items?.length ? (
                <RisksTable items={s.items as RiskItem[]} />
              ) : s.section_id === "target_audience" && s.items?.length ? (
                <PersonaCards items={s.items as PersonaItem[]} />
              ) : s.section_id === "key_features" && s.items?.length ? (
                <FeaturesTable items={s.items as FeatureItem[]} />
              ) : (
                <p className="px-4 py-3 text-xs text-foreground whitespace-pre-wrap leading-relaxed">
                  {s.content}
                </p>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Chat page ─────────────────────────────────────────────────────────────────

const AUTO_PROMPT = "Summarise this project in 2–3 lines, then list any TBD or unclear items that need clarification.";

const TBD_LEVEL_LABELS: Record<number, TBDItem["level"]> = {
  1: "Explicit TBD",
  2: "Vague statement",
  3: "Missing section",
  4: "Contradiction",
};

const SUGGESTED_REPLIES = [
  "Which TBDs should I prioritize?",
  "Summarize the outstanding items",
  "What details are needed to resolve these?",
];


export default function ChatPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: projectId } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();
  const [messages, setMessages]     = useState<ChatMessage[]>([]);
  const [localStatuses, setLocalStatuses] = useState<Record<string, TBDAction>>({});
  const [input, setInput]           = useState("");
  const [isLoading, setIsLoading]   = useState(false);
  const [generating, setGenerating] = useState(false);
  const textareaRef  = useRef<HTMLTextAreaElement>(null);
  const bottomRef    = useRef<HTMLDivElement>(null);
  const sendingRef   = useRef(false);
  const autoSentRef  = useRef(false);
  const lastSentMessageRef = useRef<string>("");
  const messagesInitializedRef = useRef(false);
  const prevTbdIdsRef = useRef<Set<string>>(new Set());
  const tbdInitializedRef = useRef(false);
  const [newTbdIds, setNewTbdIds] = useState<Set<string>>(new Set());
  const [showSuggestions, setShowSuggestions] = useState(false);

  // Proposal preview state
  const [proposalData, setProposalData] = useState<ProposalData | null>(null);
  const [retryComment, setRetryComment] = useState("");
  const [showRetryInput, setShowRetryInput] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [approving, setApproving] = useState(false);
  const [proposalError, setProposalError] = useState<string | null>(null);

  const { data: remoteTbds, isPending: tbdsPending, isError: tbdsError, refetch: refetchTbds } = useQuery({
    queryKey: ["tbds", projectId],
    queryFn: async () => {
      const { data, error } = await getTBDs(projectId);
      if (error) throw new Error(String(error));
      return (data ?? []).map((t) => {
        const raw = t as { status?: string; source_sentence?: string | null; source_section?: string | null; source_page?: number | null };
        const title = t.question.length > 80 ? t.question.slice(0, 77) + "…" : t.question;
        return {
          id: t.id,
          title,
          desc: t.question,
          level: TBD_LEVEL_LABELS[t.level] ?? "Explicit TBD",
          status: (raw.status ?? "open") as TBDAction | "open",
          source_sentence: raw.source_sentence ?? null,
          source_section: raw.source_section ?? null,
          source_page: raw.source_page ?? null,
        };
      });
    },
    staleTime: 0,
    refetchOnWindowFocus: false,
  });

  const tbdItems: TBDItem[] = (remoteTbds ?? []).map((t) => ({
    ...t,
    status: localStatuses[t.id] ?? t.status,
  }));

  const outstandingTbds = tbdItems.filter((t) => t.status === "open").length;
  const allTbdsResolved = !tbdsPending && (tbdItems.length === 0 || outstandingTbds === 0);

  // Hydrate persisted chat history from backend
  const { data: chatHistory, isSuccess: chatHistoryLoaded } = useQuery({
    queryKey: ["chat-history", projectId],
    queryFn: () => getChatHistory(projectId),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (!chatHistory || chatHistory.length === 0) return;
    if (messagesInitializedRef.current) return;
    messagesInitializedRef.current = true;
    const ts = new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
    setMessages(chatHistory.map((m, i) => ({
      id: `history-${i}`,
      role: m.role === "user" ? ("pm" as const) : ("ai" as const),
      text: m.content,
      timestamp: ts,
      confidenceScore: m.groundedness_score ?? undefined,
    })));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatHistory]);

  // Auto-send opening summary prompt for new sessions
  useEffect(() => {
    if (!chatHistoryLoaded) return;
    if (chatHistory && chatHistory.length > 0) return;
    if (autoSentRef.current) return;
    autoSentRef.current = true;

    const aiId = "auto-welcome";
    const ts = new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
    setMessages([{ id: aiId, role: "ai", text: "", timestamp: ts }]);
    setIsLoading(true);

    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    fetch(`${apiBase}/api/v1/projects/${projectId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: AUTO_PROMPT, proceed: false }),
    }).then(async (response) => {
      if (!response.ok || !response.body) return;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let accumulated = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6)) as { type: string; content?: string };
            if (event.type === "token" && event.content) {
              accumulated += event.content;
              setMessages((prev) =>
                prev.map((m) => m.id === aiId ? { ...m, text: accumulated } : m)
              );
            } else if (event.type === "tbds") {
              queryClient.invalidateQueries({ queryKey: ["tbds", projectId] });
            } else if (event.type === "done") {
              queryClient.invalidateQueries({ queryKey: ["chat-history", projectId] });
              break;
            }
          } catch { /* skip malformed lines */ }
        }
      }
    }).catch(() => {
      setMessages((prev) =>
        prev.map((m) => m.id === aiId ? { ...m, text: "Couldn't load project summary. Ask me anything about the document." } : m)
      );
    }).finally(() => {
      setIsLoading(false);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatHistoryLoaded]);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, [input]);

  // Highlight newly detected TBD items from the last chat turn
  useEffect(() => {
    if (!remoteTbds) return;
    const incoming = new Set(remoteTbds.map(t => t.id));
    if (!tbdInitializedRef.current) {
      tbdInitializedRef.current = true;
      prevTbdIdsRef.current = incoming;
      return;
    }
    const newIds = new Set([...incoming].filter(id => !prevTbdIdsRef.current.has(id)));
    prevTbdIdsRef.current = incoming;
    if (newIds.size === 0) return;
    setNewTbdIds(newIds);
    const timer = setTimeout(() => setNewTbdIds(new Set()), 3000);
    return () => clearTimeout(timer);
  }, [remoteTbds]);

  async function doSend(text: string) {
    if (!text || isLoading || sendingRef.current) return;
    sendingRef.current = true;
    lastSentMessageRef.current = text;
    setShowSuggestions(false);

    const userMsg: ChatMessage = {
      id: String(Date.now()),
      role: "pm",
      text,
      timestamp: new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false }),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    const aiId = String(Date.now() + 1);
    const ts = new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
    setMessages((prev) => [...prev, { id: aiId, role: "ai" as const, text: "", timestamp: ts }]);

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const response = await fetch(
        `${apiBase}/api/v1/projects/${projectId}/chat`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, proceed: false }),
        }
      );

      if (!response.ok) {
        const errBody = await response.json().catch(() => null);
        throw new Error(errBody?.detail ?? `HTTP ${response.status}`);
      }
      if (!response.body) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6)) as {
              type: string;
              content?: string;
              items?: unknown[];
              message?: string;
              score?: number;
              unsupported_claims?: string[];
              reasoning?: string;
              source?: string | null;
              status?: string;
            };
            if (event.type === "token" && event.content) {
              accumulated += event.content;
              setMessages((prev) =>
                prev.map((m) => m.id === aiId ? { ...m, text: accumulated } : m)
              );
            } else if (event.type === "groundedness" && event.score != null) {
              setMessages((prev) =>
                prev.map((m) => m.id === aiId ? { ...m, confidenceScore: event.score } : m)
              );
            } else if (event.type === "groundedness_warning") {
              setMessages((prev) =>
                prev.map((m) => m.id === aiId
                  ? { ...m, groundednessWarning: { score: event.score ?? 0, unsupported_claims: event.unsupported_claims ?? [], reasoning: event.reasoning ?? "", source: event.source ?? null } }
                  : m
                )
              );
            } else if (event.type === "gate_blocked") {
              setMessages((prev) =>
                prev.map((m) => m.id === aiId
                  ? { ...m, text: event.message ?? "I couldn't find relevant information in your document." }
                  : m
                )
              );
            } else if (event.type === "sources") {
              setMessages((prev) =>
                prev.map((m) => m.id === aiId ? { ...m, sources: event.items as ChatSource[] } : m)
              );
            } else if (event.type === "tbds") {
              queryClient.invalidateQueries({ queryKey: ["tbds", projectId] });
              setShowSuggestions(true);
            } else if (event.type === "done") {
              queryClient.invalidateQueries({ queryKey: ["chat-history", projectId] });
              break;
            } else if (event.type === "error") {
              throw new Error(event.content ?? event.message ?? "Stream error");
            }
          } catch {
            // skip malformed SSE lines
          }
        }
      }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : null;
      const displayText = errMsg && !errMsg.startsWith("HTTP ")
        ? errMsg
        : "Sorry, I couldn't get a response. Please try again.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiId ? { ...m, text: displayText, isError: true } : m
        )
      );
    } finally {
      setIsLoading(false);
      sendingRef.current = false;
    }
  }

  function sendMessage() {
    const text = input.trim();
    if (!text) return;
    setInput("");
    doSend(text);
  }

  function handleChatRetry() {
    const lastMsg = lastSentMessageRef.current;
    if (!lastMsg || isLoading) return;
    setMessages(prev => {
      const last = prev[prev.length - 1];
      if (last?.role === "ai" && (last.isError || !last.text)) {
        return prev.slice(0, -2);
      }
      return prev;
    });
    doSend(lastMsg);
  }

  function handleSuggestionClick(text: string) {
    doSend(text);
  }

  const TBD_ACTION_TO_API: Record<TBDAction, string> = {
    answered: "Answer",
    tbd: "TBD",
    oos: "Out-of-Scope",
  };

  function handleTBDAction(id: string, action: TBDAction, answer?: string) {
    setLocalStatuses((prev) => ({ ...prev, [id]: action }));
    submitClarification(projectId, id, TBD_ACTION_TO_API[action], answer).catch(() => {
      // Fire-and-forget; local state already updated
    });
  }

  function handleBulkTBDAction(action: TBDAction) {
    const openItems = tbdItems.filter((t) => t.status === "open");
    if (openItems.length === 0) return;
    setLocalStatuses((prev) => {
      const updates: Record<string, TBDAction> = {};
      openItems.forEach((t) => { updates[t.id] = action; });
      return { ...prev, ...updates };
    });
    Promise.allSettled(
      openItems.map((t) => submitClarification(projectId, t.id, TBD_ACTION_TO_API[action]))
    ).catch(() => {});
  }

  async function handleGenerateProposal() {
    setGenerating(true);
    setProposalError(null);
    // Show proposal panel immediately with empty sections so sections stream in
    setProposalData({ id: "", project_id: projectId, content_path: "", created_at: "", sections: [], structured_sections: [] });
    try {
      await generateProposalStream(
        projectId,
        (section) => {
          setProposalData((prev) => {
            if (!prev) return prev;
            const existing = prev.structured_sections ?? [];
            const idx = existing.findIndex((s) => s.section_id === section.section_id);
            const updated = idx >= 0
              ? existing.map((s, i) => (i === idx ? section : s))
              : [...existing, section];
            return { ...prev, structured_sections: updated };
          });
        },
        (proposal) => {
          setProposalData(proposal);
        },
      );
    } catch (err) {
      setProposalError(err instanceof Error ? err.message : "Generation failed");
      setProposalData(null);
    } finally {
      setGenerating(false);
    }
  }

  async function handleRetry() {
    if (!retryComment.trim()) return;
    setRetrying(true);
    setProposalError(null);
    // Clear sections so they stream in progressively
    setProposalData((prev) => prev ? { ...prev, structured_sections: [] } : prev);
    try {
      await retryProposalStream(
        projectId,
        retryComment,
        (section) => {
          setProposalData((prev) => {
            if (!prev) return prev;
            const existing = prev.structured_sections ?? [];
            const idx = existing.findIndex((s) => s.section_id === section.section_id);
            const updated = idx >= 0
              ? existing.map((s, i) => (i === idx ? section : s))
              : [...existing, section];
            return { ...prev, structured_sections: updated };
          });
        },
        (proposal) => {
          setProposalData(proposal);
          setRetryComment("");
          setShowRetryInput(false);
        },
      );
    } catch (err) {
      setProposalError(err instanceof Error ? err.message : "Retry failed");
    } finally {
      setRetrying(false);
    }
  }

  async function handleApprove() {
    setApproving(true);
    setProposalError(null);
    try {
      await approveProposal(projectId);
      router.push(getNextPhaseRoute("chat", projectId));
    } catch (err) {
      setProposalError(err instanceof Error ? err.message : "Approval failed");
      setApproving(false);
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Phase stepper + header — fixed top area */}
      <div className="px-6 pt-6 pb-4 border-b border-border shrink-0">
        <PhaseProgressStepper phases={getPhasesForRoute("chat")} className="mb-4" />
      </div>

      {/* Main content — fills remaining height */}
      <div className="flex flex-col lg:flex-row flex-1 min-h-0 overflow-hidden">

        {/* Left: chat */}
        <div className="flex flex-col flex-1 min-w-0 border-b lg:border-b-0 lg:border-r border-border min-h-[50vh] lg:min-h-0">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-4">
            <ChatThread
              messages={messages}
              isLoading={isLoading}
              onRetry={handleChatRetry}
              suggestedReplies={showSuggestions ? SUGGESTED_REPLIES : undefined}
              onSuggestionClick={handleSuggestionClick}
            />
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="shrink-0 px-4 py-3 border-t border-border bg-background">
            <div className="flex items-end gap-2 bg-card border border-border rounded-xl px-3 py-2">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                  }
                }}
                placeholder="Ask about the requirements or clarify a TBD…"
                rows={1}
                className="flex-1 resize-none bg-transparent text-sm text-foreground placeholder:text-text-muted focus:outline-none leading-5 py-0.5"
              />
              <button
                onClick={sendMessage}
                disabled={!input.trim() || isLoading}
                className={cn(
                  "shrink-0 w-7 h-7 rounded-lg flex items-center justify-center transition-colors",
                  input.trim() && !isLoading
                    ? "bg-primary text-primary-foreground hover:bg-accent-hover"
                    : "bg-muted text-text-muted cursor-not-allowed"
                )}
                aria-label="Send"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2.5}>
                  <path d="M2 7h10M8 3l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
            <p className="text-[10px] text-text-muted mt-1.5 px-1">
              Enter to send · Shift+Enter for new line
            </p>
          </div>
        </div>

        {/* Right: TBD widget / proposal preview */}
        <div className="w-full lg:w-80 shrink-0 flex flex-col overflow-hidden">

          {proposalData ? (
            /* ── Proposal preview panel ── */
            <>
              {/* Header */}
              <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
                <button
                  onClick={() => setProposalData(null)}
                  className="flex items-center gap-1.5 text-xs text-text-muted hover:text-foreground transition-colors"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}>
                    <path d="M9 3L5 7l4 4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Back to TBDs
                </button>
                <a
                  href={getProposalExportUrl(projectId)}
                  download
                  className="flex items-center gap-1 text-xs text-text-muted hover:text-foreground transition-colors"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}>
                    <path d="M7 2v7M4 6l3 3 3-3M2 11h10" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Download
                </a>
              </div>

              {/* Generation progress bar */}
              {(generating || retrying) && (() => {
                const done = proposalData.structured_sections?.length ?? 0;
                const total = 10;
                const pct = Math.round((done / total) * 100);
                const label = done === 0 ? "Starting…" : done === total ? "Finalizing…" : `${done} of ${total} sections`;
                return (
                  <div className="px-4 py-3 border-b border-border bg-surface-subtle/40 shrink-0">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-[11px] text-text-muted">{label}</span>
                      <span className="text-[11px] font-semibold text-primary">{pct}%</span>
                    </div>
                    <div className="h-1 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full transition-all duration-500 ease-out"
                        style={{ width: `${Math.max(4, pct)}%` }}
                      />
                    </div>
                  </div>
                );
              })()}

              {/* Sections */}
              <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
                <p className="text-[11px] font-semibold text-foreground uppercase tracking-wide">
                  {generating || retrying ? "Generating Proposal…" : "Generated Proposal"}
                </p>
                {proposalData.structured_sections?.length ? (
                  <ProposalAccordion
                    sections={proposalData.structured_sections}
                    projectId={projectId}
                    onSectionUpdate={(updated) => {
                      setProposalData((p) =>
                        p
                          ? {
                              ...p,
                              structured_sections: p.structured_sections?.map((s) =>
                                s.section_id === updated.section_id ? updated : s,
                              ),
                            }
                          : p,
                      )
                    }}
                  />
                ) : proposalData.sections.length === 0 ? (
                  <p className="text-xs text-text-muted">No sections found in proposal.</p>
                ) : (
                  proposalData.sections.map((section, i) => (
                    <div key={i} className="space-y-1">
                      <h3 className="text-xs font-semibold text-foreground">{section.heading}</h3>
                      <p className="text-xs text-text-secondary leading-relaxed whitespace-pre-wrap">
                        {section.body}
                      </p>
                    </div>
                  ))
                )}
              </div>

              {/* Actions */}
              <div className="shrink-0 px-4 py-4 border-t border-border bg-background space-y-3">
                {proposalError && (
                  <ErrorBanner message={proposalError} />
                )}

                {showRetryInput && (
                  <div className="space-y-2">
                    <textarea
                      value={retryComment}
                      onChange={(e) => setRetryComment(e.target.value)}
                      placeholder="Describe what to change or add…"
                      rows={3}
                      className="w-full resize-none bg-card border border-border rounded-lg px-3 py-2 text-xs text-foreground placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-primary/40"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={handleRetry}
                        disabled={!retryComment.trim() || retrying}
                        className={cn(
                          "flex-1 flex items-center justify-center gap-1.5 py-2 rounded-md text-xs font-medium transition-colors",
                          retryComment.trim() && !retrying
                            ? "bg-primary text-primary-foreground hover:bg-accent-hover"
                            : "bg-muted text-text-muted cursor-not-allowed"
                        )}
                      >
                        {retrying ? (
                          <>
                            <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                              <path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" />
                            </svg>
                            Regenerating…
                          </>
                        ) : "Submit Feedback"}
                      </button>
                      <button
                        onClick={() => { setShowRetryInput(false); setRetryComment(""); }}
                        className="px-3 py-2 rounded-md text-xs text-text-muted hover:text-foreground border border-border transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {!showRetryInput && (
                  <div className="flex gap-2">
                    <button
                      onClick={() => setShowRetryInput(true)}
                      disabled={generating || retrying}
                      className={cn(
                        "flex-1 py-2 rounded-md text-xs font-medium border border-border text-foreground transition-colors",
                        generating || retrying ? "opacity-50 cursor-not-allowed" : "hover:bg-card",
                      )}
                    >
                      Retry with Comment
                    </button>
                    <button
                      onClick={handleApprove}
                      disabled={approving || generating || retrying}
                      className={cn(
                        "flex-1 flex items-center justify-center gap-1.5 py-2 rounded-md text-xs font-medium transition-colors",
                        !approving && !generating && !retrying
                          ? "bg-primary text-primary-foreground hover:bg-accent-hover"
                          : "bg-muted text-text-muted cursor-not-allowed"
                      )}
                    >
                      {approving ? (
                        <>
                          <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                            <path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" />
                          </svg>
                          Approving…
                        </>
                      ) : (
                        <>
                          Approve
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}>
                            <path d="M2 7h10M8 3l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        </>
                      )}
                    </button>
                  </div>
                )}
              </div>
            </>
          ) : (
            /* ── TBD widget + generate button ── */
            <>
              <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
                <span className="text-xs font-semibold text-foreground">TBD Items</span>
                <div className="flex items-center gap-2">
                  {outstandingTbds > 0 && (
                    <span className="text-[11px] font-medium text-warning bg-warning-subtle px-2 py-0.5 rounded-full">
                      {outstandingTbds} open
                    </span>
                  )}
                  <button
                    onClick={() => refetchTbds()}
                    disabled={tbdsPending}
                    title="Refresh TBD items"
                    className="text-text-muted hover:text-foreground transition-colors disabled:opacity-40"
                  >
                    <svg
                      className={cn("w-3.5 h-3.5", tbdsPending && "animate-spin")}
                      fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}
                    >
                      <path d="M12 7A5 5 0 1 1 7 2" strokeLinecap="round" />
                      <path d="M7 2l2 2-2 2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>
                </div>
              </div>

              <div className="flex-1 min-h-0 relative">
              <div className="absolute inset-0 overflow-y-auto px-4 py-4">
                {tbdsPending ? (
                  <div className="flex flex-col gap-2">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="h-14 rounded-md bg-surface-subtle animate-pulse" />
                    ))}
                  </div>
                ) : tbdsError ? (
                  <div className="flex flex-col items-center py-8 gap-3 text-center">
                    <p className="text-xs text-destructive">Failed to load TBD items.</p>
                    <button
                      onClick={() => refetchTbds()}
                      className="px-3 py-1.5 rounded-md text-xs font-medium border border-border text-foreground hover:bg-surface-subtle transition-colors"
                    >
                      Retry
                    </button>
                  </div>
                ) : (
                  <TBDClarificationWidget items={tbdItems} onAction={handleTBDAction} onBulkAction={handleBulkTBDAction} newItemIds={newTbdIds} />
                )}
              </div>
              <div className="pointer-events-none absolute bottom-0 inset-x-0 h-8 bg-gradient-to-t from-background to-transparent" />
              </div>

              {/* Generate Proposal */}
              <div className="shrink-0 px-4 py-4 border-t border-border bg-background space-y-3">
                {proposalError && (
                  <ErrorBanner message={proposalError} />
                )}
                {!allTbdsResolved && (
                  <p className="text-[11px] text-text-muted text-center">
                    Resolve {outstandingTbds} TBD{outstandingTbds !== 1 ? "s" : ""} to unlock proposal generation.
                  </p>
                )}
                <button
                  onClick={handleGenerateProposal}
                  disabled={!allTbdsResolved || generating}
                  className={cn(
                    "w-full flex items-center justify-center gap-2 py-2.5 rounded-md text-sm font-medium transition-colors",
                    allTbdsResolved && !generating
                      ? "bg-primary text-primary-foreground hover:bg-accent-hover"
                      : "bg-muted text-text-muted cursor-not-allowed"
                  )}
                >
                  {generating ? (
                    <>
                      <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                        <path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" />
                      </svg>
                      Generating…
                    </>
                  ) : (
                    <>
                      Generate Proposal
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2}>
                        <path d="M2 7h10M8 3l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </>
                  )}
                </button>
              </div>
            </>
          )}

        </div>

      </div>
    </div>
  );
}
