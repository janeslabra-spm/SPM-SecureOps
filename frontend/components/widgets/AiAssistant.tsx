"use client";

import { useEffect, useState, useRef, useMemo, useCallback } from "react";
import {
  Sparkles,
  FileSearch,
  AlertCircle,
  ListChecks,
  TrendingUp,
  Loader2,
  Zap,
  RefreshCw,
  ShieldCheck,
  Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
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

const RISK_BG: Record<string, string> = {
  Low: "bg-green-500/10 border-green-500/30",
  Medium: "bg-warning/10 border-warning/30",
  High: "bg-orange-500/10 border-orange-500/30",
  Critical: "bg-destructive/10 border-destructive/30",
};

/**
 * AiAssistant — Bedrock AI advisory panel with manual activation.
 *
 * Cost-effective design:
 * - Analysis is NOT auto-triggered — user must click "Run Analysis"
 * - 60s minimum cooldown between requests prevents accidental spam
 * - Shows last analysis time so users know if data is stale
 * - Caching on the backend further reduces Bedrock calls
 */
const MIN_COOLDOWN_MS = 60_000; // 60s between allowed requests

export function AiAssistant({ events, viewContext, className }: AiAssistantProps) {
  const [analysis, setAnalysis] = useState<AiSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastAnalyzedAt, setLastAnalyzedAt] = useState<Date | null>(null);
  const [cooldownRemaining, setCooldownRemaining] = useState(0);
  const lastFetchTimeRef = useRef<number>(0);
  const cooldownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      if (cooldownTimerRef.current) clearInterval(cooldownTimerRef.current);
    };
  }, []);

  const startCooldownTimer = useCallback(() => {
    if (cooldownTimerRef.current) clearInterval(cooldownTimerRef.current);
    setCooldownRemaining(MIN_COOLDOWN_MS / 1000);

    cooldownTimerRef.current = setInterval(() => {
      const elapsed = Date.now() - lastFetchTimeRef.current;
      const remaining = Math.max(0, Math.ceil((MIN_COOLDOWN_MS - elapsed) / 1000));
      setCooldownRemaining(remaining);
      if (remaining === 0 && cooldownTimerRef.current) {
        clearInterval(cooldownTimerRef.current);
        cooldownTimerRef.current = null;
      }
    }, 1000);
  }, []);

  const runAnalysis = useCallback(async () => {
    if (events.length === 0) return;

    const now = Date.now();
    const elapsed = now - lastFetchTimeRef.current;
    if (elapsed < MIN_COOLDOWN_MS && lastFetchTimeRef.current !== 0) {
      return; // Still in cooldown
    }

    setLoading(true);
    setError(null);
    lastFetchTimeRef.current = Date.now();
    startCooldownTimer();

    try {
      const result = await apiClient.getAiSummary({
        events: events.slice(0, 20).map((e) => ({
          id: e.id,
          type: e.eventType ?? "unknown",
          confidence: e.confidence ?? 0,
          timestamp: e.timestamp ?? new Date().toISOString(),
        })),
        viewContext,
      });
      setAnalysis(result);
      setLastAnalyzedAt(new Date());
    } catch {
      setError("Analysis unavailable — check Bedrock configuration");
    } finally {
      setLoading(false);
    }
  }, [events, viewContext, startCooldownTimer]);

  const canRun = events.length > 0 && !loading && cooldownRemaining === 0;

  // Derive recommendations from analysis
  const recommendations = useMemo(() => {
    if (!analysis) return [];
    const recs: string[] = [];
    const totalViolations = Object.values(analysis.activeViolations).reduce(
      (sum, count) => sum + count,
      0
    );

    if (analysis.riskLevel === "Critical" || analysis.riskLevel === "High") {
      recs.push("Immediate supervisor review recommended");
    }
    if (totalViolations >= 5) {
      recs.push("Consider issuing a floor-wide compliance reminder");
    }
    if (analysis.activeViolations["PHONE_ON_TABLE"] && analysis.activeViolations["PHONE_ON_TABLE"] >= 3) {
      recs.push("Multiple phones on desks — check desk zone configuration");
    }
    if (analysis.activeViolations["PHONE_NEAR_PERSON"] && analysis.activeViolations["PHONE_NEAR_PERSON"] >= 3) {
      recs.push("Recurring phone-near-person events — possible active usage");
    }
    if (totalViolations === 0) {
      recs.push("No active violations — compliance is nominal");
    }
    return recs;
  }, [analysis]);

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
          bgClass: RISK_BG[analysis.riskLevel] ?? "",
        },
        {
          icon: ListChecks,
          label: "Active Violations",
          value:
            Object.entries(analysis.activeViolations)
              .map(([type, count]) => {
                // Format type names for readability
                const label = type
                  .replace("PHONE_ON_TABLE", "Phone on Desk")
                  .replace("PHONE_NEAR_PERSON", "Phone Near Person")
                  .replace("DOCUMENT_LEFT_ON_DESK", "Document on Desk");
                return `${label}: ${count}`;
              })
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
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="grid size-9 place-items-center rounded-lg bg-primary/15 text-primary ring-1 ring-primary/30">
            <Sparkles className="size-5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold">AI Compliance Assistant</h2>
            <p className="text-xs text-muted-foreground">On-demand advisory analysis</p>
          </div>
        </div>

        {/* Manual trigger button */}
        <Button
          variant="outline"
          size="sm"
          onClick={runAnalysis}
          disabled={!canRun}
          className={cn(
            "gap-1.5 text-xs transition-all",
            canRun
              ? "bg-primary/10 text-primary border-primary/30 hover:bg-primary/20"
              : "opacity-60"
          )}
        >
          {loading ? (
            <>
              <Loader2 className="size-3.5 animate-spin" />
              Analyzing...
            </>
          ) : cooldownRemaining > 0 ? (
            <>
              <Clock className="size-3.5" />
              {cooldownRemaining}s
            </>
          ) : (
            <>
              <Zap className="size-3.5" />
              Run Analysis
            </>
          )}
        </Button>
      </div>

      {/* Last analyzed indicator */}
      {lastAnalyzedAt && !loading && (
        <div className="mt-2 flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <RefreshCw className="size-3" />
          Last analyzed: {lastAnalyzedAt.toLocaleTimeString()}
          <span className="ml-1 text-muted-foreground/60">
            · {events.length} events
          </span>
        </div>
      )}

      {/* Content area */}
      <div className="mt-4 flex flex-col gap-3">
        {/* Initial state — no analysis yet */}
        {!loading && !error && !analysis && (
          <div className="rounded-xl border border-border bg-card/50 p-4 text-center">
            <Sparkles className="size-8 mx-auto text-muted-foreground/50 mb-2" />
            <p className="text-sm text-muted-foreground">
              {events.length === 0
                ? "No events to analyze."
                : "Click \"Run Analysis\" to get AI-powered insights on current compliance events."}
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground/60">
              Powered by Amazon Bedrock Nova Lite · Cost-optimized
            </p>
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center gap-2 py-6 text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            <span className="text-sm">Analyzing {events.length} events...</span>
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-3.5">
            <p className="text-sm text-muted-foreground">{error}</p>
          </div>
        )}

        {/* Analysis results */}
        {!loading &&
          rows.map(({ icon: Icon, label, value, colorClass, bgClass }) => (
            <div
              key={label}
              className={cn(
                "rounded-xl border border-border bg-card/50 p-3.5",
                label === "Risk Level" && bgClass
              )}
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

        {/* Recommendations section */}
        {!loading && recommendations.length > 0 && (
          <div className="rounded-xl border border-border bg-card/50 p-3.5">
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <ShieldCheck className="size-3.5" />
              Recommendations
            </div>
            <ul className="mt-2 space-y-1.5">
              {recommendations.map((rec, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-foreground">
                  <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" />
                  {rec}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="mt-4 flex items-center justify-between">
        <div className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5">
          <span className="size-2 rounded-full bg-primary pulse-dot" />
          <span className="text-xs font-medium text-muted-foreground">
            Powered by Amazon Bedrock
          </span>
        </div>
        <span className="text-[10px] text-muted-foreground/50">
          Manual activation · Cost-optimized
        </span>
      </div>
    </section>
  );
}

export default AiAssistant;
