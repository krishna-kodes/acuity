"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const PATH_TITLES: Record<string, string> = {
  "/":                  "All Projects",
  "/projects/new":      "New Project",
  "/redaction":         "Redaction Review",
  "/chat":              "Chat & Refine",
  "/techstack":         "Tech Stack",
  "/team":              "Team Suggestion",
  "/estimation":        "Effort Estimation",
  "/epics":             "Epics & Tasks",
  "/metrics":           "Metrics",
  "/admin/employees":   "Employees",
  "/admin/skills":      "Skills",
};

function deriveTitle(pathname: string): string {
  if (PATH_TITLES[pathname]) return PATH_TITLES[pathname];
  for (const [suffix, label] of Object.entries(PATH_TITLES)) {
    if (pathname.endsWith(suffix)) return label;
  }
  return "";
}

interface AppTopbarProps {
  onMenuClick?: () => void;
  className?: string;
}

export function AppTopbar({ onMenuClick, className }: AppTopbarProps) {
  const pathname = usePathname();
  const title = deriveTitle(pathname);

  return (
    <header
      className={cn(
        "flex items-center justify-between px-4 shrink-0 bg-background border-b border-border",
        "h-[var(--height-topbar)]",
        className
      )}
    >
      <div className="flex items-center gap-3">
        {/* Hamburger — mobile only */}
        <button
          onClick={onMenuClick}
          className="md:hidden w-8 h-8 flex items-center justify-center rounded-md text-text-secondary hover:bg-surface-subtle transition-colors"
          aria-label="Toggle menu"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
            <path d="M2 4h12M2 8h12M2 12h12" strokeLinecap="round" />
          </svg>
        </button>
        <h1 className="text-sm font-semibold text-foreground">{title}</h1>
      </div>

    </header>
  );
}
