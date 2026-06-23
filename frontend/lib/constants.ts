/** Client-side navigation state identifier for the 8 dashboard views */
export type ViewKey =
  | "dashboard"
  | "live"
  | "events"
  | "review"
  | "analytics"
  | "aws"
  | "status"
  | "settings";

/** All valid view keys as a constant array (useful for iteration and validation) */
export const VIEW_KEYS: ViewKey[] = [
  "dashboard",
  "live",
  "events",
  "review",
  "analytics",
  "aws",
  "status",
  "settings",
] as const;

/** Polling intervals in milliseconds */
export const POLLING_INTERVALS = {
  /** 2s for stream status */
  STREAM: 2000,
  /** 10s for dashboard widgets */
  DASHBOARD: 10000,
  /** 30s for health/AWS */
  HEALTH: 30000,
} as const;

/** Semantic color tokens for status indicators */
export const THEME_TOKENS = {
  success: "hsl(142, 71%, 45%)",
  warning: "hsl(43, 96%, 56%)",
  danger: "hsl(0, 84%, 60%)",
  info: "hsl(217, 91%, 60%)",
} as const;

/** Priority badge color mapping */
export const PRIORITY_COLORS: Record<string, string> = {
  "High Review Priority": "text-red-400 bg-red-500/15 border-red-500/20",
  "Needs Review": "text-amber-400 bg-amber-500/15 border-amber-500/20",
  Informational: "text-blue-400 bg-blue-500/15 border-blue-500/20",
} as const;

/** Status badge color mapping */
export const STATUS_COLORS: Record<string, string> = {
  "Pending Review": "text-yellow-400 bg-yellow-500/15 border-yellow-500/20",
  Confirmed: "text-green-400 bg-green-500/15 border-green-500/20",
  "False Positive": "text-gray-400 bg-gray-500/15 border-gray-500/20",
  "Warning Issued": "text-amber-400 bg-amber-500/15 border-amber-500/20",
  "Coaching Required": "text-orange-400 bg-orange-500/15 border-orange-500/20",
  Escalated: "text-red-400 bg-red-500/15 border-red-500/20",
  Resolved: "text-emerald-400 bg-emerald-500/15 border-emerald-500/20",
} as const;

/** API timeout in milliseconds */
export const API_TIMEOUT = 10_000;

/** AI summary max display length before truncation */
export const AI_SUMMARY_MAX_LENGTH = 2000;

/** AI summary debounce interval in milliseconds */
export const AI_DEBOUNCE_MS = 30_000;
