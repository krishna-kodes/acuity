/**
 * Design tokens extracted from the Claude Design file.
 * Source: docs/AI PM Tool (standalone).html
 * Used by: tailwind.config.ts (E0-T2), globals.css (E0-T3)
 */

export const colors = {
  // Core surfaces
  bg: "#F9F8F6",
  surface: "#FFFFFF",
  surfaceSubtle: "#F3F2EF",

  // Sidebar
  sidebarBg: "#F3F2EF",
  sidebarHover: "#EAE8E3",

  // Accent (primary blue)
  accent: "#3A6EA5",
  accentHover: "#316090",           // color-mix(accent 84%, black)
  accentSubtle: "#EBF0F7",          // color-mix(accent 12%, white)

  // Text
  text: "#1A1A19",
  textSecondary: "#6B6860",
  textMuted: "#A09D96",

  // Borders
  border: "#E8E6E1",
  borderStrong: "#D8D5CE",

  // Status: synced
  success: "#2D6A4F",
  successSubtle: "#EAF4EF",

  // Status: failed
  destructive: "#C0392B",
  destructiveSubtle: "#FDECEA",

  // Status: skipped
  warning: "#92600A",
  warningSubtle: "#FEF3E2",

  // Status: pending (uses textMuted)
  muted: "#A09D96",
  mutedSubtle: "#F3F2EF",
} as const;

/**
 * Sync status → color variant mapping (matches SYNC constant in design file)
 * pending  → muted
 * synced   → success
 * skipped  → warning
 * failed   → destructive
 */
export const syncStatusColors = {
  pending: { fg: colors.muted, bg: colors.mutedSubtle },
  synced: { fg: colors.success, bg: colors.successSubtle },
  skipped: { fg: colors.warning, bg: colors.warningSubtle },
  failed: { fg: colors.destructive, bg: colors.destructiveSubtle },
} as const;

export const typography = {
  // Font families
  fontSans: ["Inter", "ui-sans-serif", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
  fontMono: ["JetBrains Mono", "ui-monospace", "monospace"],

  // Font sizes (px values observed in design)
  fontSize: {
    "2xs": "10px",
    xs: "11px",
    "xs+": "11.5px",
    sm: "12px",
    "sm+": "12.5px",
    base: "13px",
    md: "14px",
    lg: "16px",
    xl: "20px",
  },

  // Font weights
  fontWeight: {
    normal: "400",
    medium: "500",
    semibold: "600",
    bold: "700",
  },

  // Line heights
  lineHeight: {
    tight: "1.2",
    normal: "1.5",
  },
} as const;

export const spacing = {
  // Common gaps and paddings observed in design
  1: "4px",
  1.5: "6px",
  2: "8px",
  2.5: "10px",
  3: "12px",
  3.5: "14px",
  4: "16px",
  4.5: "18px",
  5: "20px",
  5.5: "22px",
  cardPad: "20px",
} as const;

export const borderRadius = {
  xs: "4px",    // tags, chips
  sm: "6px",
  md: "8px",    // standard cards, inputs
  lg: "10px",   // icon containers, avatars
  xl: "12px",   // modals, dialogs
  "2xl": "14px",
  full: "999px", // pills, badges
} as const;

export const shadows = {
  xs: "0 1px 2px rgba(0,0,0,0.08)",
  sm: "0 1px 2px rgba(0,0,0,0.12)",
  md: "0 1px 4px rgba(0,0,0,0.12)",
  modal: "0 20px 60px rgba(26,26,25,0.25)",
} as const;

export const layout = {
  topBarHeight: "56px",
  sidebarWidth: "220px",   // estimated from design proportions
} as const;
