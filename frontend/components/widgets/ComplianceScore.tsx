"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";
import type { ComplianceEvent } from "@/lib/types";

export interface ComplianceScoreProps {
  events: ComplianceEvent[];
  className?: string;
}

/**
 * Calculate the compliance score based on event review status and outcomes.
 *
 * Score formula:
 * - Base score starts at 100% (fully compliant)
 * - Each unresolved (Pending Review) event reduces the score
 * - Confirmed violations reduce the score more heavily
 * - False Positives and Resolved events don't penalize
 * - Score floors at 0%
 */
export function calculateComplianceScore(events: ComplianceEvent[]): number {
  if (events.length === 0) return 100;

  let penaltyPoints = 0;
  const maxPenalty = events.length;

  for (const event of events) {
    switch (event.status) {
      case "Pending Review":
        penaltyPoints += 0.6;
        break;
      case "Confirmed":
      case "Escalated":
      case "Warning Issued":
      case "Coaching Required":
        penaltyPoints += 1.0;
        break;
      case "False Positive":
      case "Resolved":
        penaltyPoints += 0;
        break;
      default:
        penaltyPoints += 0.5;
    }
  }

  return Math.max(0, 100 - (penaltyPoints / maxPenalty) * 100);
}

export function ComplianceScore({ events, className }: ComplianceScoreProps) {
  const score = Math.round(calculateComplianceScore(events));

  const stats = useMemo(() => {
    const now = new Date();
    const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const todayEvents = events.filter((e) => new Date(e.timestamp) >= startOfDay);
    return {
      today: todayEvents.length,
      pending: events.filter((e) => e.status === "Pending Review").length,
      reviewed: events.filter((e) => e.status !== "Pending Review").length,
      falsePositives: events.filter((e) => e.status === "False Positive").length,
    };
  }, [events]);

  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  const metrics = [
    { label: "Today Events", value: String(stats.today), tone: "text-foreground" },
    { label: "Pending Reviews", value: String(stats.pending), tone: "text-warning" },
    { label: "Reviewed", value: String(stats.reviewed), tone: "text-success" },
    { label: "False Positives", value: String(stats.falsePositives), tone: "text-muted-foreground" },
  ];

  return (
    <section className={cn("glass flex flex-col rounded-2xl p-5", className)}>
      <h2 className="text-sm font-semibold">Compliance Monitoring Score</h2>

      {/* Horizontal layout: Score ring + metrics side by side */}
      <div className="mt-4 flex items-center gap-6">
        {/* Score ring */}
        <div className="relative grid shrink-0 place-items-center">
          <svg width="108" height="108" className="-rotate-90">
            <circle
              cx="54"
              cy="54"
              r={radius}
              fill="none"
              strokeWidth="10"
              className="stroke-muted"
            />
            <circle
              cx="54"
              cy="54"
              r={radius}
              fill="none"
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              className={cn(
                "transition-all duration-700",
                score >= 70 ? "stroke-success" : score >= 40 ? "stroke-warning" : "stroke-destructive"
              )}
            />
          </svg>
          <div className="absolute flex flex-col items-center">
            <span className="text-2xl font-bold tabular-nums">{score}%</span>
            <span className="text-[10px] text-muted-foreground">Score</span>
          </div>
        </div>

        {/* Metrics grid */}
        <div className="flex-1 grid grid-cols-2 gap-2">
          {metrics.map((m) => (
            <div key={m.label} className="rounded-lg border border-border bg-card/50 px-3 py-2">
              <p className={cn("text-xl font-bold tabular-nums", m.tone)}>{m.value}</p>
              <p className="text-[10px] leading-tight text-muted-foreground">{m.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Status indicator */}
      <div className={cn(
        "mt-3 flex items-center justify-center gap-2 rounded-full px-3 py-1.5 ring-1",
        score >= 70
          ? "bg-success/12 ring-success/25"
          : score >= 40
            ? "bg-warning/12 ring-warning/25"
            : "bg-destructive/12 ring-destructive/25"
      )}>
        <span className={cn(
          "size-2 rounded-full",
          score >= 70 ? "bg-success" : score >= 40 ? "bg-warning" : "bg-destructive"
        )} />
        <span className={cn(
          "text-xs font-medium",
          score >= 70 ? "text-success" : score >= 40 ? "text-warning" : "text-destructive"
        )}>
          {score >= 70
            ? "Within Monitoring Threshold"
            : score >= 40
              ? "Review Required"
              : "Critical — Immediate Action Needed"}
        </span>
      </div>

      <p className="mt-2 text-[10px] leading-relaxed text-muted-foreground">
        Reflects monitoring compliance trends, not employee performance.
      </p>
    </section>
  );
}

export default ComplianceScore;
