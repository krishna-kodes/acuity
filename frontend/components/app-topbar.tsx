"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const PATH_TITLES: Record<string, string> = {
  "/":           "All Projects",
  "/projects/new": "New Project",
  "/redaction":  "Redaction Review",
  "/chat":       "Chat & Refine",
  "/techstack":  "Tech Stack",
  "/team":       "Team Suggestion",
  "/estimation": "Effort Estimation",
  "/epics":      "Epics & Tasks",
  "/metrics":    "Metrics",
};

function deriveTitle(pathname: string): string {
  if (PATH_TITLES[pathname]) return PATH_TITLES[pathname];
  for (const [suffix, label] of Object.entries(PATH_TITLES)) {
    if (pathname.endsWith(suffix)) return label;
  }
  return "Acuity";
}

interface AppTopbarProps {
  className?: string;
}

export function AppTopbar({ className }: AppTopbarProps) {
  const pathname = usePathname();
  const title = deriveTitle(pathname);

  return (
    <header
      className={cn(
        "flex items-center justify-between px-5 shrink-0 bg-background border-b border-border",
        "h-[var(--height-topbar)]",
        className
      )}
    >
      <h1 className="text-sm font-semibold text-foreground">{title}</h1>

      <Link
        href="/projects/new"
        className={cn(
          "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium",
          "bg-primary text-primary-foreground hover:bg-accent-hover transition-colors"
        )}
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2.5}>
          <path d="M6 2v8M2 6h8" strokeLinecap="round" />
        </svg>
        New Project
      </Link>
    </header>
  );
}
