"use client";

import { useEffect, useState, useRef, useMemo, useCallback } from "react";
import { Sparkles, FileSearch, AlertCircle, ListChecks, TrendingUp, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api-client";
import type { ComplianceEvent } from "@/lib/types";
import type { AiSummaryResponse } from "@/lib/types";
import type { ViewKey } from "@/lib/constants";

export interface AiAssistantProps {
  events: ComplianceEvent[];
  viewContext: ViewKey;
  className?: string;
}

const RISK_COLORS: Record<string, string> = {
  Low: "text-green-500",
  Medium: "text-warning",
  High: "text-orange-500 font-semibold",
  Critical: "text-destructive font-bold",
};

/**
 * AiAssistant — Bedrock AI advisory panel showing live compliance analysis.
 *
 * Calls the backend /api/ai/summary endpoint which proxies to Amazon Bedrock
 * Nova Lite. Falls back to a rule-based summary if Bedrock is unavailable.
 */
/** Minimum seconds between AI analysis requests (cost control). */
const MIN_REFRESH_INTERVAL_MS = 60_000;

export function AiAssistant({ events, viewContext, className }: AiAssistantProps) {
  const [analysis, setAnalysis] = useState<AiSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastFetchTimeRef = useRef<number>(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestEventsRef = useRef(events);
  const latestViewRef = useRef(viewContext);

  // Always keep refs current so the deferred fetch uses latest data
  latestEventsRef.current = events;
  latestViewRef.current = viewContext;

  // Stable fetch function that always reads from refs
  const doFetch = useCallback(async () => {
    const currentEvents = latestEventsRef.current;
    const currentView = latestViewRef.current;

    if (currentEvents.length === 0) {
      setAnalysis(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    lastFetchTimeRef.current = Date.now();

    try {
      const result = await apiClient.getAiSummary({
        events: currentEvents.slice(0, 20).map((e) => ({
          id: e.id,
          type: e.eventType ?? "unknown",
          confidence: e.confidence ?? 0,
          timestamp: e.timestamp ?? new Date().toISOString(),
        })),
        viewContext: currentView,
      });
      setAnalysis(result);
    } catch {
      setError("Analysis unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  // Derive a stable fingerprint from event IDs
  const eventsKey = useMemo(
    () => events.map((e) => e.id).sort().join(","),
    [events],
  );

  useEffect(() => {
    if (events.length === 0) {
      setAnalysis(null);
      return;
    }

    const now = Date.now();
    const elapsed = now - lastFetchTimeRef.current;

    if (elapsed >= MIN_REFRESH_INTERVAL_MS || lastFetchTimeRef.current === 0) {
      // Enough time has passed — fetch immediately
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      doFetch();
    } else if (!timerRef.current) {
      // Schedule a deferred fetch for when the cooldown expires
      const delay = MIN_REFRESH_INTERVAL_MS - elapsed;
      timerRef.current = setTimeout(() => {
        timerRef.current = null;
        doFetch();
      }, delay);
    }
    // If a timer is already pending, do nothing — it will pick up latest data via refs

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [eventsKey, viewContext, doFetch]);

  // Build display rows from analysis
  const rows = analysis
    ? [
        {
          icon: FileSearch,
          label: "Event Summary",
          value: analysis.summary,
        },
        {
          icon: AlertCircle,
          label: "Risk Level",
          value: analysis.riskLevel,
          colorClass: RISK_COLORS[analysis.riskLevel] ?? "",
        },
        {
          icon: ListChecks,
          label: "Active Violations",
          value:
            Object.entries(analysis.activeViolations)
              .map(([type, count]) => `${type}: ${count}`)
              .join(", ") || "None",
        },
        {
          icon: TrendingUp,
          label: "Patterns",
          value: analysis.patterns,
        },
      ]
    : [];

  return (
    <section className={cn("glass flex flex-col rounded-2xl p-5", className)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="grid size-9 place-items-center rounded-lg bg-primary/15 text-primary ring-1 ring-primary/30">
            <Sparkles className="size-5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold">AI Compliance Assistant</h2>
            <p className="text-xs text-muted-foreground">Advisory analysis only</p>
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-3">
        {loading && (
          <div className="flex items-center justify-center gap-2 py-6 text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            <span className="text-sm">Analyzing events...</span>
          </div>
        )}

        {error && !loading && (
          <div className="rounded-xl border border-border bg-card/50 p-3.5">
            <p className="text-sm text-muted-foreground">{error}</p>
          </div>
        )}

        {!loading && !error && events.length === 0 && (
          <div className="rounded-xl border border-border bg-card/50 p-3.5">
            <p className="text-sm text-muted-foreground">No events to analyze.</p>
          </div>
        )}

        {!loading &&
          rows.map(({ icon: Icon, label, value, colorClass }) => (
            <div
              key={label}
              className="rounded-xl border border-border bg-card/50 p-3.5"
            >
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                <Icon className="size-3.5" />
                {label}
              </div>
              <p
                className={cn(
                  "mt-1.5 text-sm leading-relaxed text-foreground",
                  colorClass,
                )}
              >
                {value}
              </p>
            </div>
          ))}
      </div>

      <div className="mt-4 flex items-center gap-2 self-start rounded-full border border-border bg-card px-3 py-1.5">
        <span className="size-2 rounded-full bg-primary pulse-dot" />
        <span className="text-xs font-medium text-muted-foreground">
          Powered by Amazon Bedrock
        </span>
      </div>
    </section>
  );
}

export default AiAssistant;
