"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { listProjects } from "@/lib/api";

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
function IconDocument() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={1.75}>
      <path d="M4 2h6l3 3v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z" />
      <path d="M10 2v3h3" />
      <path d="M5 8h6M5 11h4" strokeLinecap="round" />
    </svg>
  );
}
function IconModules() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={1.75}>
      <rect x="2" y="2" width="5" height="5" rx="1" />
      <rect x="9" y="2" width="5" height="5" rx="1" />
      <rect x="2" y="9" width="5" height="5" rx="1" />
      <path d="M9 11.5h5M11.5 9v5" strokeLinecap="round" />
    </svg>
  );
}

// current_phase is a number from the API; map to route segment
const PHASE_NUMBER_TO_ROUTE: Record<number, string> = {
  1: "redaction",
  2: "chat",
  3: "modules",
  4: "techstack",
  5: "team",
  6: "estimation",
  7: "epics",
};

const GLOBAL_NAV = [
  { key: "dashboard", label: "All Projects", href: "/", icon: <IconDashboard />, phase: null },
];

function buildProjectNav(projectId: string) {
  const base = `/projects/${projectId}`;
  return [
    { key: "upload", label: "Upload", href: "/projects/new", icon: <IconUpload />, phase: null },
    { key: "redaction", label: "Redaction Review", href: `${base}/redaction`, icon: <IconShield />, phase: "redaction" },
    { key: "chat", label: "Chat & Refine", href: `${base}/chat`, icon: <IconChat />, phase: "chat" },
    { key: "modules", label: "Extract Modules", href: `${base}/modules`, icon: <IconModules />, phase: "modules" },
    { key: "tech-stack", label: "Tech Stack", href: `${base}/techstack`, icon: <IconLayers />, phase: "tech-stack" },
    { key: "team", label: "Team", href: `${base}/team`, icon: <IconUsers />, phase: "team" },
    { key: "estimation", label: "Estimation", href: `${base}/estimation`, icon: <IconCalculator />, phase: "estimation" },
    { key: "epics", label: "Epics & Tasks", href: `${base}/epics`, icon: <IconList />, phase: "epics" },
    { key: "documents", label: "Documents", href: `${base}/documents`, icon: <IconDocument />, phase: null },
    { key: "metrics", label: "Metrics", href: `${base}/metrics`, icon: <IconChart />, phase: null },
  ];
}

function NavLink({ item, activePhase }: { item: NavItem; activePhase?: string | null }) {
  const pathname = usePathname();
  // Root path needs exact match; other paths use startsWith so sub-routes stay highlighted
  const isActive =
    (item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)) ||
    (item.phase != null && activePhase === item.phase);

  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors",
        isActive
          ? "bg-accent text-accent-foreground font-medium ring-1 ring-inset ring-accent-foreground/10"
          : "text-text-secondary hover:bg-sidebar-hover hover:text-foreground"
      )}
    >
      {item.icon}
      {item.label}
    </Link>
  );
}

function ProjectSwitcher({ currentProjectId }: { currentProjectId: string }) {
  const [open, setOpen] = useState(false)
  const router = useRouter()

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => {
      const { data, error } = await listProjects()
      if (error) throw new Error(String(error))
      return data ?? []
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  })

  const current = projects?.find((p) => p.id === currentProjectId)
  const displayName = current?.name ?? `Project ${currentProjectId}`

  function navigate(project: { id: string; current_phase: number }) {
    const route = PHASE_NUMBER_TO_ROUTE[project.current_phase] ?? "redaction"
    router.push(`/projects/${project.id}/${route}`)
    setOpen(false)
  }

  return (
    <div className="relative px-2 mb-1">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md hover:bg-sidebar-hover transition-colors"
      >
        {/* Project icon tile */}
        <div className="w-7 h-7 rounded-md bg-primary/15 flex items-center justify-center shrink-0">
          <svg className="w-4 h-4 text-primary" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={1.75}>
            <path d="M2 5.5A1.5 1.5 0 0 1 3.5 4h3l1.5 1.5H12.5A1.5 1.5 0 0 1 14 7v5a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 12V5.5z" />
          </svg>
        </div>
        {/* Text */}
        <div className="flex-1 min-w-0 text-left">
          <div className="text-sm font-medium text-foreground truncate">{displayName}</div>
          <div className="text-[11px] text-text-muted">Switch project</div>
        </div>
        {/* Chevron */}
        <svg
          className={cn("w-3 h-3 text-text-muted shrink-0 transition-transform", open && "rotate-180")}
          fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2}
        >
          <path d="M2 4l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && projects && projects.length > 0 && (
        <div className="absolute left-2 right-2 top-full mt-1 z-50 bg-card border border-border rounded-lg shadow-md overflow-hidden max-h-56 overflow-y-auto">
          {projects.map((p) => (
            <button
              key={p.id}
              onClick={() => navigate(p)}
              className={cn(
                "w-full text-left px-3 py-2 text-sm transition-colors hover:bg-surface-subtle",
                p.id === currentProjectId
                  ? "bg-accent text-accent-foreground font-medium"
                  : "text-foreground"
              )}
            >
              {p.name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function ProfileMenu() {
  const [open, setOpen] = useState(false)
  return (
    <div className="relative border-t border-sidebar-border p-2 shrink-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md hover:bg-sidebar-hover transition-colors"
      >
        <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center text-[11px] font-bold text-accent-foreground shrink-0">
          PM
        </div>
        <div className="flex-1 min-w-0 text-left">
          <div className="text-xs font-medium text-foreground truncate">You</div>
          <div className="text-[10px] text-text-muted truncate">Product Manager</div>
        </div>
        <svg
          className={cn("w-3 h-3 text-text-muted shrink-0 transition-transform", open && "rotate-180")}
          fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2}
        >
          <path d="M2 4l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <div className="absolute bottom-full left-2 right-2 mb-1 z-50 bg-card border border-border rounded-lg shadow-md overflow-hidden">
          <button
            className="w-full text-left px-3 py-2 text-sm text-foreground hover:bg-surface-subtle transition-colors"
            onClick={() => setOpen(false)}
          >
            Your profile
          </button>
          <button
            className="w-full text-left px-3 py-2 text-sm text-foreground hover:bg-surface-subtle transition-colors"
            onClick={() => setOpen(false)}
          >
            Settings
          </button>
          <Link
            href="/admin/employees"
            onClick={() => setOpen(false)}
            className="block px-3 py-2 text-sm text-foreground hover:bg-surface-subtle transition-colors"
          >
            Administration
          </Link>
          <div className="border-t border-border" />
          <button
            className="w-full text-left px-3 py-2 text-sm text-destructive hover:bg-surface-subtle transition-colors"
            onClick={() => setOpen(false)}
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  )
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
        <span className="text-sm font-semibold text-foreground">Cohort PM</span>
        <span className="text-xs text-text-muted"> / AI Project Studio</span>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-0.5 p-2 flex-1 overflow-y-auto">
        {GLOBAL_NAV.map((item) => (
          <NavLink key={item.key} item={item} activePhase={activePhase} />
        ))}

        {projectId && <ProjectSwitcher currentProjectId={projectId} />}

        {projectNav.length > 0 && (
          <>
            <div className="mt-3 mb-1 px-3">
              <span className="text-[10px] font-semibold uppercase tracking-widest text-text-muted">
                PIPELINE
              </span>
            </div>
            {projectNav.map((item) => (
              <NavLink key={item.key} item={item} activePhase={activePhase} />
            ))}
          </>
        )}
      </nav>

      <ProfileMenu />
    </aside>
  );
}
