"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

export interface NavItem {
  key: string;
  label: string;
  href: string;
  icon: React.ReactNode;
  phase?: string | null;
}

interface AppSidebarProps {
  projectId?: string;
  activePhase?: string | null;
  className?: string;
}

function IconDashboard() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={1.75}>
      <rect x="2" y="2" width="5" height="5" rx="1" />
      <rect x="9" y="2" width="5" height="5" rx="1" />
      <rect x="2" y="9" width="5" height="5" rx="1" />
      <rect x="9" y="9" width="5" height="5" rx="1" />
    </svg>
  );
}
function IconUpload() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={1.75}>
      <path d="M8 10V3M5 6l3-3 3 3" />
      <path d="M3 12h10" strokeLinecap="round" />
    </svg>
  );
}
function IconShield() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={1.75}>
      <path d="M8 2L3 4.5V8c0 2.8 2 4.8 5 6 3-1.2 5-3.2 5-6V4.5L8 2z" />
    </svg>
  );
}
function IconChat() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={1.75}>
      <path d="M2 3h12v8H9l-3 3v-3H2V3z" />
    </svg>
  );
}
function IconLayers() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={1.75}>
      <path d="M8 2L2 5l6 3 6-3-6-3z" />
      <path d="M2 9l6 3 6-3" />
      <path d="M2 12l6 3 6-3" />
    </svg>
  );
}
function IconUsers() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={1.75}>
      <circle cx="6" cy="5" r="2.5" />
      <path d="M1 13c0-2.8 2.2-5 5-5s5 2.2 5 5" />
      <path d="M11 7a2.5 2.5 0 1 0 0-5" strokeLinecap="round" />
      <path d="M15 13c0-2.8-1.8-4.5-4-5" />
    </svg>
  );
}
function IconCalculator() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={1.75}>
      <rect x="3" y="2" width="10" height="12" rx="1.5" />
      <rect x="5" y="4" width="6" height="2" rx="0.5" />
      <circle cx="5.5" cy="9" r="0.75" fill="currentColor" stroke="none" />
      <circle cx="8" cy="9" r="0.75" fill="currentColor" stroke="none" />
      <circle cx="10.5" cy="9" r="0.75" fill="currentColor" stroke="none" />
      <circle cx="5.5" cy="11.5" r="0.75" fill="currentColor" stroke="none" />
      <circle cx="8" cy="11.5" r="0.75" fill="currentColor" stroke="none" />
      <circle cx="10.5" cy="11.5" r="0.75" fill="currentColor" stroke="none" />
    </svg>
  );
}
function IconList() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={1.75}>
      <path d="M6 4h7M6 8h7M6 12h7" strokeLinecap="round" />
      <circle cx="3" cy="4" r="1" fill="currentColor" stroke="none" />
      <circle cx="3" cy="8" r="1" fill="currentColor" stroke="none" />
      <circle cx="3" cy="12" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}
function IconChart() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={1.75}>
      <path d="M2 12L6 7l3 3 5-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const GLOBAL_NAV = [
  { key: "dashboard", label: "All Projects", href: "/", icon: <IconDashboard />, phase: null },
  { key: "upload", label: "New Project", href: "/projects/new", icon: <IconUpload />, phase: null },
];

function buildProjectNav(projectId: string) {
  const base = `/projects/${projectId}`;
  return [
    { key: "redaction", label: "Redaction Review", href: `${base}/redaction`, icon: <IconShield />, phase: "redaction" },
    { key: "chat", label: "Chat & Refine", href: `${base}/chat`, icon: <IconChat />, phase: "chat" },
    { key: "tech-stack", label: "Tech Stack", href: `${base}/techstack`, icon: <IconLayers />, phase: "tech-stack" },
    { key: "team", label: "Team", href: `${base}/team`, icon: <IconUsers />, phase: "team" },
    { key: "estimation", label: "Estimation", href: `${base}/estimation`, icon: <IconCalculator />, phase: "estimation" },
    { key: "epics", label: "Epics & Tasks", href: `${base}/epics`, icon: <IconList />, phase: "epics" },
    { key: "metrics", label: "Metrics", href: `${base}/metrics`, icon: <IconChart />, phase: null },
  ];
}

function NavLink({ item, activePhase }: { item: NavItem; activePhase?: string | null }) {
  const pathname = usePathname();
  const isActive =
    pathname === item.href ||
    (item.phase && activePhase === item.phase);

  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors",
        isActive
          ? "bg-accent text-accent-foreground font-medium"
          : "text-text-secondary hover:bg-sidebar-hover hover:text-foreground"
      )}
    >
      {item.icon}
      {item.label}
    </Link>
  );
}

export function AppSidebar({ projectId: projectIdProp, activePhase, className }: AppSidebarProps) {
  const pathname = usePathname();
  const projectId = projectIdProp ?? pathname.match(/\/projects\/([^/]+)/)?.[1];
  const projectNav = projectId ? buildProjectNav(projectId) : [];

  return (
    <aside
      className={cn(
        "flex flex-col w-[var(--width-sidebar)] shrink-0 bg-sidebar border-r border-sidebar-border h-full",
        className
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 h-[var(--height-topbar)] border-b border-sidebar-border shrink-0">
        <div className="w-6 h-6 rounded-md bg-primary flex items-center justify-center">
          <svg className="w-3.5 h-3.5 text-primary-foreground" fill="none" viewBox="0 0 14 14" stroke="currentColor" strokeWidth={2.5}>
            <path d="M2 10L7 3l5 7" />
          </svg>
        </div>
        <span className="text-sm font-semibold text-foreground">Acuity</span>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-0.5 p-2 flex-1 overflow-y-auto">
        {GLOBAL_NAV.map((item) => (
          <NavLink key={item.key} item={item} activePhase={activePhase} />
        ))}

        {projectNav.length > 0 && (
          <>
            <div className="mt-3 mb-1 px-3">
              <span className="text-[10px] font-semibold uppercase tracking-widest text-text-muted">
                Current Project
              </span>
            </div>
            {projectNav.map((item) => (
              <NavLink key={item.key} item={item} activePhase={activePhase} />
            ))}
          </>
        )}
      </nav>
    </aside>
  );
}
