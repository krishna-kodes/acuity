import type { Phase, PhaseStatus } from "@/components/phase-progress-stepper";

const PHASE_LABELS: string[] = [
  "Ingestion",
  "Refinement",
  "Modules",
  "Tech Stack",
  "Team",
  "Estimation",
  "Epics & Sync",
];

// Route segment → 1-based phase number (0 = before first phase, 8 = all complete)
const ROUTE_TO_PHASE: Record<string, number> = {
  redaction: 1,
  chat:      2,
  modules:   3,
  techstack: 4,
  team:      5,
  estimation:6,
  epics:     7,
  metrics:   8, // all phases complete on metrics screen
};

// Ordered phase route segments — used for navigation
const PHASE_ROUTES = ["redaction", "chat", "modules", "techstack", "team", "estimation", "epics"] as const;
export type PhaseRoute = typeof PHASE_ROUTES[number];

/**
 * Returns a Phase[] for the PhaseProgressStepper derived purely from the
 * current page's route segment. Removes the hardcoded arrays in each page.
 */
export function getPhasesForRoute(segment: string): Phase[] {
  const activePhase = ROUTE_TO_PHASE[segment] ?? 1;
  return PHASE_LABELS.map((label, i) => {
    const phaseNum = i + 1;
    const status: PhaseStatus =
      phaseNum < activePhase  ? "complete"    :
      phaseNum === activePhase ? "in_progress" :
      "locked";
    return { label, status };
  });
}

/**
 * Returns the URL for the next phase page given the current route segment.
 * Falls back to /metrics when past the last phase.
 */
export function getNextPhaseRoute(current: string, projectId: string): string {
  const idx = PHASE_ROUTES.indexOf(current as PhaseRoute);
  if (idx === -1 || idx === PHASE_ROUTES.length - 1) {
    return `/projects/${projectId}/metrics`;
  }
  return `/projects/${projectId}/${PHASE_ROUTES[idx + 1]}`;
}

/**
 * Returns true if a phase number is reachable given the current route.
 * Used to enable/disable sidebar nav items before Epic 4 API wiring.
 */
export function isPhaseReachable(segment: string, phaseNumber: number): boolean {
  const activePhase = ROUTE_TO_PHASE[segment] ?? 1;
  return phaseNumber <= activePhase;
}
