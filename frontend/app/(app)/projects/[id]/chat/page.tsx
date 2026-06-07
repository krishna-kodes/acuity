"use client";

import { useState, useRef, useEffect, use } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { ChatThread } from "@/components/chat-thread";
import { TBDClarificationWidget } from "@/components/tbd-clarification-widget";
import { getPhasesForRoute, getNextPhaseRoute } from "@/lib/project-phases";
import { getTBDs, submitClarification, generateProposal } from "@/lib/api";
import type { ChatMessage } from "@/components/chat-thread";
import type { TBDItem, TBDAction } from "@/components/tbd-clarification-widget";
import { cn } from "@/lib/utils";

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: "1",
    role: "ai",
    text: "I've processed your requirements document and anonymized the PII. I found 4 items that need clarification before I can generate a complete proposal. You can ask me anything about the document, or work through the TBD items on the right.",
    timestamp: "09:41",
  },
];

const TBD_LEVEL_LABELS: Record<number, TBDItem["level"]> = {
  1: "Explicit TBD",
  2: "Vague statement",
  3: "Missing section",
  4: "Contradiction",
};


export default function ChatPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: projectId } = use(params);
  const router = useRouter();
  const [messages, setMessages]     = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [localStatuses, setLocalStatuses] = useState<Record<string, TBDAction>>({});
  const [input, setInput]           = useState("");
  const [isLoading, setIsLoading]   = useState(false);
  const [generating, setGenerating] = useState(false);
  const textareaRef  = useRef<HTMLTextAreaElement>(null);
  const bottomRef    = useRef<HTMLDivElement>(null);
  const sendingRef   = useRef(false);

  const { data: remoteTbds } = useQuery({
    queryKey: ["tbds", projectId],
    queryFn: async () => {
      const { data, error } = await getTBDs(projectId);
      if (error) throw new Error(String(error));
      return (data ?? []).map((t) => ({
        id: t.id,
        title: t.question,
        desc: t.question,
        level: TBD_LEVEL_LABELS[t.level] ?? "Explicit TBD",
        status: "open" as TBDAction,
      }));
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const tbdItems: TBDItem[] = (remoteTbds ?? []).map((t) => ({
    ...t,
    status: localStatuses[t.id] ?? t.status,
  }));

  const outstandingTbds = tbdItems.filter((t) => t.status === "open").length;
  const allTbdsResolved = tbdItems.length === 0 || outstandingTbds === 0;

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

  async function sendMessage() {
    const text = input.trim();
    if (!text || isLoading || sendingRef.current) return;
    sendingRef.current = true;
    setInput("");

    const userMsg: ChatMessage = {
      id: String(Date.now()),
      role: "pm",
      text,
      timestamp: new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

  // Add empty AI message placeholder
  const aiId = String(Date.now() + 1);
  const ts = new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
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

    if (!response.ok || !response.body) {
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
          const event = JSON.parse(line.slice(6)) as { type: string; content?: string; items?: unknown[]; message?: string };
          if (event.type === "token" && event.content) {
            accumulated += event.content;
            setMessages((prev) =>
              prev.map((m) => m.id === aiId ? { ...m, text: accumulated } : m)
            );
          } else if (event.type === "done") {
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
    // On error, update the placeholder message with an error note
    setMessages((prev) =>
      prev.map((m) =>
        m.id === aiId
          ? { ...m, text: "Sorry, I couldn't get a response. Please try again." }
          : m
      )
    );
  } finally {
    setIsLoading(false);
    sendingRef.current = false;
  }
  }

  function handleTBDAction(id: string, action: TBDAction) {
    setLocalStatuses((prev) => ({ ...prev, [id]: action }));
    submitClarification(projectId, id, action).catch(() => {
      // Fire-and-forget; local state already updated
    });
  }

  async function handleGenerateProposal() {
    setGenerating(true);
    try {
      await generateProposal(projectId);
    } catch {
      // Non-fatal — navigate regardless
    }
    router.push(getNextPhaseRoute("chat", projectId));
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
            <ChatThread messages={messages} isLoading={isLoading} />
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

        {/* Right: TBD widget + generate proposal */}
        <div className="w-full lg:w-80 shrink-0 flex flex-col overflow-hidden lg:overflow-y-auto">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
            <span className="text-xs font-semibold text-foreground">TBD Items</span>
            {outstandingTbds > 0 && (
              <span className="text-[11px] font-medium text-warning bg-warning-subtle px-2 py-0.5 rounded-full">
                {outstandingTbds} open
              </span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-4">
            <TBDClarificationWidget items={tbdItems} onAction={handleTBDAction} />
          </div>

          {/* Generate Proposal */}
          <div className="shrink-0 px-4 py-4 border-t border-border bg-background">
            {!allTbdsResolved && (
              <p className="text-[11px] text-text-muted mb-3 text-center">
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
        </div>

      </div>
    </div>
  );
}
