"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { ChatThread } from "@/components/chat-thread";
import { TBDClarificationWidget } from "@/components/tbd-clarification-widget";
import { getPhasesForRoute, getNextPhaseRoute } from "@/lib/project-phases";
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

// TODO (Epic 4): fetch from GET /api/v1/projects/{id}/tbds
const INITIAL_TBDS: TBDItem[] = [
  {
    id: "tbd1",
    title: "Processing SLA",
    desc: "Section 3.2 states 'documents should be processed promptly' but does not specify a target turnaround time. What is the expected SLA for a 50-page PDF?",
    level: "Explicit TBD",
    status: "open",
  },
  {
    id: "tbd2",
    title: "Team Size",
    desc: "Section 4.1 mentions 'a small engineering team' without quantifying headcount. How many engineers are available for this project?",
    level: "Vague statement",
    status: "open",
  },
  {
    id: "tbd3",
    title: "Cloud Provider",
    desc: "The deployment section does not specify a target cloud provider or region. Where will this system be hosted?",
    level: "Explicit TBD",
    status: "open",
  },
  {
    id: "tbd4",
    title: "Authentication Method",
    desc: "User authentication is mentioned but no method is specified (SSO, OAuth, email/password). What authentication strategy should be used?",
    level: "Missing section",
    status: "open",
  },
];

// Simulated AI responses keyed by message content patterns
function simulatedReply(userText: string): string {
  const lower = userText.toLowerCase();
  if (lower.includes("sla") || lower.includes("processing time"))
    return "Got it. Based on the document context, a 2–5 minute SLA for PDFs up to 50 pages seems reasonable. I'll capture that as the processing target. Anything else to clarify?";
  if (lower.includes("team") || lower.includes("engineer"))
    return "Noted — I'll plan the team suggestion around that headcount. This also affects the effort estimates I'll generate in Phase 5.";
  if (lower.includes("cloud") || lower.includes("aws") || lower.includes("gcp") || lower.includes("azure"))
    return "Cloud provider noted. I'll factor that into the tech stack suggestion in Phase 3, including managed services and deployment options specific to that platform.";
  if (lower.includes("auth") || lower.includes("login") || lower.includes("sso"))
    return "Authentication strategy noted. I'll include this in the tech stack recommendation and make sure the epic breakdown covers the auth implementation tasks.";
  return "Thanks — I've noted that. Is there anything else in the document you'd like to clarify before we generate the proposal?";
}

export default function ChatPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [messages, setMessages]   = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [tbdItems, setTbdItems]   = useState<TBDItem[]>(INITIAL_TBDS);
  const [input, setInput]         = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef   = useRef<HTMLDivElement>(null);

  const outstandingTbds = tbdItems.filter((t) => t.status === "open").length;
  const allTbdsResolved = outstandingTbds === 0;

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
    if (!text || isLoading) return;
    setInput("");

    const userMsg: ChatMessage = {
      id: String(Date.now()),
      role: "pm",
      text,
      timestamp: new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    // TODO (Epic 4): POST /api/v1/projects/{id}/chat with { message: text }
    await new Promise((res) => setTimeout(res, 1200));
    const aiMsg: ChatMessage = {
      id: String(Date.now() + 1),
      role: "ai",
      text: simulatedReply(text),
      timestamp: new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }),
    };
    setMessages((prev) => [...prev, aiMsg]);
    setIsLoading(false);
  }

  function handleTBDAction(id: string, action: TBDAction) {
    setTbdItems((prev) => prev.map((t) => t.id === id ? { ...t, status: action } : t));
    // TODO (Epic 4): POST /api/v1/projects/{id}/clarifications { tbd_id, action }
  }

  async function handleGenerateProposal() {
    setGenerating(true);
    // TODO (Epic 4): POST /api/v1/projects/{id}/proposal
    await new Promise((res) => setTimeout(res, 1500));
    router.push(getNextPhaseRoute("chat", params.id));
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
